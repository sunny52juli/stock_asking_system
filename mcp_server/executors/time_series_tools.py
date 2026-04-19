"""Time Series 工具执行器 - 时间序列类工具.

Uses polars for performance-critical rolling operations on stock data.
"""

from __future__ import annotations
import polars as pl
from mcp_server.auto_register import tool_registry
from utils.polars_tools import (
    rolling_mean as pl_rolling_mean,
    rolling_std as pl_rolling_std,
    pct_change as pl_pct_change,
)


@tool_registry.register(description="计算移动平均线（MA）。用于平滑价格数据，识别趋势方向。", category="time_series")
def rolling_mean(data: pl.DataFrame, column: str, window: int = 5) -> pl.Series:
    """移动平均."""
    result_df = pl_rolling_mean(data, column, window)
    return result_df[f"{column}_ma"]


@tool_registry.register(description="计算百分比变化（收益率）。用于衡量价格变动幅度。", category="time_series")
def pct_change(data: pl.DataFrame, column: str, periods: int = 1) -> pl.Series:
    """百分比变化."""
    result_df = pl_pct_change(data, column, periods)
    return result_df[f"{column}_pct"]


@tool_registry.register(description="计算滚动标准差（波动率）。用于衡量价格波动程度，值越大表示波动越剧烈。", category="time_series")
def rolling_std(data: pl.DataFrame, column: str, window: int = 20) -> pl.Series:
    """移动标准差."""
    result_df = pl_rolling_std(data, column, window)
    return result_df[f"{column}_std"]


@tool_registry.register(description="计算滚动最大值。用于识别近期高点、阻力位。", category="time_series")
def rolling_max(data: pl.DataFrame, column: str, window: int = 20) -> pl.Series:
    """移动最大值."""
    result = (
        data
        .sort(["ts_code", "trade_date"])
        .with_columns(
            pl.col(column)
            .rolling_max(window_size=window, min_periods=1)
            .over("ts_code")
            .alias(f"{column}_max")
        )
    )
    return result[f"{column}_max"]


@tool_registry.register(description="计算滚动最小值。用于识别近期低点、支撑位。", category="time_series")
def rolling_min(data: pl.DataFrame, column: str, window: int = 20) -> pl.DataFrame:
    """移动最小值."""
    return (
        data
        .sort(["ts_code", "trade_date"])
        .with_columns(
            pl.col(column)
            .rolling_min(window_size=window, min_periods=1)
            .over("ts_code")
            .alias(f"{column}_min")
        )
    )


@tool_registry.register(description="计算指数加权移动平均（EMA）。对近期数据赋予更高权重，反应更灵敏。", category="time_series")
def ewm(data: pl.DataFrame, column: str, span: int = 12) -> pl.Series:
    """指数加权移动平均."""
    return data[column].ewm_mean(span=span, adjust=True)


@tool_registry.register(description="计算价格涨幅（涨跌幅）。", category="time_series")
def price_change(data: pl.DataFrame, column: str = "close", periods: int = 1) -> pl.Series:
    """价格涨幅."""
    result_df = pl_pct_change(data, column, periods)
    new_col = f"{column}_pct"
    return result_df[new_col] if new_col in result_df.columns else result_df.to_series(0)


@tool_registry.register(description="计算近期最高价。用于判断是否突破前期高点。", category="time_series")
def high_in_period(data: pl.DataFrame, column: str = "high", window: int = 20) -> pl.Series:
    """近期最高价."""
    result = rolling_max(data, column, window)
    return result
