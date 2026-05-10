"""范围加载器 - 负责批量加载日期范围数据."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

from utils.datetime_utils import DateAdjuster, generate_date_range
from datahub.core.query import Query

if TYPE_CHECKING:
    from datahub.core.dataset import DatasetMeta, FetchStep

logger = logging.getLogger(__name__)


class RangeLoader:
    """范围加载器 - 批量加载日期范围数据."""
    
    def __init__(self, cache_manager, pipeline_executor, calendar):
        """初始化.
        
        Args:
            cache_manager: 缓存管理器
            pipeline_executor: 管道执行器
            calendar: 交易日历
        """
        self.cache_manager = cache_manager
        self.pipeline_executor = pipeline_executor
        self.date_adjuster = DateAdjuster(calendar)
    
    def load_date_range(
        self,
        query: Query,
        meta: DatasetMeta,
        pipeline: list[FetchStep]
    ) -> pl.DataFrame:
        """加载日期范围数据.
        
        Args:
            query: 查询对象
            meta: 数据集元信息
            pipeline: 管道步骤
            
        Returns:
            合并后的DataFrame
        """
        # 调整查询日期为交易日
        query = self.date_adjuster.adjust_query_dates(query)
        
        # 获取交易日期列表
        trade_dates = self.date_adjuster.get_trade_dates(
            query.start_date,
            query.end_date
        )
        
        if not trade_dates:
            # 降级：使用原始日期范围
            trade_dates = generate_date_range(
                query.start_date,
                query.end_date
            )
        
        logger.debug(f"[DATE] 加载 {len(trade_dates)} 个日期的数据")
        
        # 尝试批量加载
        try:
            result = self._try_batch_load(query, meta, pipeline)
            if result is not None and not result.is_empty():
                logger.info(f"[OK] 批量加载成功: {len(result)} 条记录")
                return result
        except Exception as e:
            logger.warning(f"[WARN] 批量加载失败，回退到逐个日期加载: {e}")
        
        # 逐个日期加载
        return self._load_by_dates(trade_dates, query, meta, pipeline)
    
    def _try_batch_load(
        self,
        query: Query,
        meta: DatasetMeta,
        pipeline: list[FetchStep]
    ) -> pl.DataFrame | None:
        """尝试批量加载整个范围.
        
        Args:
            query: 查询对象
            meta: 数据集元信息
            pipeline: 管道步骤
            
        Returns:
            数据DataFrame或None
        """
        # 尝试从缓存加载整个范围
        range_query = Query(
            dataset=query.dataset,
            start_date=query.start_date,
            end_date=query.end_date,
            codes=query.codes,
            fields=query.fields,
            index_code=query.index_code,
        )
        
        try:
            return self.cache_manager.store.load(range_query)
        except Exception:
            return None
    
    def _load_by_dates(
        self,
        dates: list[str],
        query: Query,
        meta: DatasetMeta,
        pipeline: list[FetchStep]
    ) -> pl.DataFrame:
        """逐个日期加载数据.
        
        Args:
            dates: 日期列表
            query: 查询对象
            meta: 数据集元信息
            pipeline: 管道步骤
            
        Returns:
            合并后的DataFrame
        """
        all_data = []
        
        for date in dates:
            try:
                # 创建单日期查询
                single_query = Query(
                    dataset=query.dataset,
                    date=date,
                    codes=query.codes,
                    fields=query.fields,
                    index_code=query.index_code,
                )
                
                # 加载或获取数据
                data = self.cache_manager.load_or_fetch(
                    query=single_query,
                    meta=meta,
                    fetch_fn=lambda: self.pipeline_executor.execute(pipeline, single_query)
                )
                
                if data is not None and not data.is_empty():
                    all_data.append(data)
                    
            except Exception as e:
                logger.warning(f"[WARN] 加载日期 {date} 失败: {e}")
                continue
        
        if not all_data:
            raise ValueError(f"无法加载任何日期的数据: {query.start_date}~{query.end_date}")
        
        # 统一列结构后再合并
        result = self._unify_and_concat(all_data)
        logger.debug(f"[OK] 成功加载 {len(result)} 条记录（{len(all_data)}个日期）")
        
        return result
    
    def _unify_and_concat(self, dataframes: list[pl.DataFrame]) -> pl.DataFrame:
        """统一列结构后合并DataFrame.
        
        Args:
            dataframes: DataFrame列表
            
        Returns:
            合并后的DataFrame
        """
        if not dataframes:
            return pl.DataFrame()
        
        # 获取所有唯一的列名（保持第一个DataFrame的列顺序）
        all_columns = []
        seen_columns = set()
        
        for df in dataframes:
            for col in df.columns:
                if col not in seen_columns:
                    all_columns.append(col)
                    seen_columns.add(col)
        
        # 推断每列的数据类型（从第一个有该列且非空的DataFrame中获取）
        column_dtypes = {}
        for col in all_columns:
            for df in dataframes:
                if col in df.columns:
                    # 检查该列是否有非空值
                    non_null_count = df[col].null_count()
                    if non_null_count < len(df):
                        column_dtypes[col] = df[col].dtype
                        break
        
        # 统一每个DataFrame的列结构
        unified_dfs = []
        for df in dataframes:
            # 选择所有列，缺失的列用null填充
            missing_cols = [col for col in all_columns if col not in df.columns]
            
            if missing_cols:
                # 添加缺失的列（根据推断的类型填充null）
                null_columns = []
                for col in missing_cols:
                    dtype = column_dtypes.get(col)
                    if dtype is not None:
                        # 使用正确的数据类型创建null列
                        null_columns.append(pl.lit(None).cast(dtype).alias(col))
                    else:
                        # 如果无法推断类型，使用默认的Null类型
                        null_columns.append(pl.lit(None).alias(col))
                
                df = df.with_columns(null_columns)
            
            # 按统一顺序选择列
            df = df.select(all_columns)
            unified_dfs.append(df)
        
        # 合并
        return pl.concat(unified_dfs, how="vertical")
