"""特征工程工具执行器 - 时间序列排名、衰减加权等.

Uses polars for performance-critical operations on stock data.
"""

from __future__ import annotations
import polars as pl
from mcp_server.auto_register import tool_registry


@tool_registry.register(description="时间序列排名。计算当前值在窗口内的排名百分比。", category="feature")
def ts_rank(data: pl.DataFrame, column: str, window: int = 10) -> pl.Series:
    """时间序列排名."""
    return (
        data[column]
        .rolling_map(lambda x: x.rank().tail(1).item() / len(x), window_size=window)
    )


@tool_registry.register(description="时间序列最大值位置。返回最大值出现在窗口内的位置。", category="feature")
def ts_argmax(data: pl.DataFrame, column: str, window: int = 10) -> pl.Series:
    """时间序列最大值位置."""
    return (
        data[column]
        .rolling_map(lambda x: x.to_numpy().argmax(), window_size=window)
    )


@tool_registry.register(description="时间序列最小值位置。返回最小值出现在窗口内的位置。", category="feature")
def ts_argmin(data: pl.DataFrame, column: str, window: int = 10) -> pl.Series:
    """时间序列最小值位置."""
    return (
        data[column]
        .rolling_map(lambda x: x.to_numpy().argmin(), window_size=window)
    )


@tool_registry.register(description="线性衰减加权平均。对近期数据赋予更高权重。", category="feature")
def decay_linear(data: pl.DataFrame, column: str, window: int = 10) -> pl.Series:
    """线性衰减加权平均."""
    weights = pl.Series(range(1, window + 1))
    return (
        data[column]
        .rolling_map(
            lambda x: (x * weights).sum() / weights.sum(),
            window_size=window
        )
    )
