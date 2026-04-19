"""质量评估协议与选股评估器实现.

定义通用的 QualityEvaluator 协议，并提供选股领域的 ScreeningQualityEvaluator 实现。
支持 Protocol 设计，便于领域扩展。

质量评估标准从 .stock_asking/skills/quality-criteria/SKILL.md 动态加载，
避免硬编码评分规则，便于灵活调整。
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
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
    """评估阈值配置（从 SKILL.md 解析）."""

    # 候选数量阈值
    candidate_count_ranges: list[tuple[tuple[int, int], float]] = field(default_factory=list)
    
    # 行业分散度阈值
    industry_diversity_thresholds: list[tuple[float, float]] = field(default_factory=list)
    
    # 回测指标阈值
    min_sharpe_ratio: float = 0.0
    max_drawdown_threshold: float = 0.30
    min_win_rate: float = 0.50
    
    # 权重配置
    weights: dict[str, float] = field(default_factory=lambda: {
        "candidate_count": 0.4,
        "industry_diversity": 0.2,
        "backtest_metrics": 0.2,
        "screening_logic": 0.2,
    })
    
    # 决策阈值
    pass_threshold: float = 0.7
    warning_threshold: float = 0.5


class ScreeningQualityEvaluator:
    """选股领域的质量评估器 - 实现 QualityEvaluator 协议.
    
    从 quality-criteria.md 加载评估规则，支持用户动态调整。
    增强版：多维度评估（候选数量/行业多样性/代码规范性）
    """
    
    def __init__(self, rules_dir: Path | None = None, thresholds: EvaluationThresholds | None = None):
        """初始化评估器.
        
        Args:
            rules_dir: Rules 目录路径，默认从 .stock_asking/rules 加载
            thresholds: 评估阈值配置，为 None 时使用默认值
        """
        if rules_dir is None:
            # 使用项目根目录的 .stock_asking/rules（绝对路径）
            # quality_evaluator.py -> quality/ -> agent/ -> src/ -> 项目根目录
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent.parent  # 需要4层
            self.rules_dir = project_root / ".stock_asking" / "rules"
            
            logger.debug(f"Rules dir: {self.rules_dir}")
            logger.debug(f"Project root: {project_root}")
        else:
            self.rules_dir = rules_dir
        
        self.quality_criteria = self._load_quality_criteria()
        self.thresholds = thresholds or EvaluationThresholds()
    
    def _load_quality_criteria(self) -> str:
        """加载 quality-criteria.md 内容.
        
        Returns:
            quality-criteria.md 的文本内容
        """
        criteria_file = self.rules_dir / "quality-criteria.md"
        if not criteria_file.exists():
            logger.warning(f"quality-criteria.md 不存在: {criteria_file}")
            return ""
        
        try:
            content = criteria_file.read_text(encoding="utf-8")
            logger.info(f"已加载 quality-criteria.md ({len(content)} 字符)")
            return content
        except Exception as e:
            logger.error(f"加载 quality-criteria.md 失败: {e}")
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
                                args = tool_call.get("args", {})
                                if "screening_logic_json" in args:
                                    # 找到了工具调用，但需要从返回结果中获取 candidates
                                    pass
                            except Exception:
                                pass
                
                # 尝试从 content 中解析 JSON
                if hasattr(msg, "content") and msg.content:
                    try:
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
        
        # 如果候选数量为 0，返回低分但不强制重试（避免死循环）
        if candidate_count == 0:
            return {
                "quality_score": 0.0,
                "issues": all_issues,
                "suggestions": all_suggestions,
                "should_retry": False,  # 不强制重试，让 Agent 自行决定
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
        
        # 计算综合得分（使用 SKILL.md 中定义的权重）
        weights = self.thresholds.weights
        weight_list = []
        score_keys = ["candidate_count", "industry_diversity", "backtest_metrics"]
        if script_code:
            score_keys.append("screening_logic")
        
        for key in score_keys:
            if key in weights:
                weight_list.append(weights[key])
        
        # 归一化权重
        total_weight = sum(weight_list)
        if total_weight > 0:
            weight_list = [w / total_weight for w in weight_list]
        
        quality_score = sum(s * w for s, w in zip(scores, weight_list, strict=False))
        quality_score = max(0.0, min(1.0, quality_score))
        
        # 使用 SKILL.md 中定义的决策阈值
        should_retry = quality_score < self.thresholds.warning_threshold and len(all_suggestions) > 0
        
        return {
            "quality_score": quality_score,
            "issues": all_issues,
            "suggestions": all_suggestions,
            "should_retry": should_retry,
            "quality_criteria": self.quality_criteria,  # 返回评估规则供 Agent 参考
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
        
        注意：具体的数量标准由 quality-criteria.md 定义，Agent 自行判断。
        此方法只做基本的技术检查。
        """
        issues = []
        suggestions = []
        score = 1.0

        if count == 0:
            issues.append("筛选结果为空，未找到符合条件的股票")
            suggestions.append(
                "可能原因：\n"
                "  1. 筛选条件过于严格\n"
                "  2. 多个条件同时满足的股票极少\n"
                "  3. 当前市场环境下无符合该策略的股票\n"
                "建议：参考 quality_criteria 中的标准，放宽阈值或减少约束条件数量"
            )
            return 0.0, issues, suggestions

        # 具体数量评估由 Agent 根据 quality_criteria 自行判断
        return score, issues, suggestions

    def _evaluate_industry_diversity_score(
        self, diversity_score: float
    ) -> tuple[float, list[str], list[str]]:
        """评估行业多样性得分.
        
        注意：具体的分散度标准由 quality-criteria.md 定义，Agent 自行判断。
        此方法只做基本的技术检查。
        """
        issues = []
        suggestions = []
        
        # 基本检查：如果多样性极低，给出警告
        if diversity_score < 0.3:
            issues.append(f"行业集中度过高（多样性得分 {diversity_score:.2f}），缺乏分散化")
            suggestions.append("参考 quality_criteria 中的标准，扩大行业范围以降低集中度风险")
            return 0.6, issues, suggestions
        
        # 其他情况由 Agent 根据 quality_criteria 自行判断
        return 1.0, [], []

    def _evaluate_backtest_metrics(
        self, metrics: dict[str, float]
    ) -> tuple[float, list[str], list[str]]:
        """评估回测指标（从 SKILL.md 动态加载规则）."""
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
        
        win_rate = metrics.get("win_rate", 0.0)
        if win_rate < t.min_win_rate:
            issues.append(f"胜率过低（{win_rate * 100:.1f}%），策略有效性不足")
            suggestions.append("重新审视选股逻辑或调整参数")
            score *= 0.8

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
