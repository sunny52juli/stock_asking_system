"""Technical 工具执行器 - 技术指标类工具."""

from __future__ import annotations

import pandas as pd


def rsi(data: pd.DataFrame, column: str = "close", window: int = 14) -> pd.Series:
    """相对强弱指标 RSI."""
    delta = data[column].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def macd(data: pd.DataFrame, column: str = "close", fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    """MACD 指标."""
    ema_fast = data[column].ewm(span=fast).mean()
    ema_slow = data[column].ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    return macd_line - signal_line


def kdj(data: pd.DataFrame, high: str = "high", low: str = "low", close: str = "close", window: int = 9) -> pd.Series:
    """KDJ 随机指标."""
    lowest_low = data[low].rolling(window=window).min()
    highest_high = data[high].rolling(window=window).max()
    rsv = (data[close] - lowest_low) / (highest_high - lowest_low) * 100
    k = rsv.ewm(com=2).mean()
    d = k.ewm(com=2).mean()
    j = 3 * k - 2 * d
    return j


def atr(data: pd.DataFrame, high: str = "high", low: str = "low", close: str = "close", window: int = 14) -> pd.Series:
    """平均真实波幅 ATR."""
    tr1 = data[high] - data[low]
    tr2 = abs(data[high] - data[close].shift())
    tr3 = abs(data[low] - data[close].shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=window).mean()


def obv(data: pd.DataFrame, close: str = "close", vol: str = "vol") -> pd.Series:
    """能量潮 OBV."""
    close_diff = data[close].diff()
    obv = pd.Series(0, index=data.index, dtype=float)
    obv[close_diff > 0] = data[vol][close_diff > 0]
    obv[close_diff < 0] = -data[vol][close_diff < 0]
    return obv.cumsum()


def amplitude(data: pd.DataFrame, high: str = "high", low: str = "low", pre_close: str = "pre_close", window: int = 5) -> pd.Series:
    """股票最大振幅."""
    amplitude_daily = (data[high] - data[low]) / data[pre_close] * 100
    return amplitude_daily.rolling(window=window).max()


def volume_ratio(data: pd.DataFrame, column: str = "vol", window: int = 5) -> pd.Series:
    """成交量比率."""
    avg_vol = data[column].rolling(window=window).mean()
    return data[column] / avg_vol


def close_above_high(data: pd.DataFrame, column: str = "close", high_column: str = "high", window: int = 20) -> pd.Series:
    """突破判断：当日收盘价是否高于近期最高价."""
    recent_high = data[high_column].rolling(window=window).max()
    return (data[column] > recent_high).astype(int)
