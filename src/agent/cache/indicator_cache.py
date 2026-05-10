"""指标计算缓存层 - 避免重复计算技术指标."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Callable

import polars as pl

logger = logging.getLogger(__name__)


class IndicatorCache:
    """指标缓存管理器."""
    
    def __init__(self, max_size: int = 100):
        self.cache: dict[str, pl.DataFrame] = {}
        self.max_size = max_size
        self.access_order: list[str] = []  # LRU 追踪
    
    def get_or_compute(
        self,
        tool_name: str,
        params: dict[str, Any],
        compute_fn: Callable[[], pl.DataFrame]
    ) -> pl.DataFrame:
        """获取或计算指标."""
        cache_key = self._generate_key(tool_name, params)
        
        if cache_key in self.cache:
            logger.debug(f"♻️ 命中指标缓存: {tool_name}")
            self._touch(cache_key)
            return self.cache[cache_key]
        
        # 计算新指标
        logger.debug(f"⚙️ 计算新指标: {tool_name}")
        result = compute_fn()
        
        # 缓存结果
        self._put(cache_key, result)
        return result
    
    def _generate_key(self, tool_name: str, params: dict[str, Any]) -> str:
        """生成缓存键."""
        param_str = json.dumps(params, sort_keys=True, default=str)
        raw_key = f"{tool_name}:{param_str}"
        return hashlib.md5(raw_key.encode()).hexdigest()
    
    def _put(self, key: str, value: pl.DataFrame) -> None:
        """存入缓存（带 LRU 淘汰）."""
        if len(self.cache) >= self.max_size:
            oldest = self.access_order.pop(0)
            del self.cache[oldest]
            logger.debug(f"🗑️ 淘汰缓存: {oldest[:8]}...")
        
        self.cache[key] = value
        self.access_order.append(key)
    
    def _touch(self, key: str) -> None:
        """更新访问顺序（LRU）."""
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)
    
    def clear(self) -> None:
        """清空缓存."""
        self.cache.clear()
        self.access_order.clear()
    
    def stats(self) -> dict[str, int]:
        """获取缓存统计."""
        return {
            "size": len(self.cache),
            "max_size": self.max_size
        }
