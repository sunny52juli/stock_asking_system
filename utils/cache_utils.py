"""高性能缓存层 - LRU + TTL 缓存.

提供：
- 内存缓存 (LRU + TTL)
- 磁盘缓存 (持久化)
- 多级缓存策略
- 自动过期清理
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CacheEntry:
    """缓存条目."""
    
    key: str
    value: Any
    created_at: float
    ttl: float | None = None  # Time To Live (seconds)
    access_count: int = 0
    
    def is_expired(self) -> bool:
        """检查是否过期."""
        if self.ttl is None:
            return False
        return time.time() > (self.created_at + self.ttl)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at,
            "ttl": self.ttl,
            "access_count": self.access_count,
        }


class LRUCache:
    """LRU (Least Recently Used) 缓存.
    
    特性：
    - 固定容量
    - 自动淘汰最少使用的条目
    - 支持 TTL
    - 线程安全
    
    使用示例::
    
        cache = LRUCache(max_size=1000, default_ttl=3600)
        
        # 设置缓存
        cache.set("key", value)
        
        # 获取缓存
        value = cache.get("key")
        
        # 带默认值的获取
        value = cache.get_or_set("key", lambda: expensive_computation())
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: float | None = None):
        """初始化缓存.
        
        Args:
            max_size: 最大缓存条目数
            default_ttl: 默认 TTL (秒)，None 表示永不过期
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Any | None:
        """获取缓存值.
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值或 None（未命中或已过期）
        """
        if key not in self._cache:
            self._misses += 1
            return None
        
        entry = self._cache[key]
        
        # 检查是否过期
        if entry.is_expired():
            self._cache.pop(key)
            self._misses += 1
            logger.debug(f"🗑️  缓存过期: {key}")
            return None
        
        # 移动到末尾（最近使用）
        self._cache.move_to_end(key)
        entry.access_count += 1
        self._hits += 1
        
        return entry.value
    
    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """设置缓存值.
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 可选的 TTL，覆盖默认值
        """
        if key in self._cache:
            # 更新现有条目
            self._cache.move_to_end(key)
            self._cache[key].value = value
            self._cache[key].created_at = time.time()
            if ttl is not None:
                self._cache[key].ttl = ttl
        else:
            # 添加新条目
            if len(self._cache) >= self.max_size:
                # 淘汰最旧的条目
                oldest_key, oldest_entry = self._cache.popitem(last=False)
                logger.debug(f"🗑️  缓存淘汰: {oldest_key} (access_count={oldest_entry.access_count})")
            
            self._cache[key] = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                ttl=ttl if ttl is not None else self.default_ttl,
            )
    
    def get_or_set(self, key: str, factory: Callable[[], Any], ttl: float | None = None) -> Any:
        """获取或设置缓存值.
        
        Args:
            key: 缓存键
            factory: 值工厂函数（仅在未命中时调用）
            ttl: 可选的 TTL
            
        Returns:
            缓存值
        """
        value = self.get(key)
        
        if value is not None:
            return value
        
        # 未命中，计算并缓存
        value = factory()
        self.set(key, value, ttl)
        
        return value
    
    def delete(self, key: str) -> bool:
        """删除缓存条目.
        
        Args:
            key: 缓存键
            
        Returns:
            True 如果删除成功
        """
        if key in self._cache:
            self._cache.pop(key)
            return True
        return False
    
    def clear(self) -> None:
        """清空缓存."""
        self._cache.clear()
        logger.info("🗑️  缓存已清空")
    
    def cleanup_expired(self) -> int:
        """清理过期的缓存条目.
        
        Returns:
            清理的条目数
        """
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        
        for key in expired_keys:
            self._cache.pop(key)
        
        if expired_keys:
            logger.debug(f"🗑️  清理了 {len(expired_keys)} 个过期条目")
        
        return len(expired_keys)
    
    def stats(self) -> dict[str, Any]:
        """获取缓存统计信息."""
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2f}%",
            "default_ttl": self.default_ttl,
        }
    
    def keys(self) -> list[str]:
        """获取所有缓存键."""
        return list(self._cache.keys())


class DiskCache:
    """磁盘缓存 - 持久化存储.
    
    特性：
    - 基于文件的持久化
    - 自动序列化/反序列化
    - 支持大对象缓存
    - 定期清理
    
    使用示例::
    
        cache = DiskCache(cache_dir=".cache/data")
        cache.set("large_dataset", data)
        data = cache.get("large_dataset")
    """
    
    def __init__(self, cache_dir: str | Path = ".cache", default_ttl: float | None = None):
        """初始化磁盘缓存.
        
        Args:
            cache_dir: 缓存目录
            default_ttl: 默认 TTL (秒)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl
        self._metadata: dict[str, dict[str, Any]] = {}
        
        # 加载元数据
        self._load_metadata()
    
    def get(self, key: str) -> Any | None:
        """获取缓存值."""
        if key not in self._metadata:
            return None
        
        meta = self._metadata[key]
        
        # 检查过期
        if meta.get('ttl') and time.time() > (meta['created_at'] + meta['ttl']):
            self._delete_file(key)
            return None
        
        # 读取文件
        cache_file = self._get_cache_file(key)
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"⚠️  读取缓存失败 {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """设置缓存值."""
        cache_file = self._get_cache_file(key)
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(value, f, ensure_ascii=False, default=str)
            
            # 更新元数据
            self._metadata[key] = {
                'created_at': time.time(),
                'ttl': ttl if ttl is not None else self.default_ttl,
                'file': str(cache_file),
            }
            
            self._save_metadata()
            
        except Exception as e:
            logger.error(f"❌ 写入缓存失败 {key}: {e}")
    
    def delete(self, key: str) -> bool:
        """删除缓存条目."""
        if key in self._metadata:
            self._delete_file(key)
            return True
        return False
    
    def clear(self) -> None:
        """清空缓存."""
        for key in list(self._metadata.keys()):
            self._delete_file(key)
        
        self._metadata.clear()
        self._save_metadata()
        logger.info("🗑️  磁盘缓存已清空")
    
    def cleanup_expired(self) -> int:
        """清理过期条目."""
        expired_keys = [
            key for key, meta in self._metadata.items()
            if meta.get('ttl') and time.time() > (meta['created_at'] + meta['ttl'])
        ]
        
        for key in expired_keys:
            self._delete_file(key)
        
        if expired_keys:
            logger.debug(f"🗑️  清理了 {len(expired_keys)} 个过期条目")
        
        return len(expired_keys)
    
    def _get_cache_file(self, key: str) -> Path:
        """获取缓存文件路径."""
        # 使用 hash 避免文件名冲突
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.json"
    
    def _delete_file(self, key: str) -> None:
        """删除缓存文件和元数据."""
        if key in self._metadata:
            cache_file = Path(self._metadata[key]['file'])
            if cache_file.exists():
                cache_file.unlink()
            del self._metadata[key]
            self._save_metadata()
    
    def _load_metadata(self) -> None:
        """加载元数据."""
        metadata_file = self.cache_dir / "metadata.json"
        
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    self._metadata = json.load(f)
            except Exception as e:
                logger.warning(f"⚠️  加载元数据失败: {e}")
                self._metadata = {}
    
    def _save_metadata(self) -> None:
        """保存元数据."""
        metadata_file = self.cache_dir / "metadata.json"
        
        try:
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self._metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ 保存元数据失败: {e}")


class MultiLevelCache:
    """多级缓存 - L1 (内存) + L2 (磁盘).
    
    策略：
    - L1: 快速访问，容量小
    - L2: 持久化，容量大
    - 自动降级和升级
    """
    
    def __init__(
        self,
        l1_max_size: int = 1000,
        l1_ttl: float | None = 300,
        l2_cache_dir: str | Path = ".cache",
        l2_ttl: float | None = 3600,
    ):
        """初始化多级缓存.
        
        Args:
            l1_max_size: L1 缓存大小
            l1_ttl: L1 TTL (秒)
            l2_cache_dir: L2 缓存目录
            l2_ttl: L2 TTL (秒)
        """
        self.l1 = LRUCache(max_size=l1_max_size, default_ttl=l1_ttl)
        self.l2 = DiskCache(cache_dir=l2_cache_dir, default_ttl=l2_ttl)
    
    def get(self, key: str) -> Any | None:
        """获取缓存值（L1 → L2）."""
        # 尝试 L1
        value = self.l1.get(key)
        if value is not None:
            return value
        
        # 尝试 L2
        value = self.l2.get(key)
        if value is not None:
            # 升级到 L1
            self.l1.set(key, value)
            return value
        
        return None
    
    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """设置缓存值（同时写入 L1 和 L2）."""
        self.l1.set(key, value, ttl)
        self.l2.set(key, value, ttl)
    
    def delete(self, key: str) -> None:
        """删除缓存值."""
        self.l1.delete(key)
        self.l2.delete(key)
    
    def clear(self) -> None:
        """清空所有缓存."""
        self.l1.clear()
        self.l2.clear()
    
    def stats(self) -> dict[str, Any]:
        """获取缓存统计."""
        return {
            "l1": self.l1.stats(),
            "l2": "DiskCache (persistent)",
        }


# 全局缓存实例
_query_cache: MultiLevelCache | None = None
_data_cache: MultiLevelCache | None = None


def get_query_cache() -> MultiLevelCache:
    """获取查询结果缓存."""
    global _query_cache
    if _query_cache is None:
        _query_cache = MultiLevelCache(
            l1_max_size=500,
            l1_ttl=300,  # 5分钟
            l2_cache_dir=".cache/queries",
            l2_ttl=3600,  # 1小时
        )
    return _query_cache


def get_data_cache() -> MultiLevelCache:
    """获取数据缓存."""
    global _data_cache
    if _data_cache is None:
        _data_cache = MultiLevelCache(
            l1_max_size=100,
            l1_ttl=600,  # 10分钟
            l2_cache_dir=".cache/data",
            l2_ttl=86400,  # 24小时
        )
    return _data_cache


def reset_caches():
    """重置所有缓存（用于测试）."""
    global _query_cache, _data_cache
    _query_cache = None
    _data_cache = None
