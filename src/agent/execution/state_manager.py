"""会话状态管理器 - 管理跨查询的数据缓存和增量计算."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import polars as pl

from infrastructure.config.settings import Settings
from src.agent.services.stock_pool_service import StockPoolService
from src.agent.cache.indicator_cache import IndicatorCache
from src.agent.cache.screening_cache import ScreeningCache

logger = logging.getLogger(__name__)


class SessionStateManager:
    """会话状态管理器 - 维护跨查询的共享状态."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.data: pl.DataFrame | None = None
        self.stock_codes: list[str] | None = None
        self.index_data: pl.DataFrame | None = None
        
        # 缓存层
        self.indicator_cache = IndicatorCache()
        self.screening_cache = ScreeningCache()
        
        # 历史追踪
        self.query_history: list[dict[str, Any]] = []
        self.last_screening_logic: dict | None = None
    
    def load_base_data(self) -> None:
        """加载基础数据（带缓存）."""
        stock_pool_service = StockPoolService(self.settings)
        self.data, self.stock_codes, self.index_data = stock_pool_service.apply_filter()
        logger.info(f"[OK] 基础数据加载完成: {len(self.data)} 条记录")
    
    def is_data_loaded(self) -> bool:
        """检查数据是否已加载."""
        return self.data is not None and len(self.data) > 0
    
    def record_query(self, query: str, logic: dict, results: list[dict]) -> None:
        """记录查询历史."""
        from datetime import datetime
        self.query_history.append({
            "query": query,
            "logic": logic,
            "result_count": len(results),
            "timestamp": datetime.now()
        })
        self.last_screening_logic = logic
    
    def can_reuse_indicators(self, new_logic: dict) -> list[str]:
        """检测哪些指标可以复用."""
        if not self.last_screening_logic:
            return []
        
        old_tools = {t["tool"] for t in self.last_screening_logic.get("tools", [])}
        new_tools = {t["tool"] for t in new_logic.get("tools", [])}
        
        reusable = old_tools & new_tools
        if reusable:
            logger.info(f"♻️ 可复用指标: {', '.join(reusable)}")
        
        return list(reusable)
    
    def clear_caches(self) -> None:
        """清空所有缓存."""
        self.indicator_cache.clear()
        self.screening_cache.clear()
        logger.info("🗑️ 缓存已清空")
    
    def cleanup(self) -> None:
        """清理资源."""
        self.clear_caches()
        self.query_history.clear()
        logger.info("🧹 会话资源已清理")
