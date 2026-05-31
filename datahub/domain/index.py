"""Index domain: members, optional index daily. Implements IndexProtocol."""

from __future__ import annotations

import logging
import polars as pl


from datahub.core.dataset import Dataset
from datahub.core.query import Query
from datahub.core.repository import Repository
from datahub.domain._helpers import load_with_date_or_range

logger = logging.getLogger(__name__)


class Index:
    """Index domain implementation: constituents, weights, level, valuation. Contract: protocols.index.IndexProtocol."""

    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def members(
        self,
        index_code: str,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> "pd.DataFrame":
        """获取指数成分股列表。
        
        注意：此功能已简化，如需获取指数成分股，建议直接使用 Tushare API。
        """
        logger.warning("[WARN] Index.members() 已弃用，建议使用其他方式获取指数成分股")
        return pl.DataFrame()

    def available_dates(self, index_code: str | None = None) -> list[str]:
        """获取可用日期列表（已简化，返回空列表）。"""
        return []

    def latest_date(self, index_code: str | None = None) -> str | None:
        """获取最新日期（已简化，返回None）。"""
        return None

    def level(
        self,
        index_code: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        freq: str = "daily",
    ) -> "pl.DataFrame":
        """加载指数日线数据。
        
        Args:
            index_code: 指数代码（可选），如果为 None 则返回所有指数
            start_date: 起始日期
            end_date: 结束日期
            freq: 频率
            
        Returns:
            指数数据 DataFrame
        """
        query_params = {
            "dataset": Dataset.INDEX_DAILY,
            "start_date": start_date,
            "end_date": end_date,
        }
        
        # 如果指定了指数代码，添加过滤条件
        if index_code:
            query_params["index_code"] = index_code
        
        result = self._repo.load(Query(**query_params))
        
        # 去重：确保 (index_code 或 ts_code, trade_date) 唯一
        if not result.is_empty() and 'trade_date' in result.columns:
            # 确定用于分组的列
            group_col = 'index_code' if 'index_code' in result.columns else ('ts_code' if 'ts_code' in result.columns else None)
            if group_col:
                before_count = len(result)
                result = result.unique(subset=[group_col, 'trade_date'], keep='first')
                after_count = len(result)
                if before_count != after_count:
                    logger.debug(f"   [OK] level 函数去除 {before_count - after_count} 条重复记录")
            else:
                # 如果没有 index_code 或 ts_code，只按 trade_date 去重
                before_count = len(result)
                result = result.unique(subset=['trade_date'], keep='first')
                after_count = len(result)
                if before_count != after_count:
                    logger.debug(f"   [OK] level 函数去除 {before_count - after_count} 条重复记录")
        
        return result

    def batch_level(
        self,
        index_codes: list[str],
        start_date: str,
        end_date: str,
        freq: str = "daily",
    ) -> "pl.DataFrame":
        """批量加载多个指数的日线数据。
        
        由于 Tushare API 要求每次调用必须指定 ts_code，因此采用逐个加载并合并的策略。
        但会在缓存层面优化：按天分区存储，每天的所有指数数据保存在一个文件中。
        
        Args:
            index_codes: 指数代码列表
            start_date: 起始日期
            end_date: 结束日期
            freq: 频率
            
        Returns:
            合并后的指数数据 DataFrame (包含 index_code 列)
        """
        if not index_codes:
            return pl.DataFrame()
        
        from concurrent.futures import ThreadPoolExecutor
        
        logger.info(f"[SEARCH] 批量加载 {len(index_codes)} 个指数数据...")
        
        # 定义单个指数加载函数
        def load_single_index(idx_code: str) -> tuple[str, pl.DataFrame | None]:
            try:
                df = self.level(
                    index_code=idx_code,
                    start_date=start_date,
                    end_date=end_date,
                    freq=freq,
                )
                if df.is_empty():
                    return (idx_code, None)
                
                # 添加 index_code 列
                if 'ts_code' in df.columns:
                    df = df.rename({'ts_code': 'index_code'})
                else:
                    df = df.with_columns(pl.lit(idx_code).alias('index_code'))
                
                return (idx_code, df)
            except Exception as e:
                logger.error(f"   [ERROR] {idx_code}: {e}")
                return (idx_code, None)
        
        # 使用 map 并行加载
        max_workers = len(index_codes)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(load_single_index, index_codes))
        
        # 分离成功和失败的结果
        dfs = []
        failed_indices = []
        for idx_code, df in results:
            if df is not None:
                # 统一列顺序，确保所有 DataFrame 有相同的列
                standard_columns = ['index_code', 'trade_date', 'open', 'high', 'low', 'close', 'vol', 'amount']
                available_cols = [col for col in standard_columns if col in df.columns]
                if available_cols:
                    dfs.append(df.select(available_cols))
                else:
                    failed_indices.append(idx_code)
            else:
                failed_indices.append(idx_code)
        
        if not dfs:
            logger.warning("[WARN] 所有指数数据加载失败")
            return pl.DataFrame()
        
        # 合并所有指数的数据
        combined = pl.concat(dfs)
        
        # 去重：确保 (index_code, trade_date) 唯一，保留第一条记录
        if 'index_code' in combined.columns and 'trade_date' in combined.columns:
            before_count = len(combined)
            combined = combined.unique(subset=['index_code', 'trade_date'], keep='first')
            after_count = len(combined)
            if before_count != after_count:
                logger.info(f"   [OK] 去除重复数据: {before_count - after_count} 条重复记录")
        
        logger.info(f"[OK] 批量加载完成: {len(index_codes) - len(failed_indices)}/{len(index_codes)} 个指数, 共 {len(combined)} 条记录")
        
        if failed_indices:
            logger.warning(f"[WARN] 以下指数加载失败: {', '.join(failed_indices)}")
        
        return combined

    def returns(
        self,
        index_code: str,
        start_date: str,
        end_date: str,
        freq: str = "daily",
        include_dividends: bool = True,
    ) -> "pl.DataFrame":
        df_pl = self.level(index_code=index_code, start_date=start_date, end_date=end_date, freq=freq)
        if df_pl.is_empty() or "close" not in df_pl.columns:
            return df_pl
        
        # 去重：确保 trade_date 唯一
        date_col = next((c for c in ["trade_date"] if c in df_pl.columns), df_pl.columns[0])
        before_count = len(df_pl)
        df_pl = df_pl.unique(subset=[date_col], keep='first')
        after_count = len(df_pl)
        if before_count != after_count:
            logger.info(f"   [OK] returns 函数去除 {before_count - after_count} 条重复记录")
        
        df_pl = df_pl.sort(date_col)
        df_pl = df_pl.with_columns(
            (pl.col("close") / pl.col("close").shift(1) - 1).alias("return")
        )
        result_cols = [date_col, "ts_code", "return"]
        available_cols = [c for c in result_cols if c in df_pl.columns]
        return df_pl.select(available_cols).drop_nulls()

    def valuation(
        self,
        index_code: str,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> "pd.DataFrame":
        return load_with_date_or_range(
            self._repo,
            Dataset.INDEX_VALUATION,
            date=date,
            start_date=start_date,
            end_date=end_date,
            index_code=index_code,
        )

    def weights(
        self,
        index_code: str,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        codes: list[str] | None = None,
    ) -> "pd.DataFrame":
        """获取指数成分股权重（已简化）。
        
        注意：此功能已弃用，如需权重数据，建议直接使用 Tushare API。
        """
        logger.warning("[WARN] Index.weights() 已弃用")
        return pl.DataFrame()

    def rebalance_history(
        self,
        index_code: str,
        start_date: str,
        end_date: str,
    ) -> "pl.DataFrame":
        """获取指数调仓历史（已简化）。
        
        注意：此功能已弃用。
        """
        logger.warning("[WARN] Index.rebalance_history() 已弃用")
        return pl.DataFrame()

    def sector_breakdown(
        self,
        index_code: str,
        date: str,
        level: int = 1,
    ) -> "pl.DataFrame":
        """获取指数行业分布（已简化）。
        
        注意：此功能已弃用。
        """
        logger.warning("[WARN] Index.sector_breakdown() 已弃用")
        return pl.DataFrame()

    def catalog(self, family: str | None = None) -> "pl.DataFrame":
        query = Query(
            dataset=Dataset.INDEX_BASIC,
            start_date="19900101",
            end_date="20991231",
        )
        df_pl = self._repo.load(query)
        if family and "market" in df_pl.columns:
            df_pl = df_pl.filter(pl.col("market").str.contains(family))
        return df_pl.with_row_index().drop("index")


