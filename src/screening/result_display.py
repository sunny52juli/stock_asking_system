"""结果显示工具 - 格式化显示查询结果."""

from __future__ import annotations

import re
from typing import Any

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class ResultDisplayer:
    """结果显示器 - 格式化显示 Agent 查询结果."""
    
    @staticmethod
    def display(result: dict):
        """显示查询结果.
        
        Args:
            result: 查询结果字典 (支持 Agent 消息格式或直接 candidates 格式)
        """
        # 1. 处理直接传入 candidates 的情况（编辑模式预览）
        if "candidates" in result and not result.get("messages"):
            ResultDisplayer._display_candidates_table(result)
            return

        # 2. 处理 Agent 消息格式 - ✅ 跳过 Agent 的自然语言总结，直接显示详细表格
        # 提取 candidates 和 screening_logic
        candidates = []
        logic = {}
        
        if result.get("messages"):
            # 从最后一条消息中提取 candidates
            final_message = result["messages"][-1]
            if hasattr(final_message, 'additional_kwargs'):
                candidates = final_message.additional_kwargs.get('candidates', [])
                logic = final_message.additional_kwargs.get('screening_logic', {})
        
        # 如果没有 candidates，尝试从 result 顶层获取
        if not candidates:
            candidates = result.get("candidates", [])
            logic = result.get("screening_logic", {})
        
        # 显示详细表格
        if candidates:
            ResultDisplayer._display_candidates_table({
                "candidates": candidates,
                "screening_logic": logic
            })

    @staticmethod
    def _display_candidates_table(result: dict):
        """以详细表格形式展示候选股票."""
        candidates = result.get("candidates", [])
        logic = result.get("screening_logic", {})
        
        if not candidates:
            logger.info("💡 未找到符合条件的股票")
            return

        logger.info(f"\n[OK] 找到 {len(candidates)} 只符合条件的股票\n")
        
        # 策略说明
        rationale = logic.get("rationale", "")
        if rationale:
            logger.info(f"📝 策略逻辑: {rationale}\n")

        # 行业分布统计
        industries = {}
        for stock in candidates:
            ind = stock.get("industry", "未知")
            industries[ind] = industries.get(ind, 0) + 1
        
        logger.info("🏭 行业分布:")
        for ind, count in sorted(industries.items(), key=lambda x: x[1], reverse=True)[:5]:
            logger.info(f"   • {ind}: {count} 只")
        
        # 详细表格 (Markdown 格式)
        logger.info("\n📈 筛选结果详情 (Top 10):")
        
        # 动态生成表头：根据 metrics 中的键值自动扩展列
        base_headers = ["排名", "代码", "名称", "行业", "综合评分"]
        
        # ✅ 优先展示筛选表达式中使用的核心指标，而不是简单取前3个
        expression = logic.get("expression", "")
        expression_vars = set()  # 表达式中使用的变量名
        
        # 获取所有可用的指标键
        sample_metrics = candidates[0].get("metrics", {}) if candidates else {}
        all_metric_keys = list(sample_metrics.keys())
        
        if expression:
            # 从表达式中提取变量名（字母、数字、下划线组合，但不是数字）
            import re
            # 匹配变量名：不是纯数字，且不是 and/or/not/True/False 等关键字
            all_vars = re.findall(r'\b([a-zA-Z_]\w*)\b', expression)
            # 过滤出表达式中的变量（排除 Python 关键字和数字）
            keywords = {'and', 'or', 'not', 'True', 'False', 'None', 'if', 'else', 'lambda'}
            expression_vars = {v for v in all_vars if v not in keywords and not v.isdigit()}
            
            # 🔍 调试：打印提取的表达式变量
            logger.debug(f"🔍 表达式: {expression}")
            logger.debug(f"🔍 提取的变量: {expression_vars}")
            logger.debug(f"🔍 所有可用指标: {all_metric_keys}")
        
        # 筛选出表达式中使用的指标，并按表达式中的出现顺序排序
        priority_metrics = [k for k in all_metric_keys if k in expression_vars]
        
        # 如果表达式中的指标不足3个，补充其他指标（最多总共展示5个）
        if len(priority_metrics) < 3:
            other_metrics = [k for k in all_metric_keys if k not in expression_vars]
            priority_metrics = priority_metrics + other_metrics[:5 - len(priority_metrics)]
        elif len(priority_metrics) > 5:
            # 最多展示5个指标，避免表格过宽
            priority_metrics = priority_metrics[:5]
        
        metric_keys = priority_metrics
        headers = base_headers + [f"{k.replace('_', ' ').title()}" for k in metric_keys]

        # 打印 Markdown 表头
        header_line = "| " + " | ".join(headers) + " |"
        separator = "|" + "|".join([":---:" if h == "排名" or h == "综合评分" else ":---" for h in headers]) + "|"
        logger.info(header_line)
        logger.info(separator)
        
        # 打印数据行
        for i, stock in enumerate(candidates[:10], 1):
            ts_code = stock.get("ts_code", "N/A")
            name = f"**{stock.get('name', 'N/A')}**"  # 加粗名称
            industry = stock.get("industry", "N/A")
            score = f"**{stock.get('confidence', 0):.2f}**"  # 加粗得分
            
            row_data = [str(i), ts_code, name, industry, score]
            
            # 填充指标数据
            metrics = stock.get("metrics", {})
            for k in metric_keys:
                val = metrics.get(k, 0)
                if isinstance(val, float):
                    if 'rate' in k or 'ratio' in k:
                        row_data.append(f"{val*100:.1f}%")
                    else:
                        row_data.append(f"{val:.2f}")
                else:
                    row_data.append(str(val))
            
            logger.info("| " + " | ".join(row_data) + " |")
    
    @staticmethod
    def _extract_stock_codes(content: str) -> list[str]:
        """从文本中提取股票代码.
        
        Args:
            content: 文本内容
            
        Returns:
            股票代码列表
        """
        # 匹配 A 股股票代码格式：6位数字 + .SZ/.SH/.BJ
        pattern = r'\b(\d{6}\.(?:SZ|SH|BJ))\b'
        matches = re.findall(pattern, content)
        return list(dict.fromkeys(matches))  # 去重并保持顺序
