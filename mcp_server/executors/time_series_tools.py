"""Time Series 工具执行器 - 时间序列类工具."""

from __future__ import annotations

import pandas as pd


def rolling_mean(data: pd.DataFrame, column: str, window: int = 5) -> pd.Series:
    """移动平均."""
    return data[column].rolling(window=window).mean()


def pct_change(data: pd.DataFrame, column: str, periods: int = 1) -> pd.Series:
    """百分比变化."""
    return data[column].pct_change(periods=periods)


def rolling_std(data: pd.DataFrame, column: str, window: int = 20) -> pd.Series:
    """移动标准差."""
    return data[column].rolling(window=window).std()


def rolling_max(data: pd.DataFrame, column: str, window: int = 20) -> pd.Series:
    """移动最大值."""
    return data[column].rolling(window=window).max()


def rolling_min(data: pd.DataFrame, column: str, window: int = 20) -> pd.Series:
    """移动最小值."""
    return data[column].rolling(window=window).min()


def ewm(data: pd.DataFrame, column: str, span: int = 12) -> pd.Series:
    """指数加权移动平均."""
    return data[column].ewm(span=span).mean()


def price_change(data: pd.DataFrame, column: str = "close", periods: int = 1) -> pd.Series:
    """价格涨幅."""
    return data[column].pct_change(periods=periods)


def high_in_period(data: pd.DataFrame, column: str = "high", window: int = 20) -> pd.Series:
    """近期最高价."""
    return data[column].rolling(window=window).max()
