"""Math 工具执行器 - 数学变换类工具."""

from __future__ import annotations
import polars as pl
from mcp_server.auto_register import tool_registry


@tool_registry.register(description="计算绝对值。用于处理负值数据。参数：column=列名", category="math")
def abs_value(data: pl.DataFrame, column: str) -> pl.Series:
    """计算绝对值."""
    return data[column].abs()


@tool_registry.register(description="对数变换 log(1+x)。用于压缩数据范围，减少极端值影响。参数：column=列名", category="math")
def log_transform(data: pl.DataFrame, column: str) -> pl.Series:
    """对数变换，log(1+x)."""
    return data[column].log1p()


@tool_registry.register(description="平方根变换，保留符号。用于降低数据波动性。参数：column=列名", category="math")
def sqrt_transform(data: pl.DataFrame, column: str) -> pl.Series:
    """平方根变换，保留符号."""
    return data[column].sign() * data[column].abs().sqrt()


@tool_registry.register(description="幂次变换 x^n。用于调整数据分布形态。参数：column=列名, power=幂次(默认2)", category="math")
def power_transform(data: pl.DataFrame, column: str, power: float = 2) -> pl.Series:
    """幂次变换，x^n."""
    return data[column].pow(power)


@tool_registry.register(description="横截面排名归一化到 [0,1]。用于消除量纲影响。参数：column=列名", category="math")
def rank_normalize(data: pl.DataFrame, column: str) -> pl.Series:
    """横截面排名归一化到 [0,1]."""
    ranks = data[column].rank(method='average')
    return (ranks - 1) / (len(ranks) - 1) if len(ranks) > 1 else pl.Series([0.5])


@tool_registry.register(description="Z-score 标准化。将数据转换为均值为0、标准差为1的分布。参数：column=列名", category="math")
def zscore_normalize(data: pl.DataFrame, column: str) -> pl.Series:
    """Z-score 标准化."""
    mean = data[column].mean()
    std = data[column].std()
    if std == 0 or std is None:
        return pl.Series([0.0] * len(data))
    return (data[column] - mean) / std
