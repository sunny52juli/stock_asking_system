"""News domain. Implements NewsProtocol."""

from __future__ import annotations

from typing import Literal

import pandas as pd

from datahub.core.dataset import Dataset
from datahub.core.query import Query
from datahub.core.repository import Repository


class News:
    """News domain implementation: filings, events, analyst. Contract: protocols.news.NewsProtocol."""

    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    # ── 1. Sentiment ───────────────────────────────────────────────────

    def sentiment(
        self,
        *,
        code: str | None = None,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        source: Literal["news", "social", "analyst", "combined"] = "combined",
        window: int = 7,
    ) -> pd.DataFrame:
        raise NotImplementedError("News.sentiment() not yet implemented")

    # ── 2. Events ─────────────────────────────────────────────────────

    def events(
        self,
        *,
        code: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        event_type: Literal[
            "earnings",
            "guidance",
            "ma",
            "management",
            "buyback",
            "strategic",
            "regulatory",
            "all",
        ] = "all",
    ) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        include_announcements = event_type in (
            "all",
            "guidance",
            "ma",
            "management",
            "buyback",
            "strategic",
            "regulatory",
        )
        include_earnings = event_type in ("all", "earnings")

        if include_announcements and code:
            try:
                q = Query(
                    dataset=Dataset.STOCK_ANNOUNCEMENT,
                    start_date=start_date,
                    end_date=end_date,
                    codes=[code],
                )
                df = self._repo.load(q)
                df["event_type"] = "announcement"
                frames.append(df)
            except Exception:
                pass

        if include_earnings and code:
            try:
                q = Query(
                    dataset=Dataset.EARNINGS_FORECAST,
                    start_date=start_date,
                    end_date=end_date,
                    codes=[code],
                )
                df = self._repo.load(q)
                df["event_type"] = "earnings"
                frames.append(df)
            except Exception:
                pass

        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    def earnings_surprise(
        self,
        *,
        code: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        query = Query(
            dataset=Dataset.EARNINGS_FORECAST,
            start_date=start_date,
            end_date=end_date,
            codes=[code] if code else None,
        )
        return self._repo.load(query)

    # ── 3. Filings ────────────────────────────────────────────────────

    def filings(
        self,
        *,
        code: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        filing_type: Literal[
            "annual_report",
            "semi_report",
            "quarterly_report",
            "ownership_change",
            "material_event",
            "prospectus",
            "all",
        ] = "all",
    ) -> pd.DataFrame:
        query = Query(
            dataset=Dataset.STOCK_ANNOUNCEMENT,
            start_date=start_date,
            end_date=end_date,
            codes=[code] if code else None,
        )
        df = self._repo.load(query)
        if filing_type != "all" and "ann_type" in df.columns:
            df = df[df["ann_type"] == filing_type]
        return df.reset_index(drop=True)

    # ── 4. Analyst actions ────────────────────────────────────────────

    def analyst_ratings(
        self,
        *,
        code: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        action: Literal["initiation", "upgrade", "downgrade", "reiterate", "all"] = "all",
    ) -> pd.DataFrame:
        query = Query(
            dataset=Dataset.ANALYST_REPORT,
            start_date=start_date,
            end_date=end_date,
            codes=[code] if code else None,
        )
        df = self._repo.load(query)
        if action != "all" and "rating_type" in df.columns:
            df = df[df["rating_type"] == action]
        return df.reset_index(drop=True)

    def consensus(
        self,
        *,
        code: str | None = None,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        if date is not None:
            query = Query(
                dataset=Dataset.EARNINGS_FORECAST,
                date=date,
                codes=[code] if code else None,
            )
        else:
            query = Query(
                dataset=Dataset.EARNINGS_FORECAST,
                start_date=start_date,
                end_date=end_date,
                codes=[code] if code else None,
            )
        df = self._repo.load(query)
        if df.empty:
            return df
        numeric_cols = [
            c
            for c in ["net_profit_min", "net_profit_max", "p_change_min", "p_change_max"]
            if c in df.columns
        ]
        if numeric_cols:
            agg = dict.fromkeys(numeric_cols, "mean")
            date_col = next((c for c in ["ann_date", "end_date"] if c in df.columns), None)
            if date_col:
                return df.groupby(date_col, as_index=False).agg(agg)
        return df

    def estimate_revisions(
        self,
        *,
        code: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        period: Literal["fy1", "fy2"] = "fy1",
    ) -> pd.DataFrame:
        query = Query(
            dataset=Dataset.EARNINGS_FORECAST,
            start_date=start_date,
            end_date=end_date,
            codes=[code] if code else None,
        )
        df = self._repo.load(query)
        if period and "end_date" in df.columns:
            df = df[df["end_date"].str.startswith(period)]
        return df.reset_index(drop=True)

    # ── 5. Calendar ───────────────────────────────────────────────────

    def calendar(
        self,
        *,
        start_date: str,
        end_date: str,
        event_type: Literal[
            "earnings",
            "dividend",
            "ipo",
            "lock_expiry",
            "index_rebal",
            "all",
        ] = "all",
        codes: list[str] | None = None,
    ) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []

        try:
            q = Query(
                dataset=Dataset.TRADE_CALENDAR,
                start_date=start_date,
                end_date=end_date,
            )
            frames.append(self._repo.load(q))
        except Exception:
            pass

        if event_type in ("all", "earnings") and codes:
            try:
                q = Query(
                    dataset=Dataset.STOCK_ANNOUNCEMENT,
                    start_date=start_date,
                    end_date=end_date,
                    codes=codes,
                )
                df = self._repo.load(q)
                df["event_type"] = "announcement"
                frames.append(df)
            except Exception:
                pass

        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    # ── Meta ───────────────────────────────────────────────────────────

    def available_dates(
        self,
        kind: Literal["sentiment", "events", "filings", "analyst"] = "events",
    ) -> list[str]:
        return []

    def latest_date(
        self,
        kind: Literal["sentiment", "events", "filings", "analyst"] = "events",
    ) -> str | None:
        return None
