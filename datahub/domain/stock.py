"""Stock domain API: price, universe, index constituents."""

from __future__ import annotations


from datahub.core.dataset import Dataset
from datahub.core.query import Query
from datahub.core.repository import Repository
from datahub.domain._helpers import load_with_date_or_range


class Stock:
    """Stock domain implementation: daily quotes, index constituents, basic listing. Contract: protocols.stock.StockProtocol."""

    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def price(
        self,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        codes: list[str] | None = None,
        fields: list[str] | None = None,
    ) -> "pd.DataFrame":
        """Daily stock quotes (OHLCV + merged indicators). Single day or range."""
        return load_with_date_or_range(
            self._repo,
            Dataset.STOCK_DAILY,
            date=date,
            start_date=start_date,
            end_date=end_date,
            codes=codes,
            fields=fields,
        )

    def universe_by_index(
        self,
        index_code: str,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> "pd.DataFrame":
        """Index constituents and weights. Single date or range."""
        return load_with_date_or_range(
            self._repo,
            Dataset.STOCK_INDEX_WEIGHT,
            date=date,
            start_date=start_date,
            end_date=end_date,
            index_code=index_code,
        )

    def universe(self) -> "pl.DataFrame":
        """Stock basic listing info (single snapshot)."""
        return self._repo.load(Query(dataset=Dataset.STOCK_BASIC, date="basic"))

    def available_dates(self) -> list[str]:
        """Available dates for daily dataset."""
        return self._repo.available_dates(Dataset.STOCK_DAILY)

    def latest_date(self) -> str | None:
        """Latest available date for daily dataset."""
        return self._repo.latest_date(Dataset.STOCK_DAILY)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_query(
        self,
        dataset: Dataset,
        *,
        date: str | None,
        start_date: str | None,
        end_date: str | None,
        codes: list[str] | None = None,
        fields: list[str] | None = None,
        index_code: str | None = None,
    ) -> Query:
        """Build a Query, routing to date or range mode."""
        if date is not None:
            return Query(
                dataset=dataset,
                date=date,
                codes=codes,
                fields=fields,
                index_code=index_code,
            )
        if start_date is not None and end_date is not None:
            return Query(
                dataset=dataset,
                start_date=start_date,
                end_date=end_date,
                codes=codes,
                fields=fields,
                index_code=index_code,
            )
        raise ValueError("Provide either date or (start_date, end_date)")

    # ------------------------------------------------------------------
    # 2. PRICE & RETURNS
    # ------------------------------------------------------------------

    def returns(
        self,
        codes: list[str],
        start_date: str,
        end_date: str,
        freq: str = "daily",
        adj: str = "post",
    ) -> "pl.DataFrame":
        """Wide-format simple-return matrix: index=trade_date, columns=ts_code."""
        code_list = [codes] if isinstance(codes, str) else codes
        df = self.price(start_date=start_date, end_date=end_date, codes=code_list)
        if df.is_empty():
            return df
        close_col = "adj_close" if "adj_close" in df.columns else "close"
        # Polars pivot
        wide = df.pivot(values=close_col, index="trade_date", columns="ts_code")
        # Calculate pct_change using polars
        ret_cols = [c for c in wide.columns if c != "trade_date"]
        for col in ret_cols:
            wide = wide.with_columns(
                (pl.col(col) / pl.col(col).shift(1) - 1).alias(col)
            )
        return wide.drop_nulls(subset=ret_cols, how="all")

    def liquidity(
        self,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        codes: list[str] | None = None,
    ) -> "pd.DataFrame":
        query = self._build_query(
            Dataset.STOCK_DAILY,
            date=date,
            start_date=start_date,
            end_date=end_date,
            codes=codes,
        )
        df = self._repo.load(query)
        key_cols = ["ts_code", "trade_date"]
        liq_cols = [
            c
            for c in [
                "vol",
                "amount",
                "turnover_rate",
                "turnover_rate_f",
                "volume_ratio",
                "float_share",
                "free_share",
                "circ_mv",
            ]
            if c in df.columns
        ]
        return df[key_cols + liq_cols]

    def limit_hits(
        self,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        direction: str = "both",
    ) -> "pl.DataFrame":
        query = self._build_query(
            Dataset.STOCK_DAILY,
            date=date,
            start_date=start_date,
            end_date=end_date,
        )
        df_pl = self._repo.load(query)
        if "pct_chg" not in df_pl.columns:
            return df_pl.head(0)
        if direction == "up":
            df_pl = df_pl.filter(pl.col("pct_chg") >= 9.9)
        elif direction == "down":
            df_pl = df_pl.filter(pl.col("pct_chg") <= -9.9)
        else:
            df_pl = df_pl.filter((pl.col("pct_chg") >= 9.9) | (pl.col("pct_chg") <= -9.9))
        return df_pl

    # ------------------------------------------------------------------
    # 3. FUNDAMENTALS
    # ------------------------------------------------------------------

    def valuation(
        self,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        codes: list[str] | None = None,
        fields: list[str] | None = None,
    ) -> "pd.DataFrame":
        query = self._build_query(
            Dataset.STOCK_VALUATION,
            date=date,
            start_date=start_date,
            end_date=end_date,
            codes=codes,
            fields=fields,
        )
        return self._repo.load(query)

    def financials(
        self,
        code: str,
        start_date: str,
        end_date: str,
        period_type: str = "annual",
        fields: list[str] | None = None,
    ) -> "pl.DataFrame":
        sources = [
            Dataset.STOCK_FINANCIALS_INCOME,
            Dataset.STOCK_FINANCIALS_BALANCE,
            Dataset.STOCK_FINANCIALS_CASHFLOW,
        ]
        frames: list["pl.DataFrame"] = []
        for ds in sources:
            try:
                q = Query(
                    dataset=ds,
                    start_date=start_date,
                    end_date=end_date,
                    codes=[code],
                    fields=fields,
                )
                frames.append(self._repo.load(q))
            except Exception:  # noqa: BLE001
                pass
        if not frames:
            return pl.DataFrame()
        merged = frames[0]
        for right in frames[1:]:
            on_cols = [
                c for c in ["ts_code", "end_date"] if c in merged.columns and c in right.columns
            ]
            merged = merged.join(right, on=on_cols, how="outer", suffix="_dup")
            merged = merged.select([c for c in merged.columns if not c.endswith("_dup")])
        if "end_date" in merged.columns:
            if period_type == "annual":
                merged = merged.filter(pl.col("end_date").str.ends_with("1231"))
            elif period_type == "semi":
                merged = merged.filter(
                    pl.col("end_date").str.ends_with("0630") | pl.col("end_date").str.ends_with("1231")
                )
        return merged.with_row_index().drop("index")

    def earnings(
        self,
        code: str,
        start_date: str,
        end_date: str,
        include_estimates: bool = False,
    ) -> "pl.DataFrame":
        query = Query(
            dataset=Dataset.EARNINGS_FORECAST,
            start_date=start_date,
            end_date=end_date,
            codes=[code],
        )
        return self._repo.load(query)

    def order_flow(
        self,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        codes: list[str] | None = None,
    ) -> "pd.DataFrame":
        query = self._build_query(
            Dataset.STOCK_DAILY,
            date=date,
            start_date=start_date,
            end_date=end_date,
            codes=codes,
        )
        df = self._repo.load(query)
        key_cols = ["ts_code", "trade_date"]
        flow_cols = [
            c
            for c in [
                "buy_sm_vol",
                "buy_sm_amount",
                "sell_sm_vol",
                "sell_sm_amount",
                "buy_md_vol",
                "buy_md_amount",
                "sell_md_vol",
                "sell_md_amount",
                "buy_lg_vol",
                "buy_lg_amount",
                "sell_lg_vol",
                "sell_lg_amount",
                "buy_elg_vol",
                "buy_elg_amount",
                "sell_elg_vol",
                "sell_elg_amount",
                "net_mf_vol",
                "net_mf_amount",
            ]
            if c in df.columns
        ]
        return df[key_cols + flow_cols]

    def margin_pressure(
        self,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        codes: list[str] | None = None,
    ) -> "pd.DataFrame":
        query = self._build_query(
            Dataset.STOCK_MARGIN,
            date=date,
            start_date=start_date,
            end_date=end_date,
            codes=codes,
        )
        return self._repo.load(query)

    # ------------------------------------------------------------------
    # 4. CORPORATE EVENTS
    # ------------------------------------------------------------------

    def dividends(
        self,
        code: str,
        start_date: str,
        end_date: str,
        status: str = "all",
    ) -> "pd.DataFrame":
        query = Query(
            dataset=Dataset.STOCK_DIVIDEND,
            start_date=start_date,
            end_date=end_date,
            codes=[code],
        )
        df = self._repo.load(query)
        if status != "all" and "div_proc" in df.columns:
            df = df[df["div_proc"] == status]
        return df.reset_index(drop=True)

    def corporate_actions(
        self,
        code: str,
        start_date: str,
        end_date: str,
        action_type: str = "all",
    ) -> "pl.DataFrame":
        frames: list["pl.DataFrame"] = []
        if action_type in ("all", "buyback", "repurchase"):
            try:
                q = Query(
                    dataset=Dataset.STOCK_REPURCHASE,
                    start_date=start_date,
                    end_date=end_date,
                    codes=[code],
                )
                df = self._repo.load(q)
                df = df.with_columns(pl.lit("buyback").alias("action_type"))
                frames.append(df)
            except Exception:  # noqa: BLE001
                pass
        if action_type in ("all", "dividend"):
            try:
                q = Query(
                    dataset=Dataset.STOCK_DIVIDEND,
                    start_date=start_date,
                    end_date=end_date,
                    codes=[code],
                )
                df = self._repo.load(q)
                df = df.with_columns(pl.lit("dividend").alias("action_type"))
                frames.append(df)
            except Exception:  # noqa: BLE001
                pass
        if not frames:
            return pl.DataFrame()
        return pl.concat(frames)

    def ownership(
        self,
        code: str,
        date: str,
        holder_type: str = "all",
    ) -> "pd.DataFrame":
        query = Query(
            dataset=Dataset.STOCK_HOLDER,
            date=date,
            codes=[code],
        )
        return self._repo.load(query)

    def insider_activity(
        self,
        code: str,
        start_date: str,
        end_date: str,
    ) -> "pd.DataFrame":
        query = Query(
            dataset=Dataset.STOCK_PLEDGE,
            start_date=start_date,
            end_date=end_date,
            codes=[code],
        )
        return self._repo.load(query)
