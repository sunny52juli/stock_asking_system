"""统计工具执行器 - 相关系数、偏度、峰度等."""

from __future__ import annotations
import polars as pl
from mcp_server.auto_register import tool_registry


@tool_registry.register(description="滚动相关系数。衡量两个变量之间的线性关系强度。", category="statistical")
def correlation(data: pl.DataFrame, x: str, y: str, window: int = 20) -> pl.Series:
    """滚动相关系数 - 纯polars实现."""
    # 简单实现：逐窗口计算
    corr_values = []
    for i in range(len(data)):
        start = max(0, i - window + 1)
        window_data = data[start:i+1]
        if len(window_data) >= 2:
            corr_matrix = window_data.select([x, y]).corr()
            corr_val = corr_matrix[x][1] if x != y else corr_matrix[x][0]
            corr_values.append(corr_val)
        else:
            corr_values.append(None)
    return pl.Series(corr_values)


@tool_registry.register(description="偏度。衡量数据分布的不对称性。", category="statistical")
def skewness(data: pl.DataFrame, column: str, window: int = 20) -> pl.Series:
    """偏度."""
    # 使用 rolling_map on Series
    return data[column].rolling_map(lambda s: s.skew(), window_size=window)


@tool_registry.register(description="峰度。衡量数据分布的尖锐程度。", category="statistical")
def kurtosis(data: pl.DataFrame, column: str, window: int = 20) -> pl.Series:
    """峰度."""
    # 使用 rolling_map on Series
    return data[column].rolling_map(lambda s: s.kurtosis(), window_size=window)
