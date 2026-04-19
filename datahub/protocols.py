"""Domain protocols (contracts). Implementations in domain/.

Output columns align with docs/data/TUSHARE_API_REFERENCE.md where applicable.
"""

from __future__ import annotations

from typing import Literal, Protocol


class StockProtocol(Protocol):
    """Stock. Entry: from datahub import Stock; s = Stock()."""

    def universe(self) -> pd.DataFrame:
        """Stock basic list. Columns: ts_code, symbol, name, area, industry, fullname, enname,
        cnspell, market, exchange, curr_type, list_status, list_date, delist_date, is_hs,
        act_name, act_ent_type. Tushare: stock_basic."""
        ...

    def price(
        self,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        codes: list[str] | None = None,
        fields: list[str] | None = None,
    ) -> pd.DataFrame:
        """Daily quotes. Columns: ts_code, trade_date, open, high, low, close, pre_close,
        change, pct_chg, vol, amount. Tushare: daily (may merge daily_basic)."""
        ...

    def universe_by_index(
        self,
        index_code: str,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Index constituents. Columns: index_code, con_code, trade_date, weight.
        Tushare: index_weight."""
        ...

    def available_dates(self) -> list[str]:
        """Available trade dates (YYYYMMDD)."""
        ...

    def latest_date(self) -> str | None:
        """Latest available trade date (YYYYMMDD)."""
        ...

    def returns(
        self,
        codes: list[str],
        start_date: str,
        end_date: str,
        freq: str = "daily",
        adj: str = "post",
    ) -> pd.DataFrame:
        """Returns series. Columns: ts_code, date, return (and/or freq). From price + adj_factor."""
        ...

    def liquidity(
        self,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        codes: list[str] | None = None,
    ) -> pd.DataFrame:
        """Liquidity/turnover. Columns: ts_code, trade_date, turnover_rate, turnover_rate_f,
        volume_ratio, etc. Tushare: daily_basic."""
        ...

    def limit_hits(
        self,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        direction: str = "both",
    ) -> pd.DataFrame:
        """Limit up/down list. Columns: trade_date, ts_code, industry, name, close, pct_chg,
        amp, fc_ratio, flt_ratio, turnover, fd_amount, first_time, last_time, open_times,
        strth, limit_type. Tushare: limit_list."""
        ...

    def valuation(
        self,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        codes: list[str] | None = None,
        fields: list[str] | None = None,
    ) -> pd.DataFrame:
        """Daily valuation. Columns: ts_code, trade_date, close, turnover_rate, turnover_rate_f,
        volume_ratio, pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm, total_share, float_share,
        free_share, total_mv, circ_mv. Tushare: daily_basic."""
        ...

    def financials(
        self,
        code: str,
        start_date: str,
        end_date: str,
        period_type: str = "annual",
        fields: list[str] | None = None,
    ) -> pd.DataFrame:
        """Income/balance/cashflow. Columns: 100+ fields (revenue, cost, profit, etc).
        Tushare: income, balancesheet, cashflow."""
        ...

    def earnings(
        self,
        code: str,
        start_date: str,
        end_date: str,
        include_estimates: bool = False,
    ) -> pd.DataFrame:
        """Earnings/forecast. Columns: ts_code, ann_date, end_date, type, p_change_min,
        p_change_max, net_profit_min, net_profit_max, etc. Tushare: forecast, express."""
        ...

    def order_flow(
        self,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        codes: list[str] | None = None,
    ) -> pd.DataFrame:
        """Money flow. Columns: ts_code, trade_date, buy_sm_vol, buy_sm_amount, sell_sm_vol,
        sell_sm_amount, buy_md_vol, buy_md_amount, sell_md_vol, sell_md_amount, buy_lg_vol,
        buy_lg_amount, sell_lg_vol, sell_lg_amount, buy_elg_vol, buy_elg_amount, sell_elg_vol,
        sell_elg_amount, net_mf_vol, net_mf_amount. Tushare: moneyflow."""
        ...

    def margin_pressure(
        self,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        codes: list[str] | None = None,
    ) -> pd.DataFrame:
        """Margin/margin detail. Columns: ts_code, trade_date, rzye, rqye, rzmre, rqyl,
        rzche, rqchl, rzmcl, rzrqye. Tushare: margin_detail."""
        ...

    def dividends(
        self,
        code: str,
        start_date: str,
        end_date: str,
        status: str = "all",
    ) -> pd.DataFrame:
        """Dividend. Columns: ts_code, ann_date, record_date, ex_date, pay_date, div_proc, etc.
        Tushare: dividend."""
        ...

    def corporate_actions(
        self,
        code: str,
        start_date: str,
        end_date: str,
        action_type: str = "all",
    ) -> pd.DataFrame:
        """Corporate actions (dividend, buyback, etc). Tushare: dividend, repurchase, etc."""
        ...

    def ownership(
        self,
        code: str,
        date: str,
        holder_type: str = "all",
    ) -> pd.DataFrame:
        """Holder/ownership. Tushare: stk_holdernumber, holder."""
        ...

    def insider_activity(
        self,
        code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """Insider trading. Tushare: stk_holdertrade."""
        ...


class FundProtocol(Protocol):
    """Fund. Entry: from datahub import Fund; f = Fund()."""

    def nav(
        self,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        codes: list[str] | None = None,
        fields: list[str] | None = None,
    ) -> pd.DataFrame:
        """Fund NAV. Columns: ts_code, ann_date, nav_date, unit_nav, accum_nav, accum_div,
        net_asset, total_netasset, adj_nav, update_flag. Tushare: fund_nav."""
        ...

    def available_dates(self) -> list[str]:
        """Available NAV dates (YYYYMMDD)."""
        ...

    def latest_date(self) -> str | None:
        """Latest NAV date (YYYYMMDD)."""
        ...

    def universe(
        self,
        market: str = "CN",
        fund_type: str | None = None,
        status: str = "active",
        fields: list[str] | None = None,
    ) -> pd.DataFrame:
        """Fund list. Columns: ts_code, name, management, custodian, fund_type, found_date,
        due_date, list_date, issue_date, delist_date, issue_amount, invest_type, type, status,
        etc. Tushare: fund_basic."""
        ...

    def profile(self, code: str) -> pd.DataFrame:
        """Single fund profile. Same columns as universe. Tushare: fund_basic."""
        ...

    def returns(
        self,
        codes: list[str],
        start_date: str,
        end_date: str,
        freq: str = "daily",
    ) -> pd.DataFrame:
        """Fund returns. Columns: ts_code, date, return (from nav)."""
        ...

    def risk_metrics(
        self,
        codes: list[str],
        start_date: str,
        end_date: str,
        benchmark: str | None = None,
        freq: str = "monthly",
    ) -> pd.DataFrame:
        """Risk metrics (volatility, Sharpe, etc). Derived from nav/returns."""
        ...

    def holdings(
        self,
        code: str,
        *,
        period: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        asset_type: str = "equity",
    ) -> pd.DataFrame:
        """Fund portfolio. Columns: ts_code, ann_date, end_date, symbol, type, shares,
        market_val, ratio. Tushare: fund_portfolio."""
        ...

    def sector_exposure(self, code: str, period: str) -> pd.DataFrame:
        """Sector exposure. Derived from holdings/industry."""
        ...

    def top_positions(self, code: str, period: str, top_n: int = 10) -> pd.DataFrame:
        """Top N positions. Same columns as holdings. Tushare: fund_portfolio."""
        ...

    def aum_history(
        self,
        codes: list[str],
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """AUM history. From nav * shares."""
        ...

    def distributions(
        self,
        code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """Fund dividend/distribution. Tushare: fund_div."""
        ...


class IndexProtocol(Protocol):
    """Index. Entry: from datahub import Index; idx = Index()."""

    def members(
        self,
        index_code: str,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Index constituents. Columns: index_code, con_code, trade_date, weight.
        Tushare: index_weight."""
        ...

    def available_dates(self, index_code: str | None = None) -> list[str]:
        """Available index dates (YYYYMMDD)."""
        ...

    def latest_date(self, index_code: str | None = None) -> str | None:
        """Latest index date (YYYYMMDD)."""
        ...

    def level(
        self,
        index_code: str,
        start_date: str,
        end_date: str,
        freq: str = "daily",
    ) -> pd.DataFrame:
        """Index OHLC. Columns: ts_code, trade_date, close, open, high, low, pre_close,
        pct_change, vol, amount. Tushare: index_daily."""
        ...

    def returns(
        self,
        index_code: str,
        start_date: str,
        end_date: str,
        freq: str = "daily",
        include_dividends: bool = True,
    ) -> pd.DataFrame:
        """Index returns. Derived from level."""
        ...

    def valuation(
        self,
        index_code: str,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Index valuation. Tushare: index_valuation if available."""
        ...

    def weights(
        self,
        index_code: str,
        *,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        codes: list[str] | None = None,
    ) -> pd.DataFrame:
        """Index weights. Columns: index_code, con_code, trade_date, weight.
        Tushare: index_weight."""
        ...

    def rebalance_history(
        self,
        index_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """Rebalance history. From index_weight changes."""
        ...

    def sector_breakdown(
        self,
        index_code: str,
        date: str,
        level: int = 1,
    ) -> pd.DataFrame:
        """Sector breakdown. From members + industry."""
        ...

    def catalog(self, family: str | None = None) -> pd.DataFrame:
        """Index catalog. Columns: ts_code, name, fullname, market, publisher, index_type,
        category, base_date, base_point, list_date, weight_rule, desc, exp_date.
        Tushare: index_basic, index_classify."""
        ...


class NewsProtocol(Protocol):
    """News. Entry: from datahub import News; n = News()."""

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
        """Sentiment scores. Columns vary by source (code, date, score, etc)."""
        ...

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
        """Events. Columns: code, date, event_type, title, summary, etc."""
        ...

    def earnings_surprise(
        self,
        *,
        code: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Earnings surprise. Columns: code, date, actual, estimate, surprise, etc."""
        ...

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
        """Filings/announcements. Tushare anns: ts_code, ann_date, title, content, etc."""
        ...

    def analyst_ratings(
        self,
        *,
        code: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        action: Literal["initiation", "upgrade", "downgrade", "reiterate", "all"] = "all",
    ) -> pd.DataFrame:
        """Analyst ratings. Columns: code, date, action, rating, target_price, etc."""
        ...

    def consensus(
        self,
        *,
        code: str | None = None,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Consensus estimates. Columns: code, date, eps, revenue, etc."""
        ...

    def estimate_revisions(
        self,
        *,
        code: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        period: Literal["fy1", "fy2"] = "fy1",
    ) -> pd.DataFrame:
        """Estimate revisions. Columns: code, date, period, revision, etc."""
        ...

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
        """Event calendar. Columns: code, date, event_type, description. Tushare: disclosure_date."""
        ...

    def available_dates(
        self,
        kind: Literal["sentiment", "events", "filings", "analyst"] = "events",
    ) -> list[str]:
        """Available dates for given kind (YYYYMMDD)."""
        ...

    def latest_date(
        self,
        kind: Literal["sentiment", "events", "filings", "analyst"] = "events",
    ) -> str | None:
        """Latest date for given kind (YYYYMMDD)."""
        ...


class CalendarProtocol(Protocol):
    """Trading calendar. Entry: from datahub import Calendar; cal = Calendar()."""

    def get_trade_dates(self, start_date: str, end_date: str) -> list[str]:
        """Return list of trade dates (YYYYMMDD) in [start_date, end_date], ascending."""
        ...

    def is_trade_day(self, date: str) -> bool:
        """Return True if date is a trade day (YYYYMMDD)."""
        ...

    def get_latest_trade_date(self, before_date: str) -> str | None:
        """Return the latest trade date strictly before before_date (YYYYMMDD), or None."""
        ...


class FeatureProtocol(Protocol):
    """Feature. Entry: from datahub import Feature; feat = Feature()."""

    def snapshot(
        self,
        factors: str | list[str],
        *,
        date: str,
        universe: list[str] | None = None,
    ) -> pd.DataFrame:
        """Factor snapshot. Columns: ts_code (or code), trade_date, plus one column per factor
        (e.g. pe_ttm, momentum_1m). Built from daily/daily_basic/adj_factor."""
        ...

    def history(
        self,
        factors: str | list[str],
        *,
        start_date: str,
        end_date: str,
        universe: list[str] | None = None,
        freq: Literal["D", "W", "M"] = "D",
    ) -> pd.DataFrame:
        """Factor history. Columns: ts_code, trade_date, factor_1, factor_2, ..."""
        ...

    def rank(
        self,
        factor: str,
        *,
        date: str,
        universe: list[str] | None = None,
        method: Literal["percentile", "zscore", "rank"] = "percentile",
        neutralize_by: list[Literal["industry", "size"]] | None = None,
    ) -> pd.DataFrame:
        """Factor cross-sectional rank. Columns: ts_code, trade_date, factor, rank (or percentile)."""
        ...

    def exposure(
        self,
        universe: list[str],
        factors: list[str],
        *,
        date: str,
        normalize: bool = True,
    ) -> pd.DataFrame:
        """Factor exposure. Columns: factor, exposure (and optionally industry/size)."""
        ...

    def screen(
        self,
        rules: dict[str, tuple[float | None, float | None]],
        *,
        date: str,
        universe: list[str] | None = None,
        sort_by: str | None = None,
        ascending: bool = False,
        top_n: int | None = None,
    ) -> pd.DataFrame:
        """Screen by factor rules. Columns: ts_code, trade_date, factor columns, pass/fail."""
        ...

    def quantile_portfolios(
        self,
        factor: str,
        *,
        date: str,
        n_quantiles: int = 5,
        universe: list[str] | None = None,
    ) -> pd.DataFrame:
        """Quantile portfolios. Columns: ts_code, trade_date, factor, quantile (1..n)."""
        ...

    def ic_series(
        self,
        factor: str,
        *,
        start_date: str,
        end_date: str,
        forward_returns_period: int = 20,
        universe: list[str] | None = None,
        method: Literal["pearson", "spearman"] = "spearman",
    ) -> pd.DataFrame:
        """IC time series. Columns: trade_date, ic (and optionally pvalue)."""
        ...

    def factor_return(
        self,
        factor: str,
        *,
        start_date: str,
        end_date: str,
        universe: list[str] | None = None,
        long_short: bool = True,
    ) -> pd.DataFrame:
        """Factor return series. Columns: trade_date, return (long-short or long)."""
        ...

    def list_factors(self) -> list[str]:
        """Available factor names (e.g. pe_ttm, momentum_1m)."""
        ...

    def describe(self, factor: str) -> dict[str, object]:
        """Factor metadata: name, description, source fields, etc."""
        ...

    def available_dates(self, factor: str | None = None) -> list[str]:
        """Available dates for factor(s) (YYYYMMDD)."""
        ...

    def latest_date(self, factor: str | None = None) -> str | None:
        """Latest date for factor(s) (YYYYMMDD)."""
        ...
