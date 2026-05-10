"""缓存模块."""

from utils.cache_utils import (
    LRUCache,
    DiskCache,
    MultiLevelCache,
    get_query_cache,
    get_data_cache,
)

__all__ = [
    "LRUCache",
    "DiskCache",
    "MultiLevelCache",
    "get_query_cache",
    "get_data_cache",
]
