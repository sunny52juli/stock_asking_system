"""Feature domain — cross-sectional factor computation and analytics."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Literal

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from datahub.protocols import StockProtocol

# Built-in factor registry: factor_name -> spec
_FACTOR_REGISTRY: dict[str, dict] = {
    "momentum_1m": {
        "description": "1个月价格动量(近21日收益率)",
        "window": 21,
        "source_col": "close",
        "transform": "pct_change",
    },
    "momentum_3m": {
        "description": "3个月价格动量(近63日收益率)",
        "window": 63,
        "source_col": "close",
        "transform": "pct_change",
    },
    "momentum_6m": {
        "description": "6个月价格动量(近126日收益率)",
        "window": 126,
        "source_col": "close",
        "transform": "pct_change",
    },
    "volatility_20d": {
        "description": "20日收益率波动率(年化)",
        "window": 20,
        "source_col": "close",
        "transform": "volatility",
    },
    "volatility_60d": {
        "description": "60日收益率波动率(年化)",
        "window": 60,
        "source_col": "close",
        "transform": "volatility",
    },
    "turnover_mean_20d": {
        "description": "20日平均换手率",
        "window": 20,
        "source_col": "turnover_rate",
        "transform": "mean",
    },
    "amount_mean_20d": {
        "description": "20日平均成交额(流动性)",
        "window": 20,
        "source_col": "amount",
        "transform": "mean",
    },
    "pe_ttm": {
        "description": "市盈率 TTM(估值因子)",
        "window": 1,
        "source_col": "pe_ttm",
        "transform": "last",
    },
    "pb": {
        "description": "市净率(估值因子)",
        "window": 1,
        "source_col": "pb",
        "transform": "last",
    },
    "rsi_14": {
        "description": "14日 RSI 相对强弱指标",
        "window": 14,
        "source_col": "close",
        "transform": "rsi",
    },
}

_MAX_LOOKBACK_DAYS = 400  # calendar-day buffer for slowest factor (momentum_6m = 126 trading days)


def _to_factor_list(factors: str | list[str]) -> list[str]:
    return [factors] if isinstance(factors, str) else list(factors)


def _long_to_wide(price_df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Pivot long-format price DataFrame to wide (trade_date x ts_code)."""
    if "trade_date" not in price_df.columns or "ts_code" not in price_df.columns:
        return pd.DataFrame()
    if col not in price_df.columns:
        return pd.DataFrame()
    wide = price_df.pivot_table(index="trade_date", columns="ts_code", values=col, aggfunc="last")
    wide.index = wide.index.astype(str)
    wide = wide.sort_index()
    return wide


def _compute_factor(price_df: pd.DataFrame, factor_name: str) -> pd.Series:
    """Compute a single cross-sectional factor from long-format price DataFrame.

    Returns a Series indexed by ts_code with the latest computed value.
    """
    if factor_name not in _FACTOR_REGISTRY:
        raise ValueError(
            f"Unknown factor: {factor_name!r}. Call list_factors() to see available factors."
        )
    spec = _FACTOR_REGISTRY[factor_name]
    col: str = spec["source_col"]
    window: int = spec["window"]
    transform: str = spec["transform"]

    # Fall back to close if the target column is absent
    if col not in price_df.columns:
        if "close" in price_df.columns:
            col = "close"
        else:
            return pd.Series(dtype=float, name=factor_name)

    wide = _long_to_wide(price_df, col)
    if wide.empty:
        return pd.Series(dtype=float, name=factor_name)

    if transform == "pct_change":
        result = wide.pct_change(periods=window).iloc[-1]
    elif transform == "volatility":
        returns = wide.pct_change()
        result = returns.rolling(window).std().iloc[-1] * np.sqrt(252)
    elif transform == "mean":
        result = wide.rolling(window).mean().iloc[-1]
    elif transform == "last":
        result = wide.iloc[-1]
    elif transform == "rsi":
        delta = wide.diff()
        gain = delta.clip(lower=0).rolling(window).mean()
        loss = (-delta.clip(upper=0)).rolling(window).mean()
        rs = gain / loss.replace(0, np.nan)
        result = (100 - 100 / (1 + rs)).iloc[-1]
    else:
        result = wide.iloc[-1]

    result.name = factor_name
    return result


