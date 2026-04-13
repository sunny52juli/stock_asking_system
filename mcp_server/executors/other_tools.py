"""Statistical、Feature Engineering、Risk Metrics、Screening 工具执行器."""

from __future__ import annotations

import pandas as pd


# ========== Statistical Tools ==========

def correlation(data: pd.DataFrame, x: str, y: str, window: int = 20) -> pd.Series:
    """滚动相关系数."""
    return data[x].rolling(window=window).corr(data[y])


def skewness(data: pd.DataFrame, column: str, window: int = 20) -> pd.Series:
    """偏度."""
    return data[column].rolling(window=window).skew()


def kurtosis(data: pd.DataFrame, column: str, window: int = 20) -> pd.Series:
    """峰度."""
    return data[column].rolling(window=window).kurt()


# ========== Feature Engineering Tools ==========

def ts_rank(data: pd.DataFrame, column: str, window: int = 10) -> pd.Series:
    """时间序列排名."""
    return data[column].rolling(window=window).apply(lambda x: pd.Series(x).rank().iloc[-1] / len(x), raw=False)


def ts_argmax(data: pd.DataFrame, column: str, window: int = 10) -> pd.Series:
    """时间序列最大值位置."""
    return data[column].rolling(window=window).apply(lambda x: x.argmax(), raw=True)


def ts_argmin(data: pd.DataFrame, column: str, window: int = 10) -> pd.Series:
    """时间序列最小值位置."""
    return data[column].rolling(window=window).apply(lambda x: x.argmin(), raw=True)


def decay_linear(data: pd.DataFrame, column: str, window: int = 10) -> pd.Series:
    """线性衰减加权平均."""
    weights = pd.Series(range(1, window + 1))
    return data[column].rolling(window=window).apply(lambda x: (x * weights.values).sum() / weights.sum(), raw=True)


# ========== Risk Metrics Tools ==========

def volatility(data: pd.DataFrame, column: str, window: int = 20) -> pd.Series:
    """波动率（年化标准差）."""
    return data[column].rolling(window=window).std() * (252 ** 0.5)


def max_drawdown(data: pd.DataFrame, column: str, window: int = 60) -> pd.Series:
    """最大回撤."""
    rolling_max = data[column].rolling(window=window).max()
    drawdown = (data[column] - rolling_max) / rolling_max
    return drawdown.rolling(window=window).min()


# ========== Screening Tools ==========

def filter_by_industry(data: pd.DataFrame, industry: str) -> pd.Series:
    """按行业筛选."""
    if "industry" not in data.columns:
        raise ValueError("Data does not contain 'industry' column")
    return (data["industry"] == industry).astype(int)


def filter_by_market(data: pd.DataFrame, market: str) -> pd.Series:
    """按市场筛选."""
    if "ts_code" not in data.columns:
        raise ValueError("Data does not contain 'ts_code' column")
    # 根据 ts_code 后缀判断市场
    market_map = {"sh": ".SH", "sz": ".SZ", "bj": ".BJ"}
    suffix = market_map.get(market.lower(), f".{market.upper()}")
    return data["ts_code"].str.endswith(suffix).astype(int)
