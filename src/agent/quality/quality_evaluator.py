"""质量评估协议与选股评估器实现.

定义通用的 QualityEvaluator 协议，并提供选股领域的 ScreeningQualityEvaluator 实现。
支持 Protocol 设计，便于领域扩展。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@runtime_checkable
class QualityEvaluator(Protocol):
    """质量评估器协议.

    所有领域特定的质量评估器必须实现此协议。
    """

    def evaluate(self, query: str, result: dict[str, Any]) -> dict[str, Any]:
        """评估执行结果质量.

        Args:
            query: 用户查询
            result: 执行结果

        Returns:
            包含 quality_score, issues, suggestions, should_retry 的字典
        """
        ...


@dataclass
class EvaluationThresholds:
    """评估阈值配置."""

    min_sharpe_ratio: float = 0.0
    max_drawdown_threshold: float = 0.30


class ScreeningQualityEvaluator:
    """选股领域的质量评估器 - 实现 QualityEvaluator 协议.
    
    从 reflection.md 加载评估规则，支持用户动态调整。
    增强版：多维度评估（候选数量/行业多样性/代码规范性）
    """
    
    def __init__(self, rules_dir: Path | None = None, thresholds: EvaluationThresholds | None = None):
        """初始化评估器.
        
        Args:
            rules_dir: Rules 目录路径，默认从 app/setting/rules 加载
            thresholds: 评估阈值配置，为 None 时使用默认值
        """
        if rules_dir is None:
            # 使用项目根目录的 app/setting/rules（绝对路径）
            # quality_evaluator.py -> quality/ -> agent/ -> src/ -> 项目根目录
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent
            self.rules_dir = project_root / "app" / "setting" / "rules"
            
            logger.debug(f"Rules dir: {self.rules_dir}")
            logger.debug(f"Project root: {project_root}")
        else:
            self.rules_dir = rules_dir
        
        self.reflection_rules = self._load_reflection_rules()
        self.thresholds = thresholds or EvaluationThresholds()
    
    def _load_reflection_rules(self) -> str:
        """加载 reflection.md 内容.
        
        Returns:
            reflection.md 的文本内容
        """
        reflection_file = self.rules_dir / "reflection.md"
        if not reflection_file.exists():
            logger.warning(f"reflection.md 不存在: {reflection_file}")
            return ""
        
        try:
            content = reflection_file.read_text(encoding="utf-8")
            logger.info(f"已加载 reflection.md ({len(content)} 字符)")
            return content
        except Exception as e:
            logger.error(f"加载 reflection.md 失败: {e}")
            return ""
    
    def evaluate(self, query: str, result: dict[str, Any]) -> dict[str, Any]:
        """评估筛选结果质量 - 增强版（支持量化评分）.
        
        Args:
            query: 用户查询
            result: 筛选结果
            
        Returns:
            包含 quality_score, issues, suggestions, should_retry 的字典
        """
        all_issues = []
        all_suggestions = []
        scores = []
        
        # 提取候选股票（从多个可能的位置）
        candidates = result.get("candidates", [])
        
        # 如果顶层没有，尝试从工具调用结果中提取
        if not candidates:
            messages = result.get("messages", [])
            for msg in reversed(messages):
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        if tool_call.get("name") == "run_screening":
                            try:
                                import json
                                args = tool_call.get("args", {})
                                if "screening_logic_json" in args:
                                    # 找到了工具调用，但需要从返回结果中获取 candidates
                                    pass
                            except Exception:
                                pass
                
                # 尝试从 content 中解析 JSON
                if hasattr(msg, "content") and msg.content:
                    try:
                        import json
                        content_str = msg.content if isinstance(msg.content, str) else str(msg.content)
                        if "candidates" in content_str:
                            # 尝试提取 JSON
                            start = content_str.find('{')
                            if start >= 0:
                                json_str = content_str[start:]
                                parsed = json.loads(json_str)
                                if isinstance(parsed, dict) and "candidates" in parsed:
                                    candidates = parsed["candidates"]
                                    break
                    except (json.JSONDecodeError, TypeError):
                        pass
        
        # 1. 评估候选股票数量
        candidate_count = len(candidates)
        score, issues, suggestions = self._evaluate_candidate_count(candidate_count)
        scores.append(score)
        all_issues.extend(issues)
        all_suggestions.extend(suggestions)
        
        # 如果候选数量为 0，直接返回低分
        if candidate_count == 0:
            return {
                "quality_score": 0.0,
                "issues": all_issues,
                "suggestions": all_suggestions,
                "should_retry": True,
                "candidate_count": candidate_count,
            }
        
        # 2. 评估行业多样性
        industry_diversity_score = self._evaluate_industry_diversity(candidates)
        score, issues, suggestions = self._evaluate_industry_diversity_score(industry_diversity_score)
        scores.append(score)
        all_issues.extend(issues)
        all_suggestions.extend(suggestions)
        
        # 3. 评估回测指标（如果有）
        metrics = result.get("backtest_metrics", {})
        score, issues, suggestions = self._evaluate_backtest_metrics(metrics)
        scores.append(score)
        all_issues.extend(issues)
        all_suggestions.extend(suggestions)
        
        # 4. 评估代码规范性（如果生成了脚本）
        script_code = result.get("script_code", "")
        if script_code:
            code_quality = self._evaluate_code_quality(script_code)
            if code_quality["has_issues"]:
                all_issues.extend(code_quality["issues"])
                all_suggestions.extend(code_quality["suggestions"])
                scores.append(0.7)  # 代码有问题扣分
            else:
                scores.append(1.0)
        
        # 计算综合得分（加权平均）
        weights = [0.4, 0.2, 0.2, 0.2] if script_code else [0.5, 0.3, 0.2]
        weights = weights[:len(scores)]  # 确保权重数量匹配
        quality_score = sum(s * w for s, w in zip(scores, weights, strict=False))
        quality_score = max(0.0, min(1.0, quality_score))
        
        should_retry = quality_score < 0.5 and len(all_suggestions) > 0
        
        return {
            "quality_score": quality_score,
            "issues": all_issues,
            "suggestions": all_suggestions,
            "should_retry": should_retry,
            "reflection_rules": self.reflection_rules,
            "candidate_count": candidate_count,
            "metrics": {
                "industry_diversity_score": industry_diversity_score,
            },
        }
    
    def _evaluate_industry_diversity(self, candidates: list[dict]) -> float:
        """评估行业多样性.
        
        Args:
            candidates: 候选股票列表
            
        Returns:
            多样性评分（0-1），越高表示行业分布越均匀
        """
        if not candidates:
            return 0.0
        
        # 统计行业分布
        industry_counts = {}
        for stock in candidates:
            industry = stock.get("industry", "未知")
            industry_counts[industry] = industry_counts.get(industry, 0) + 1
        
        total = len(candidates)
        num_industries = len(industry_counts)
        
        if num_industries <= 1:
            return 0.0
        
        # 计算熵值（Entropy）作为多样性指标
        import math
        entropy = 0.0
        for count in industry_counts.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log(p)
        
        # 归一化到 0-1
        max_entropy = math.log(num_industries)
        diversity_score = entropy / max_entropy if max_entropy > 0 else 0.0
        
        return diversity_score

    def _evaluate_candidate_count(self, count: int) -> tuple[float, list[str], list[str]]:
        """评估候选股票数量.
        
        注意：候选数量控制已通过 rules/*.md 实现，此方法仅做基本检查。
        """
        issues = []
        suggestions = []
        score = 1.0

        if count == 0:
            issues.append("筛选结果为空，未找到符合条件的股票")
            suggestions.append("放宽筛选条件（如降低涨幅阈值、扩大行业范围）")
            suggestions.append("检查筛选逻辑是否有误")
            suggestions.append("考虑减少技术指标的约束条件")
            return 0.0, issues, suggestions

        # 候选数量控制由 Agent 根据 reflection.md 规则自行判断
        # 这里不做具体数值限制
        return score, issues, suggestions

    def _evaluate_industry_diversity_score(
        self, diversity_score: float
    ) -> tuple[float, list[str], list[str]]:
        """评估行业多样性得分."""
        issues = []
        suggestions = []

        if diversity_score >= 0.5:
            return 1.0, [], []
        elif diversity_score >= 0.3:
            return 0.85, [], []
        else:
            issues.append(f"行业集中度过高（多样性得分 {diversity_score:.2f}），缺乏分散化")
            suggestions.append("扩大行业范围以降低集中度风险")
            return 0.6, issues, suggestions

    def _evaluate_backtest_metrics(
        self, metrics: dict[str, float]
    ) -> tuple[float, list[str], list[str]]:
        """评估回测指标."""
        t = self.thresholds
        issues = []
        suggestions = []
        score = 1.0

        if not metrics:
            return 1.0, [], []

        sharpe = metrics.get("sharpe_ratio", 0.0)
        if sharpe < t.min_sharpe_ratio:
            issues.append(f"夏普比率过低（{sharpe:.2f}），风险调整后收益不佳")
            suggestions.append("优化策略参数以提高风险调整收益")
            score *= 0.7

        max_dd = metrics.get("max_drawdown", 0.0)
        if max_dd > t.max_drawdown_threshold:
            issues.append(f"最大回撤过大（{max_dd * 100:.1f}%），风险偏高")
            suggestions.append("增加止损机制或调整仓位管理")
            score *= 0.7

        return score, issues, suggestions
    
    def _evaluate_code_quality(self, code: str) -> dict[str, Any]:
        """评估生成代码的质量.
        
        Args:
            code: 生成的 Python 代码
            
        Returns:
            包含 has_issues, issues, suggestions 的字典
        """
        issues = []
        suggestions = []
        
        # 1. 检查是否包含必要的导入
        required_imports = ["import pandas", "from datahub"]
        missing_imports = []
        for imp in required_imports:
            if imp not in code:
                missing_imports.append(imp)
        
        if missing_imports:
            issues.append(f"缺少必要的导入：{', '.join(missing_imports)}")
            suggestions.append("确保包含所有必要的库导入")
        
        # 2. 检查是否有主函数入口
        if "if __name__ ==" not in code and "def main" not in code:
            issues.append("缺少主函数入口")
            suggestions.append("添加 if __name__ == '__main__' 或 main() 函数")
        
        # 3. 检查是否有注释
        comment_ratio = code.count("#") / max(len(code.split("\n")), 1)
        if comment_ratio < 0.1:
            issues.append("代码注释不足")
            suggestions.append("添加必要的注释说明关键逻辑")
        
        # 4. 检查是否有硬编码的魔法数字
        magic_numbers = re.findall(r'(?<!\w)(?:\d+\.\d+|\d{2,})(?!\w)', code)
        if len(magic_numbers) > 5:
            issues.append(f"存在过多魔法数字（{len(magic_numbers)}个）")
            suggestions.append("将常量提取为命名变量")
        
        # 5. 检查异常处理
        if "try:" not in code or "except" not in code:
            issues.append("缺少异常处理")
            suggestions.append("添加 try-except 块处理潜在错误")
        
        return {
            "has_issues": len(issues) > 0,
            "issues": issues,
            "suggestions": suggestions,
        }