def _date_yyyymmdd_to_start(end_date: str, calendar_days_back: int) -> str:
    """Subtract calendar_days_back from end_date (YYYYMMDD) and return YYYYMMDD."""
    dt = datetime.date(int(end_date[:4]), int(end_date[4:6]), int(end_date[6:8]))
    start_dt = dt - datetime.timedelta(days=calendar_days_back)
    return start_dt.strftime("%Y%m%d")


class Feature:
    """Feature domain implementation: factor snapshot, rank, screen. Contract: protocols.feature.FeatureProtocol."""

    def __init__(self, stock: StockProtocol) -> None:
        self._stock = stock

    # ------------------------------------------------------------------
    # 1. CROSS-SECTIONAL ACCESS
    # ------------------------------------------------------------------

    def snapshot(
        self,
        factors: str | list[str],
        *,
        date: str,
        universe: list[str] | None = None,
    ) -> pd.DataFrame:
        """Factor values for the full universe at a single point in time.

        Returns DataFrame: index = ts_code, columns = factor names.
        """
        factor_list = _to_factor_list(factors)
        max_window = max(
            (_FACTOR_REGISTRY.get(f, {}).get("window", 1) for f in factor_list), default=1
        )
        # Use generous lookback so rolling windows are fully populated
        days_back = max(max_window * 2 + 60, _MAX_LOOKBACK_DAYS)
        start_date = _date_yyyymmdd_to_start(date, days_back)

        price_df = self._stock.price(
            codes=universe,
            start_date=start_date,
            end_date=date,
        )
        if price_df is None or price_df.empty:
            return pd.DataFrame()

        results: dict[str, pd.Series] = {}
        for factor in factor_list:
            try:
                results[factor] = _compute_factor(price_df, factor)
            except Exception:  # noqa: BLE001
                results[factor] = pd.Series(dtype=float, name=factor)

        return pd.DataFrame(results).rename_axis("ts_code")

    def history(
        self,
        factors: str | list[str],
        *,
        start_date: str,
        end_date: str,
        universe: list[str] | None = None,
        freq: Literal["D", "W", "M"] = "D",
    ) -> pd.DataFrame:
        """Factor value panel over time (long format: ts_code, trade_date, + factors).

        Computes rolling cross-sections; may be slow for large date ranges.
        """
        factor_list = _to_factor_list(factors)
        max_window = max(
            (_FACTOR_REGISTRY.get(f, {}).get("window", 1) for f in factor_list), default=1
        )
        # Extend start_date back to warm up rolling windows
        extended_start = _date_yyyymmdd_to_start(start_date, max_window * 2 + 60)

        price_df = self._stock.price(
            codes=universe,
            start_date=extended_start,
            end_date=end_date,
        )
        if price_df is None or price_df.empty:
            return pd.DataFrame()

        if "trade_date" not in price_df.columns:
            return pd.DataFrame()

        all_dates = sorted(d for d in price_df["trade_date"].unique() if str(d) >= start_date)

        records: list[dict] = []
        for date in all_dates:
            sub = price_df[price_df["trade_date"] <= date]
            for factor in factor_list:
                try:
                    vals = _compute_factor(sub, factor)
                    for code, val in vals.items():
                        records.append(
                            {"trade_date": date, "ts_code": code, "factor": factor, "value": val}
                        )
                except Exception:  # noqa: BLE001
                    pass

        return pd.DataFrame(records)

    # ------------------------------------------------------------------
    # 2. RANKING & NORMALIZATION
    # ------------------------------------------------------------------

    def rank(
        self,
        factor: str,
        *,
        date: str,
        universe: list[str] | None = None,
        method: Literal["percentile", "zscore", "rank"] = "percentile",
        neutralize_by: list[Literal["industry", "size"]] | None = None,
    ) -> pd.DataFrame:
        """Cross-sectional rank/score within the universe.

        Returns DataFrame: ts_code, {factor}_rank.
        """
        snap = self.snapshot(factors=[factor], date=date, universe=universe)
        if snap.empty or factor not in snap.columns:
            return pd.DataFrame()
        series = snap[factor].dropna()
        if method == "percentile":
            ranked = series.rank(pct=True)
        elif method == "zscore":
            ranked = (series - series.mean()) / series.std()
        else:
            ranked = series.rank()
        return ranked.rename(f"{factor}_rank").reset_index()

    # ------------------------------------------------------------------
    # 3. PORTFOLIO CONSTRUCTION TOOLS
    # ------------------------------------------------------------------

    def exposure(
        self,
        universe: list[str],
        factors: list[str],
        *,
        date: str,
        normalize: bool = True,
    ) -> pd.DataFrame:
        """Factor exposure matrix (z-scored). Rows = ts_code, columns = factors."""
        snap = self.snapshot(factors=factors, date=date, universe=universe)
        if snap.empty:
            return snap
        if normalize:
            snap = (snap - snap.mean()) / snap.std()
        return snap

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
        """Declarative multi-factor stock screen.

        ``rules`` supports two calling conventions:
        - Percentile bounds (Protocol style): ``{"momentum_1m": (0.7, None)}``
          meaning keep stocks with factor rank in [0.7, 1.0].
        - Operator style: ``{"pe_ttm": ("<", 20)}`` — first element is a
          comparison string (``"<"``, ``"<="``, ``">"``, ``">="``, ``"=="``).
        """
        factors = list(rules.keys())
        snap = self.snapshot(factors=factors, date=date, universe=universe)
        if snap.empty:
            return snap

        mask = pd.Series(True, index=snap.index)
        for factor, bounds in rules.items():
            if factor not in snap.columns:
                continue
            col = snap[factor]

            if isinstance(bounds[0], str):
                # Operator style: (op, threshold)
                op, threshold = bounds[0], bounds[1]
                if op == "<":
                    mask &= col < threshold
                elif op == "<=":
                    mask &= col <= threshold
                elif op == ">":
                    mask &= col > threshold
                elif op == ">=":
                    mask &= col >= threshold
                elif op == "==":
                    mask &= col == threshold
            else:
                # Percentile style: (min_pct, max_pct)
                pct_ranks = col.rank(pct=True)
                lo, hi = bounds
                if lo is not None:
                    mask &= pct_ranks >= lo
                if hi is not None:
                    mask &= pct_ranks <= hi

        result = snap[mask]
        if sort_by and sort_by in result.columns:
            result = result.sort_values(sort_by, ascending=ascending)
        if top_n is not None:
            result = result.head(top_n)
        return result.reset_index()

    def quantile_portfolios(
        self,
        factor: str,
        *,
        date: str,
        n_quantiles: int = 5,
        universe: list[str] | None = None,
    ) -> pd.DataFrame:
        """Assign each stock to a quantile bucket (Q1 = bottom, Qn = top).

        Returns DataFrame: ts_code, {factor}, quantile.
        """
        snap = self.snapshot(factors=[factor], date=date, universe=universe)
        if snap.empty or factor not in snap.columns:
            return pd.DataFrame()
        series = snap[factor].dropna()
        labels = [f"Q{i + 1}" for i in range(n_quantiles)]
        snap = snap.loc[series.index].copy()
        snap["quantile"] = pd.qcut(series, q=n_quantiles, labels=labels, duplicates="drop")
        return snap.reset_index()

    # ------------------------------------------------------------------
    # 4. ANALYTICS (factor diagnostics)
    # ------------------------------------------------------------------

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
        """Information Coefficient time series.

        IC = cross-sectional rank correlation between factor values and
        subsequent ``forward_returns_period``-day stock returns.

        Returns DataFrame: trade_date, ic, factor_name, forward_period.
        """
        hist = self.history(
            factors=[factor],
            start_date=start_date,
            end_date=end_date,
            universe=universe,
        )
        if hist.empty:
            return pd.DataFrame()

        price_df = self._stock.price(
            codes=universe,
            start_date=start_date,
            end_date=end_date,
        )
        if price_df is None or price_df.empty or "trade_date" not in price_df.columns:
            return pd.DataFrame()

        close_wide = _long_to_wide(price_df, "close")
        if close_wide.empty:
            return pd.DataFrame()

        fwd_returns = close_wide.pct_change(periods=forward_returns_period).shift(
            -forward_returns_period
        )

        all_dates = sorted(hist["trade_date"].unique())
        records: list[dict] = []
        for date in all_dates:
            if date not in fwd_returns.index:
                continue
            day_hist = hist[(hist["trade_date"] == date) & (hist["factor"] == factor)]
            if day_hist.empty:
                continue
            day_factors = day_hist.set_index("ts_code")["value"].dropna()
            day_fwd = fwd_returns.loc[date].dropna()
            common = day_factors.index.intersection(day_fwd.index)
            if len(common) < 5:
                continue
            f_vals = day_factors.loc[common]
            r_vals = day_fwd.loc[common]
            ic = f_vals.rank().corr(r_vals.rank()) if method == "spearman" else f_vals.corr(r_vals)
            records.append(
                {
                    "trade_date": date,
                    "ic": ic,
                    "factor_name": factor,
                    "forward_period": forward_returns_period,
                }
            )

        return pd.DataFrame(records)

    def factor_return(
        self,
        factor: str,
        *,
        start_date: str,
        end_date: str,
        universe: list[str] | None = None,
        long_short: bool = True,
    ) -> pd.DataFrame:
        """Factor return time series (top quintile minus bottom quintile if long_short).

        Returns DataFrame: trade_date, factor_return, cumulative_return.
        """
        hist = self.history(
            factors=[factor],
            start_date=start_date,
            end_date=end_date,
            universe=universe,
        )
        if hist.empty:
            return pd.DataFrame()

        price_df = self._stock.price(
            codes=universe,
            start_date=start_date,
            end_date=end_date,
        )
        if price_df is None or price_df.empty:
            return pd.DataFrame()

        close_wide = _long_to_wide(price_df, "close")
        if close_wide.empty:
            return pd.DataFrame()

        daily_rets = close_wide.pct_change()
        all_dates = sorted(hist["trade_date"].unique())
        records: list[dict] = []
        for date in all_dates:
            if date not in daily_rets.index:
                continue
            day_hist = hist[(hist["trade_date"] == date) & (hist["factor"] == factor)]
            if day_hist.empty:
                continue
            day_factors = day_hist.set_index("ts_code")["value"].dropna()
            n = len(day_factors)
            if n < 4:
                continue
            top_n = max(1, n // 5)
            long_stocks = day_factors.nlargest(top_n).index
            next_rets = daily_rets.loc[date]
            long_ret = next_rets.reindex(long_stocks).mean()
            if long_short:
                short_stocks = day_factors.nsmallest(top_n).index
                short_ret = next_rets.reindex(short_stocks).mean()
                port_ret = long_ret - short_ret
            else:
                port_ret = long_ret
            records.append({"trade_date": date, "factor_return": port_ret})

        if not records:
            return pd.DataFrame()

        result = pd.DataFrame(records)
        result["cumulative_return"] = (1 + result["factor_return"].fillna(0)).cumprod() - 1
        return result

    # ------------------------------------------------------------------
    # Meta
    # ------------------------------------------------------------------

    def list_factors(self) -> list[str]:
        """Names of all registered factors."""
        return list(_FACTOR_REGISTRY.keys())

    def describe(self, factor: str) -> dict[str, object]:
        """Metadata for a registered factor."""
        if factor not in _FACTOR_REGISTRY:
            raise ValueError(
                f"Unknown factor: {factor!r}. Call list_factors() to see available factors."
            )
        return dict(_FACTOR_REGISTRY[factor])

    def available_dates(self, factor: str | None = None) -> list[str]:
        return []

    def latest_date(self, factor: str | None = None) -> str | None:
        return None
