"""筛选结果缓存层 - 缓存完整的筛选执行结果."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class ScreeningCache:
    """筛选结果缓存."""
    
    def __init__(self, max_size: int = 50):
        self.cache: dict[str, list[dict]] = {}
        self.max_size = max_size
    
    def get_or_execute(
        self,
        screening_logic: dict[str, Any],
        execute_fn: Callable[[], str | list[dict]]
    ) -> str | list[dict]:
        """获取或执行筛选."""
        cache_key = self._generate_key(screening_logic)
        
        if cache_key in self.cache:
            logger.info(f"♻️ 命中筛选结果缓存")
            return self.cache[cache_key]
        
        # 执行筛选
        logger.info(f"⚙️ 执行新筛选")
        results = execute_fn()
        
        # 缓存结果
        self._put(cache_key, results)
        return results
    
    def _generate_key(self, logic: dict[str, Any]) -> str:
        """生成筛选逻辑的哈希键."""
        # 只关注核心字段
        key_data = {
            "expression": logic.get("expression"),
            "tools": [
                {"tool": t["tool"], "params": t["params"]}
                for t in logic.get("tools", [])
            ]
        }
        logic_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.sha256(logic_str.encode()).hexdigest()[:16]
    
    def _put(self, key: str, results: str | list[dict]) -> None:
        """存入缓存."""
        if len(self.cache) >= self.max_size:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            logger.debug(f"🗑️ 淘汰筛选缓存")
        
        self.cache[key] = results
    
    def clear(self) -> None:
        """清空缓存."""
        self.cache.clear()
    
    def stats(self) -> dict[str, Any]:
        """获取缓存统计信息."""
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hit_rate": "N/A"  # TODO: 实现命中率统计
        }
