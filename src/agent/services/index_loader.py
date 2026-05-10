"""指数数据加载器 - 统一的指数数据加载和合并服务."""

from __future__ import annotations

from typing import Optional
import polars as pl

from infrastructure.logging.logger import get_logger

from datahub.core.dataset import Dataset
from datahub.core.query import Query
from datahub.factory import Factory
from datahub.domain.index_selector import get_index_code
import traceback
logger = get_logger(__name__)


class IndexDataLoader:
    """指数数据加载器.
    
    职责：
    1. 根据股票代码自动选择基准指数
    2. 加载指数历史数据
    3. 将指数数据合并到股票数据中
    
    使用示例：
        loader = IndexDataLoader()
        data_with_index = loader.load_and_merge(stock_data, stock_codes)
    """
    
    def __init__(self):
        self._cache: dict[str, pl.DataFrame] = {}
    
    def load_and_merge(
        self,
        stock_data: pl.DataFrame,
        stock_codes: Optional[list[str]] = None,
        primary_index: Optional[str] = None,
    ) -> pl.DataFrame:
        """加载指数数据并合并到股票数据中.
        
        Args:
            stock_data: 股票数据 DataFrame (MultiIndex: ts_code, trade_date)
            stock_codes: 股票代码列表（可选，用于确定指数）
            primary_index: 指定主指数代码（可选，否则自动选择）
            
        Returns:
            添加了 index_close 列的 DataFrame
        """
        try:
            # 步骤1：确定需要使用的指数列表
            if primary_index:
                index_codes = [primary_index]
            else:
                index_codes = self._select_all_indices(stock_data, stock_codes)
            
            if not index_codes:
                logger.warning("[WARN] 无法确定指数，跳过指数数据加载")
                return stock_data
            
            # 步骤2：获取日期范围
            date_range = self._extract_date_range(stock_data)
            if date_range is None:
                return stock_data
            
            start_date, end_date = date_range
            
            # 步骤3：加载所有指数数据（带缓存）
            all_index_data = []
            for idx_code in index_codes:
                index_data = self._load_index_data(idx_code, start_date, end_date)
                if not index_data.is_empty() and 'index_close' in index_data.columns:
                    all_index_data.append(index_data)
            
            if not all_index_data:
                logger.warning(f"[WARN] 所有指数数据为空，返回原始股票数据")
                return stock_data
            
            # 合并所有指数数据
            combined_index_data = pl.concat(all_index_data)
            
            logger.info(f"[OK] 成功加载 {len(index_codes)} 个指数数据，共 {len(combined_index_data)} 条记录")
            
            # 将指数数据合并到股票数据中
            result = self._merge_index_data(stock_data, combined_index_data)
            
            return result
            
        except Exception as e:
            logger.warning(f"[WARN] 加载指数数据失败: {e}")
            logger.debug(traceback.format_exc())
            # 返回原始股票数据，而不是空 DataFrame
            return stock_data
    
    def _select_primary_index(
        self,
        stock_data: pl.DataFrame,
        stock_codes: Optional[list[str]] = None,
    ) -> Optional[str]:
        """根据股票代码选择主要指数.
        
        Args:
            stock_data: 股票数据
            stock_codes: 股票代码列表
            
        Returns:
            指数代码（如 '000300.SH'）
        """
        
        # 确定需要分析的股票
        if stock_codes:
            codes_to_process = stock_codes[:10]
        else:
            if "ts_code" in stock_data.columns:
                codes_to_process = stock_data.select(pl.col("ts_code").unique()).to_series().to_list()[:10]
            else:
                return None
        
        if not codes_to_process:
            return None
        
        # 统计各指数的出现次数
        index_counts: dict[str, int] = {}
        for code in codes_to_process:
            idx_code = get_index_code(code)
            index_counts[idx_code] = index_counts.get(idx_code, 0) + 1
        
        # 选择出现次数最多的指数
        primary_index = max(index_counts, key=index_counts.get)
        logger.info(f"[DATA] 主要使用指数: {primary_index} ({index_counts[primary_index]}/{len(codes_to_process)} 只股票)")
        
        return primary_index
    
    def _select_all_indices(
        self,
        stock_data: pl.DataFrame,
        stock_codes: Optional[list[str]] = None,
    ) -> list[str]:
        """根据股票代码选择所有相关指数.
        
        Args:
            stock_data: 股票数据
            stock_codes: 股票代码列表
            
        Returns:
            指数代码列表
        """
        
        # 确定需要分析的股票
        if stock_codes:
            codes_to_process = stock_codes
        else:
            if "ts_code" in stock_data.columns:
                codes_to_process = stock_data.select(pl.col("ts_code").unique()).to_series().to_list()
            else:
                return []
        
        if not codes_to_process:
            return []
        
        # 收集所有唯一的指数代码
        unique_indices: set[str] = set()
        for code in codes_to_process:
            idx_code = get_index_code(code)
            unique_indices.add(idx_code)
        
        indices_list = sorted(list(unique_indices))
        logger.info(f"[DATA] 检测到 {len(indices_list)} 个指数: {', '.join(indices_list)}")
        
        return indices_list
    
    def _extract_date_range(self, stock_data: pl.DataFrame) -> Optional[tuple[str, str]]:
        """从股票数据中提取日期范围.
        
        Returns:
            (start_date, end_date) 格式为 'YYYYMMDD'
        """
        # Polars DataFrame
        dates_pl = stock_data.select(pl.col("trade_date").unique()).to_series()
        if len(dates_pl) == 0:
            return None
        # Polars: min/max 可能返回 datetime.date 或其他类型，需要转换
        min_date = dates_pl.min()
        max_date = dates_pl.max()
        # 转换为字符串格式 YYYYMMDD
        if hasattr(min_date, 'strftime'):
            start_date = min_date.strftime('%Y%m%d')
            end_date = max_date.strftime('%Y%m%d')
        else:
            # 如果已经是字符串或整数，直接转换
            start_date = str(min_date).replace('-', '')[:8]
            end_date = str(max_date).replace('-', '')[:8]
        
        return (start_date, end_date)
    
    def _load_index_data(
        self,
        index_code: str,
        start_date: str,
        end_date: str,
    ) -> pl.DataFrame:
        """加载指数数据（带缓存）.
        
        Args:
            index_code: 指数代码
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            
        Returns:
            指数数据 DataFrame (index: trade_date, columns: ['index_close'])
        """
        # 检查缓存
        cache_key = f"{index_code}_{start_date}_{end_date}"
        if cache_key in self._cache:
            logger.debug(f"📦 使用缓存的指数数据: {cache_key}")
            return self._cache[cache_key]
        
        # 加载数据
        try:
            from datahub import Index
            index = Index()
            index_data = index.level(
                index_code=index_code,
                start_date=start_date,
                end_date=end_date,
                freq="daily",
            )
        except Exception as e:
            logger.debug(f"加载指数 {index_code} 数据失败: {e}")
            return pl.DataFrame()
        
        # 检查是否为空
        if index_data.is_empty() or 'close' not in index_data.columns:
            return pl.DataFrame()
        
        # 处理数据格式（保持 polars）
        index_data = index_data.rename({"close": "index_close"})
        
        # 添加 index_code 列
        if "index_code" not in index_data.columns:
            index_data = index_data.with_columns(pl.lit(index_code).alias("index_code"))
        
        # 确保 trade_date 是日期类型
        if "trade_date" in index_data.columns:
            # polars 中 trade_date 可能已经是 date/datetime 类型，无需转换
            pass
        
        # 缓存结果（保持 polars 格式）
        self._cache[cache_key] = index_data
        
        return index_data
    
    def _merge_index_data(
        self,
        stock_data: pl.DataFrame,
        index_data: pl.DataFrame,
    ) -> pl.DataFrame:
        """将指数数据合并到股票数据中.
        
        Args:
            stock_data: 股票数据 (polars 或 pandas)
            index_data: 指数数据
            
        Returns:
            合并后的 DataFrame
        """
        # 如果指数数据为空，直接返回原始数据
        if index_data.is_empty():
            logger.warning("[WARN] 指数数据为空，跳过合并")
            return stock_data
        
        try:
            # Polars: join on trade_date
            result_data = stock_data.join(
                index_data.select(["trade_date", "index_close"]),
                on="trade_date",
                how="left"
            )
            
            return result_data
        except Exception as e:
            logger.warning(f"[WARN] 合并指数数据失败：{e}，返回原始数据")
            return stock_data
    
    def clear_cache(self):
        """清除缓存."""
        self._cache.clear()
        logger.info("🗑️ 指数数据缓存已清除")


# 全局单例
_global_loader: Optional[IndexDataLoader] = None


def get_index_loader() -> IndexDataLoader:
    """获取全局指数数据加载器单例."""
    global _global_loader
    if _global_loader is None:
        _global_loader = IndexDataLoader()
    return _global_loader


def load_and_merge_index_data(
    stock_data: pl.DataFrame,
    stock_codes: Optional[list[str]] = None,
    primary_index: Optional[str] = None,
) -> pl.DataFrame:
    """便捷函数：加载并合并指数数据.
    
    Args:
        stock_data: 股票数据
        stock_codes: 股票代码列表
        primary_index: 指定主指数
        
    Returns:
        添加了 index_close 列的 DataFrame
    """
    loader = get_index_loader()
    return loader.load_and_merge(stock_data, stock_codes, primary_index)
