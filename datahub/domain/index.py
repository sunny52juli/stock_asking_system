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
        return load_with_date_or_range(
            self._repo,
            Dataset.STOCK_INDEX_WEIGHT,
            date=date,
            start_date=start_date,
            end_date=end_date,
            index_code=index_code,
        )

    def available_dates(self, index_code: str | None = None) -> list[str]:
        return self._repo.available_dates(Dataset.STOCK_INDEX_WEIGHT)

    def latest_date(self, index_code: str | None = None) -> str | None:
        return self._repo.latest_date(Dataset.STOCK_INDEX_WEIGHT)

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
        
        return self._repo.load(Query(**query_params))

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
        date_col = next((c for c in ["trade_date"] if c in df_pl.columns), df_pl.columns[0])
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
        return load_with_date_or_range(
            self._repo,
            Dataset.STOCK_INDEX_WEIGHT,
            date=date,
            start_date=start_date,
            end_date=end_date,
            index_code=index_code,
            codes=codes,
        )

    def rebalance_history(
        self,
        index_code: str,
        start_date: str,
        end_date: str,
    ) -> "pl.DataFrame":
        df = self.weights(index_code=index_code, start_date=start_date, end_date=end_date)
        if df.is_empty():
            return pl.DataFrame()
        date_col = next((c for c in ["trade_date", "end_date"] if c in df.columns), None)
        code_col = next((c for c in ["con_code", "ts_code"] if c in df.columns), None)
        if date_col is None or code_col is None:
            return pl.DataFrame()
        dates = sorted(df[date_col].unique().to_list())
        rebalances = []
        for i in range(1, len(dates)):
            prev_codes = set(df.filter(pl.col(date_col) == dates[i-1])[code_col].to_list())
            curr_codes = set(df.filter(pl.col(date_col) == dates[i])[code_col].to_list())
            added = curr_codes - prev_codes
            removed = prev_codes - curr_codes
            if added or removed:
                rebalances.append(
                    {
                        "date": dates[i],
                        "added": list(added),
                        "removed": list(removed),
                        "added_count": len(added),
                        "removed_count": len(removed),
                    }
                )
        return pl.DataFrame(rebalances)

    def sector_breakdown(
        self,
        index_code: str,
        date: str,
        level: int = 1,
    ) -> "pl.DataFrame":
        weights_pl = self.weights(index_code=index_code, date=date)
        if weights_pl.is_empty():
            return pl.DataFrame()
        code_col = next((c for c in ["con_code", "ts_code"] if c in weights_pl.columns), None)
        weight_col = next((c for c in ["weight"] if c in weights_pl.columns), None)
        if code_col is None:
            return weights_pl
        try:
            basic_q = Query(
                dataset=Dataset.STOCK_BASIC,
                start_date="19900101",
                end_date="20991231",
                codes=weights_pl[code_col].to_list(),
            )
            basic_pl = self._repo.load(basic_q)
            industry_col = "industry"
            if industry_col in basic_pl.columns and "ts_code" in basic_pl.columns:
                merged = weights_pl.join(
                    basic_pl.select(["ts_code", industry_col]),
                    left_on=code_col,
                    right_on="ts_code",
                    how="left",
                    suffix="_dup"
                )
                # 移除带 _dup 后缀的列
                dup_cols = [col for col in merged.columns if col.endswith("_dup")]
                if dup_cols:
                    merged = merged.drop(dup_cols)
                if weight_col:
                    return (
                        merged.group_by(industry_col)
                        .agg(pl.col(weight_col).sum())
                        .sort(weight_col, descending=True)
                    )
        except Exception:
            return weights_pl
        return weights_pl

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
