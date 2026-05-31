"""缓存管理器 - 负责数据的缓存加载、保存和质量检查."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

from datahub.core.exceptions import DataNotFoundError

if TYPE_CHECKING:
    from datahub.core.dataset import Dataset, DatasetMeta
    from datahub.core.query import Query
    from datahub.core.repository import Repository

logger = logging.getLogger(__name__)


class CacheManager:
    """缓存管理器 - 管理数据缓存的加载、保存和质量检查."""
    
    def __init__(self, store: Repository, auto_save: bool = True):
        """初始化.
        
        Args:
            store: 存储仓库
            auto_save: 是否自动保存缓存
        """
        self.store = store
        self.auto_save = auto_save
    
    def load_or_fetch(
        self,
        query: Query,
        meta: DatasetMeta,
        fetch_fn
    ) -> pl.DataFrame:
        """加载或获取数据（带缓存）.
        
        Args:
            query: 查询对象
            meta: 数据集元信息
            fetch_fn: 获取数据的函数
            
        Returns:
            数据 DataFrame
        """
        # 尝试从缓存加载
        try:
            result = self.store.load(query)
            index_info = f" (index={query.index_code})" if query.index_code else ""
            logger.debug("[OK] Cache HIT: %s/%s%s", query.dataset.value, query.date, index_info)
            return result
        except DataNotFoundError as e:
            index_info = f" (index={query.index_code})" if query.index_code else ""
            logger.debug("Cache MISS: %s/%s%s", query.dataset.value, query.date, index_info)
        
        # Cache MISS - 从数据源获取
        index_info = f" (index={query.index_code})" if query.index_code else ""
        logger.info(
            "[ERROR] Cache MISS: %s/%s%s, fetching from source",
            query.dataset.value,
            query.date,
            index_info,
        )
        
        data = fetch_fn()
        
        if data is None or data.is_empty():
            raise DataNotFoundError(
                f"No data for {query.dataset.value}/{query.date}."
            )
        
        # 数据质量检测
        self._check_and_warn_quality(data, query)
        
        # 自动保存缓存
        if self.auto_save:
            self._auto_save(query, meta, data)
        
        return data
    
    def _check_and_warn_quality(self, data: pl.DataFrame, query: Query):
        """检查数据质量并警告.
        
        Args:
            data: 数据 DataFrame
            query: 查询对象
        """
        nan_ratio = self._calculate_nan_ratio(data)
        
        if nan_ratio > 0.5:
            logger.error(
                "[ERROR] Data quality FAILED: %s/%s has %.1f%% NaN (threshold: 50%%). "
                "Data will NOT be saved.",
                query.dataset.value,
                query.date,
                nan_ratio * 100,
            )
            # 临时禁用自动保存
            self.auto_save = False
        elif nan_ratio > 0.1:
            logger.warning(
                "[WARN] Data quality WARNING: %s/%s has %.1f%% NaN. "
                "Data will be saved but please verify.",
                query.dataset.value,
                query.date,
                nan_ratio * 100,
            )
    
    def _calculate_nan_ratio(self, data: pl.DataFrame) -> float:
        """计算 NaN 比例.
        
        Args:
            data: 数据 DataFrame
            
        Returns:
            NaN 比例 (0-1)
        """
        if data.is_empty():
            return 0.0
        
        total_cells = data.height * data.width
        if total_cells == 0:
            return 0.0
        
        nan_count = sum(
            data.select(pl.col(col).is_null().sum()).item()
            for col in data.columns
        )
        
        return nan_count / total_cells
    
    def _auto_save(self, query: Query, meta: DatasetMeta, data: pl.DataFrame):
        """自动保存缓存.
        
        Args:
            query: 查询对象
            meta: 数据集元信息
            data: 数据 DataFrame
        """
        partition_key = self._resolve_partition_key(query, meta)
        index_info = f" (index={query.index_code})" if query.index_code else ""
        logger.info("💾 Auto-saving cache: %s/%s%s", query.dataset.value, query.date, index_info)
        
        success = self._safe_save(query.dataset, data, partition_key)
        if success:
            index_info = f" (index={query.index_code})" if query.index_code else ""
            logger.info("[OK] Cache saved: %s/%s%s", query.dataset.value, query.date, index_info)
        else:
            index_info = f" (index={query.index_code})" if query.index_code else ""
            logger.warning("[WARN] Cache save failed: %s/%s%s", query.dataset.value, query.date, index_info)
    
    def _resolve_partition_key(self, query: Query, meta: DatasetMeta) -> str:
        """解析分区键.
        
        Args:
            query: 查询对象
            meta: 数据集元信息
            
        Returns:
            分区键字符串
        """
        # 统一使用 partition_key_template 生成分区键
        index_code_safe = ""
        if query.index_code:
            index_code_safe = query.index_code.replace(".", "_")
        
        return meta.partition_key_template.format(
            datetime=query.date or "",
            date=query.date or "",
            index_code=index_code_safe,
        )
    
    def _safe_save(self, dataset: Dataset, data: pl.DataFrame, partition_key: str) -> bool:
        """安全保存（捕获异常）.
        
        Args:
            dataset: 数据集
            data: 数据 DataFrame
            partition_key: 分区键
            
        Returns:
            是否成功
        """
        try:
            return self.store.save(dataset, data, partition_key)
        except Exception as e:
            logger.error("[ERROR] Cache save error: %s", e, exc_info=True)
            return False
