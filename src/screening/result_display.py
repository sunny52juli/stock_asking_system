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
            result: 查询结果字典
        """
        if not result.get("messages"):
            return
        
        final_message = result["messages"][-1]
        content = (
            final_message.content 
            if hasattr(final_message, 'content') 
            else str(final_message)
        )
        
        logger.info("\n📊 Agent 分析结果:")
        logger.info("-" * 60)
        
        # 直接显示 Agent 的回复内容
        logger.info(content)
        
        # 如果有 candidates 数据，额外显示结构化的股票列表
        candidates = result.get("candidates", [])
        if candidates:
            logger.info(f"\n{'='*60}")
            logger.info(f"✅ 共筛选出 {len(candidates)} 只股票")
            logger.info(f"{'='*60}")
            
            # 显示前10只股票的详细信息
            display_count = min(10, len(candidates))
            for i, stock in enumerate(candidates[:display_count], 1):
                ts_code = stock.get("ts_code", "N/A")
                name = stock.get("name", "N/A")
                industry = stock.get("industry", "N/A")
                confidence = stock.get("confidence", 0)
                reason = stock.get("reason", "")
                metrics = stock.get("metrics", {})
                
                logger.info(f"\n### {i}. **{name} ({ts_code})** - {industry}")
                
                # 显示关键指标
                if metrics:
                    for key, value in list(metrics.items())[:3]:  # 最多显示3个指标
                        if isinstance(value, (int, float)):
                            if "pct" in key.lower() or "change" in key.lower():
                                logger.info(f"   - {key}: {value:.2%}")
                            elif "vol" in key.lower() or "volume" in key.lower():
                                logger.info(f"   - {key}: {value:.2f}")
                            else:
                                logger.info(f"   - {key}: {value:.4f}")
                
                logger.info(f"   - 置信度: {confidence:.2%}")
                if reason:
                    logger.info(f"   - 理由: {reason[:80]}")
            
            if len(candidates) > 10:
                logger.info(f"\n... 还有 {len(candidates) - 10} 只股票（详见保存的脚本）")
    
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
