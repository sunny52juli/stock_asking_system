"""Index domain: members, optional index daily. Implements IndexProtocol."""

from __future__ import annotations

import pandas as pd

from datahub.core.dataset import Dataset
from datahub.core.query import Query
from datahub.core.repository import Repository
from datahub.domain._helpers import load_with_date_or_range


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
    ) -> pd.DataFrame:
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
        index_code: str,
        start_date: str,
        end_date: str,
        freq: str = "daily",
    ) -> pd.DataFrame:
        return self._repo.load(
            Query(
                dataset=Dataset.INDEX_DAILY,
                start_date=start_date,
                end_date=end_date,
                index_code=index_code,
            )
        )

    def returns(
        self,
        index_code: str,
        start_date: str,
        end_date: str,
        freq: str = "daily",
        include_dividends: bool = True,
    ) -> pd.DataFrame:
        df = self.level(index_code=index_code, start_date=start_date, end_date=end_date, freq=freq)
        if df.empty or "close" not in df.columns:
            return df
        date_col = next((c for c in ["trade_date"] if c in df.columns), df.columns[0])
        df = df.sort_values(date_col)
        df = df.copy()
        df["return"] = df["close"].pct_change()
        return df[[date_col, "ts_code", "return"]].dropna().reset_index(drop=True)

    def valuation(
        self,
        index_code: str,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
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
    ) -> pd.DataFrame:
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
    ) -> pd.DataFrame:
        df = self.weights(index_code=index_code, start_date=start_date, end_date=end_date)
        if df.empty:
            return pd.DataFrame()
        date_col = next((c for c in ["trade_date", "end_date"] if c in df.columns), None)
        code_col = next((c for c in ["con_code", "ts_code"] if c in df.columns), None)
        if date_col is None or code_col is None:
            return pd.DataFrame()
        dates = sorted(df[date_col].unique())
        rebalances = []
        for i in range(1, len(dates)):
            prev_codes = set(df[df[date_col] == dates[i - 1]][code_col])
            curr_codes = set(df[df[date_col] == dates[i]][code_col])
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
        return pd.DataFrame(rebalances)

    def sector_breakdown(
        self,
        index_code: str,
        date: str,
        level: int = 1,
    ) -> pd.DataFrame:
        weights_df = self.weights(index_code=index_code, date=date)
        if weights_df.empty:
            return pd.DataFrame()
        code_col = next((c for c in ["con_code", "ts_code"] if c in weights_df.columns), None)
        weight_col = next((c for c in ["weight"] if c in weights_df.columns), None)
        if code_col is None:
            return weights_df
        try:
            basic_q = Query(
                dataset=Dataset.STOCK_BASIC,
                start_date="19900101",
                end_date="20991231",
                codes=weights_df[code_col].tolist(),
            )
            basic_df = self._repo.load(basic_q)
            industry_col = "industry"
            if industry_col in basic_df.columns and "ts_code" in basic_df.columns:
                merged = weights_df.merge(
                    basic_df[["ts_code", industry_col]],
                    left_on=code_col,
                    right_on="ts_code",
                    how="left",
                )
                if weight_col:
                    return (
                        merged.groupby(industry_col, as_index=False)[weight_col]
                        .sum()
                        .sort_values(weight_col, ascending=False)
                        .reset_index(drop=True)
                    )
        except Exception:
            return weights_df
        return weights_df

    def catalog(self, family: str | None = None) -> pd.DataFrame:
        query = Query(
            dataset=Dataset.INDEX_BASIC,
            start_date="19900101",
            end_date="20991231",
        )
        df = self._repo.load(query)
        if family and "market" in df.columns:
            df = df[df["market"].str.contains(family, na=False)]
        return df.reset_index(drop=True)
