"""风险指标和筛选工具执行器."""

from __future__ import annotations
import polars as pl
from mcp_server.auto_register import tool_registry


# ========== Risk Metrics Tools ==========

@tool_registry.register(description="波动率（年化标准差）。衡量价格波动程度，用于风险评估。", category="risk")
def volatility(data: pl.DataFrame, column: str, window: int = 20) -> pl.Series:
    """波动率（年化标准差）."""
    return data[column].rolling_std(window_size=window) * (252 ** 0.5)


@tool_registry.register(description="最大回撤。衡量从峰值到谷值的最大跌幅，用于评估下行风险。", category="risk")
def max_drawdown(data: pl.DataFrame, column: str, window: int = 60) -> pl.Series:
    """最大回撤."""
    rolling_max = data[column].rolling_max(window_size=window)
    drawdown = (data[column] - rolling_max) / rolling_max
    return drawdown.rolling_min(window_size=window)
