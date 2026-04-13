"""Math 工具执行器 - 数学变换类工具."""

from __future__ import annotations

import numpy as np
import pandas as pd


def abs_value(data: pd.DataFrame, column: str) -> pd.Series:
    """计算绝对值."""
    result = data[column].abs()
    result.name = None
    return result


def log_transform(data: pd.DataFrame, column: str) -> pd.Series:
    """对数变换，log(1+x)."""
    return np.log1p(data[column])


def sqrt_transform(data: pd.DataFrame, column: str) -> pd.Series:
    """平方根变换，保留符号."""
    return np.sign(data[column]) * np.sqrt(np.abs(data[column]))


def power_transform(data: pd.DataFrame, column: str, power: float = 2) -> pd.Series:
    """幂次变换，x^n."""
    return np.power(data[column], power)


def rank_normalize(data: pd.DataFrame, column: str) -> pd.Series:
    """横截面排名归一化到 [0,1]."""
    return data[column].rank(pct=True)


def zscore_normalize(data: pd.DataFrame, column: str) -> pd.Series:
    """Z-score 标准化."""
    mean = data[column].mean()
    std = data[column].std()
    if std == 0:
        return pd.Series(0, index=data.index)
    return (data[column] - mean) / std
