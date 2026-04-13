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
        logger.info(content[:800])
        
        # 提取股票代码
        stock_codes = re.findall(r'\b[0-9]{6}\.[A-Z]{2}\b', content)
        if stock_codes:
            logger.info("\n🎯 推荐股票:")
            logger.info("-" * 60)
            for code in stock_codes[:20]:
                logger.info(f"  - {code}")
            if len(stock_codes) > 20:
                logger.info(f"  ... 还有 {len(stock_codes) - 20} 只股票)")
        else:
            logger.info("\n⚠️ 未检测到明确的股票代码)")
