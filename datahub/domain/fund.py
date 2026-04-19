"""Fund domain API: nav."""

from __future__ import annotations


from datahub.core.dataset import Dataset
from datahub.core.query import Query
from datahub.core.repository import Repository
from datahub.domain._helpers import load_with_date_or_range


class Fund:
    """Fund domain implementation: NAV, universe, holdings. Contract: protocols.fund.FundProtocol."""

    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def nav(
        self,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        codes: list[str] | None = None,
        fields: list[str] | None = None,
    ) -> "pd.DataFrame":
        """Fund NAV. Single date or range."""
        return load_with_date_or_range(
            self._repo,
            Dataset.FUND_NAV,
            date=date,
            start_date=start_date,
            end_date=end_date,
            codes=codes,
            fields=fields,
        )

    def available_dates(self) -> list[str]:
        """Available dates for fund nav dataset."""
        return self._repo.available_dates(Dataset.FUND_NAV)

    def latest_date(self) -> str | None:
        """Latest available date for fund nav dataset."""
        return self._repo.latest_date(Dataset.FUND_NAV)

    def universe(
        self,
        market: str = "CN",
        fund_type: str | None = None,
        status: str = "active",
        fields: list[str] | None = None,
    ) -> "pl.DataFrame":
        
        query = Query(
            dataset=Dataset.FUND_BASIC,
            start_date="19900101",
            end_date="20991231",
            fields=fields,
        )
        df = self._repo.load(query)
        if market and "market" in df.columns:
            df = df.filter(pl.col("market") == market)
        if fund_type and "fund_type" in df.columns:
            df = df.filter(pl.col("fund_type") == fund_type)
        if status and status != "all" and "status" in df.columns:
            df = df.filter(pl.col("status") == status)
        return df.with_row_index().drop("index")

    def profile(self, code: str) -> "pd.DataFrame":
        query = Query(
            dataset=Dataset.FUND_BASIC,
            start_date="19900101",
            end_date="20991231",
            codes=[code],
        )
        return self._repo.load(query)

    def returns(
        self,
        codes: list[str],
        start_date: str,
        end_date: str,
        freq: str = "daily",
    ) -> "pl.DataFrame":
        
        query = Query(
            dataset=Dataset.FUND_NAV,
            start_date=start_date,
            end_date=end_date,
            codes=codes,
        )
        df = self._repo.load(query)
        nav_col = "adj_nav" if "adj_nav" in df.columns else "unit_nav"
        date_col = next(
            (c for c in ["ann_date", "nav_date", "end_date"] if c in df.columns),
            None,
        )
        if date_col is None or nav_col not in df.columns:
            return pl.DataFrame()
        # Polars pivot and pct_change
        pivot = df.pivot(values=nav_col, index=date_col, columns="ts_code")
        ret_cols = [c for c in pivot.columns if c != date_col]
        for col in ret_cols:
            pivot = pivot.with_columns(
                (pl.col(col) / pl.col(col).shift(1) - 1).alias(col)
            )
        # Unpivot back to long format
        rets = pivot.unpivot(
            index=date_col,
            variable_name="ts_code",
            value_name="return"
        )
        return rets.drop_nulls().with_row_index().drop("index")

    def risk_metrics(
        self,
        codes: list[str],
        start_date: str,
        end_date: str,
        benchmark: str | None = None,
        freq: str = "monthly",
    ) -> "pl.DataFrame":
        
        rets_df = self.returns(codes=codes, start_date=start_date, end_date=end_date)
        if rets_df.is_empty():
            return pl.DataFrame()
        results = []
        for code in rets_df["ts_code"].unique().to_list():
            r = rets_df.filter(pl.col("ts_code") == code)["return"].drop_nulls()
            if r.is_empty():
                continue
            ann = r.mean() * 252
            vol = r.std() * np.sqrt(252)
            sharpe = ann / vol if vol > 0 else float("nan")
            cum = (1 + r).cum_prod()
            peak = cum.cum_max()
            dd = (cum - peak) / peak
            max_dd = float(dd.min())
            results.append(
                {
                    "ts_code": code,
                    "ann_return": ann,
                    "volatility": vol,
                    "sharpe": sharpe,
                    "max_drawdown": max_dd,
                }
            )
        return pl.DataFrame(results)

    def holdings(
        self,
        code: str,
        *,
        period: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        asset_type: str = "equity",
    ) -> "pd.DataFrame":
        if period is not None:
            query = Query(dataset=Dataset.FUND_PORTFOLIO, date=period, codes=[code])
        else:
            query = Query(
                dataset=Dataset.FUND_PORTFOLIO,
                start_date=start_date or "19900101",
                end_date=end_date or "20991231",
                codes=[code],
            )
        return self._repo.load(query)

    def sector_exposure(self, code: str, period: str) -> "pl.DataFrame":
        
        df = self.holdings(code=code, period=period)
        # Convert to polars for groupby (large dataset optimization)
        df_pl = pl.from_pandas(df)
        if df_pl.is_empty() or "stk_mkv_ratio" not in df_pl.columns:
            return pl.DataFrame()
        return df_pl.group_by("symbol").agg(pl.col("stk_mkv_ratio").sum())

    def top_positions(self, code: str, period: str, top_n: int = 10) -> "pl.DataFrame":
        
        df = self.holdings(code=code, period=period)
        # Convert to polars for sorting (large dataset optimization)
        df_pl = pl.from_pandas(df)
        if df_pl.is_empty():
            return df_pl
        sort_col = next((c for c in ["stk_mkv_ratio", "mkv"] if c in df_pl.columns), None)
        if sort_col is None:
            return df_pl.head(top_n)
        return df_pl.sort(sort_col, descending=True).head(top_n)

    def aum_history(
        self,
        codes: list[str],
        start_date: str,
        end_date: str,
    ) -> "pd.DataFrame":
        query = Query(
            dataset=Dataset.FUND_NAV,
            start_date=start_date,
            end_date=end_date,
            codes=codes,
        )
        df = self._repo.load(query)
        date_col = next((c for c in ["nav_date", "ann_date"] if c in df.columns), None)
        aum_col = next((c for c in ["total_netasset", "accum_nav"] if c in df.columns), None)
        if date_col is None or aum_col is None:
            return pl.DataFrame()
        return df[[c for c in ["ts_code", date_col, aum_col] if c in df.columns]]

    def distributions(
        self,
        code: str,
        start_date: str,
        end_date: str,
    ) -> "pd.DataFrame":
        query = Query(
            dataset=Dataset.FUND_DIVIDEND,
            start_date=start_date,
            end_date=end_date,
            codes=[code],
        )
        return self._repo.load(query)
