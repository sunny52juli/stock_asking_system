"""同步仓库 - 负责数据同步和缓存管理."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

from datahub.core.dataset import DatasetRegistry
from datahub.core.exceptions import DataNotFoundError
from datahub.sync.cache_manager import CacheManager
from datahub.sync.pipeline_executor import PipelineExecutor
from datahub.sync.range_loader import RangeLoader
from datahub.domain.calendar import Calendar

if TYPE_CHECKING:
    from datahub.core.query import Query
    from datahub.core.repository import Repository
    from datahub.core.source import DataSource

logger = logging.getLogger(__name__)


class SyncRepository:
    """同步仓库 - 委托给服务类执行实际逻辑."""
    
    def __init__(
        self,
        store: Repository,
        source: DataSource,
        auto_save: bool = True,
    ):
        """初始化.
        
        Args:
            store: 存储仓库
            source: 数据源
            auto_save: 是否自动保存
        """
        self.store = store
        self.source = source
        
        # 初始化服务类
        self.cache_manager = CacheManager(store, auto_save)
        self.pipeline_executor = PipelineExecutor(source)
        
        calendar = Calendar()
        self.range_loader = RangeLoader(
            self.cache_manager,
            self.pipeline_executor,
            calendar
        )
    
    def load(self, query: Query) -> pl.DataFrame:
        """加载数据.
        
        Args:
            query: 查询对象
            
        Returns:
            数据DataFrame
        """
        meta, pipeline = DatasetRegistry.get(query.dataset)
        
        if not query.is_range:
            return self._load_single(query, meta, pipeline)
        
        if meta.partition_by == "date":
            return self.range_loader.load_date_range(query, meta, pipeline)
        
        return self._fetch_range_direct(query, meta, pipeline)
    
    def save(self, dataset, data: pl.DataFrame, partition_key: str) -> bool:
        """保存数据.
        
        Args:
            dataset: 数据集
            data: 数据DataFrame
            partition_key: 分区键
            
        Returns:
            是否成功
        """
        return self.store.save(dataset, data, partition_key)
    
    def exists(self, dataset, partition_key: str) -> bool:
        """检查数据是否存在.
        
        Args:
            dataset: 数据集
            partition_key: 分区键
            
        Returns:
            是否存在
        """
        return self.store.exists(dataset, partition_key)
    
    def available_dates(self, dataset) -> list[str]:
        """获取可用日期列表.
        
        Args:
            dataset: 数据集
            
        Returns:
            日期列表
        """
        return self.store.available_dates(dataset)
    
    def latest_date(self, dataset) -> str | None:
        """获取最新日期.
        
        Args:
            dataset: 数据集
            
        Returns:
            最新日期或None
        """
        return self.store.latest_date(dataset)
    
    def _load_single(self, query: Query, meta, pipeline: list) -> pl.DataFrame:
        """加载单个日期数据.
        
        Args:
            query: 查询对象
            meta: 数据集元信息
            pipeline: 管道步骤
            
        Returns:
            数据DataFrame
        """
        return self.cache_manager.load_or_fetch(
            query=query,
            meta=meta,
            fetch_fn=lambda: self.pipeline_executor.execute(pipeline, query)
        )
    
    def _fetch_range_direct(self, query: Query, meta, pipeline: list) -> pl.DataFrame:
        """直接获取范围数据（非日期分区）.
        
        Args:
            query: 查询对象
            meta: 数据集元信息
            pipeline: 管道步骤
            
        Returns:
            数据DataFrame
        """
        # TODO: 实现直接范围获取
        raise NotImplementedError("直接范围获取待实现")
