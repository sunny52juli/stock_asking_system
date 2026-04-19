"""Technical 工具执行器 - 技术指标类工具."""

from __future__ import annotations
import polars as pl
from mcp_server.auto_register import tool_registry


@tool_registry.register(description="相对强弱指标 RSI。衡量价格变动速度和幅度，0-100之间。>70 超买，<30 超卖。", category="technical")
def rsi(data: pl.DataFrame, column: str = "close", window: int = 14) -> pl.Series:
    """相对强弱指标 RSI."""
    delta = data[column].diff()
    gain = delta.clip(lower_bound=0).rolling_mean(window_size=window)
    loss = (-delta.clip(upper_bound=0)).rolling_mean(window_size=window)
    # Avoid division by zero
    rs = gain / loss.replace(0, None).fill_null(1e-10)
    return 100 - (100 / (1 + rs))


@tool_registry.register(description="MACD 指标。趋势跟踪动量指标，显示两条移动平均线的关系。", category="technical")
def macd(data: pl.DataFrame, column: str = "close", fast: int = 12, slow: int = 26, signal: int = 9) -> pl.Series:
    """MACD 指标."""
    ema_fast = data[column].ewm_mean(span=fast)
    ema_slow = data[column].ewm_mean(span=slow)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm_mean(span=signal)
    return macd_line - signal_line


@tool_registry.register(description="KDJ 随机指标。用于判断超买超卖状态和趋势反转。", category="technical")
def kdj(data: pl.DataFrame, high: str = "high", low: str = "low", close: str = "close", window: int = 9) -> pl.Series:
    """KDJ 随机指标."""
    lowest_low = data[low].rolling_min(window_size=window)
    highest_high = data[high].rolling_max(window_size=window)
    rsv = (data[close] - lowest_low) / (highest_high - lowest_low).replace(0, None).fill_null(1e-10) * 100
    k = rsv.ewm_mean(com=2)
    d = k.ewm_mean(com=2)
    j = 3 * k - 2 * d
    return j


@tool_registry.register(description="平均真实波幅 ATR。衡量市场波动性，用于设置止损位。", category="technical")
def atr(data: pl.DataFrame, high: str = "high", low: str = "low", close: str = "close", window: int = 14) -> pl.Series:
    """平均真实波幅 ATR."""
    result = data.with_columns([
        (pl.col(high) - pl.col(low)).alias('tr1'),
        (pl.col(high) - pl.col(close).shift(1)).abs().alias('tr2'),
        (pl.col(low) - pl.col(close).shift(1)).abs().alias('tr3'),
    ]).with_columns([
        pl.max_horizontal(['tr1', 'tr2', 'tr3']).alias('tr')
    ]).with_columns([
        pl.col('tr').rolling_mean(window_size=window).alias('atr')
    ])
    return result['atr']


@tool_registry.register(description="能量潮 OBV。通过成交量变化预测价格走势。", category="technical")
def obv(data: pl.DataFrame, close: str = "close", vol: str = "vol") -> pl.Series:
    """能量潮 OBV."""
    result = data.with_columns([
        pl.when(pl.col(close).diff() > 0).then(pl.col(vol))
          .when(pl.col(close).diff() < 0).then(-pl.col(vol))
          .otherwise(0).alias('obv_daily')
    ]).with_columns([
        pl.col('obv_daily').cum_sum().alias('obv')
    ])
    return result['obv']


@tool_registry.register(description="股票最大振幅。衡量价格波动范围。", category="technical")
def amplitude(data: pl.DataFrame, high: str = "high", low: str = "low", pre_close: str = "pre_close", window: int = 5) -> pl.Series:
    """股票最大振幅."""
    amplitude_daily = (data[high] - data[low]) / data[pre_close].replace(0, None).fill_null(1e-10) * 100
    return amplitude_daily.rolling_max(window_size=window)


@tool_registry.register(description="成交量比率。当前成交量与平均成交量的比值。", category="technical")
def volume_ratio(data: pl.DataFrame, column: str = "vol", window: int = 5) -> pl.Series:
    """成交量比率."""
    avg_vol = data[column].rolling_mean(window_size=window)
    return data[column] / avg_vol.replace(0, None).fill_null(1e-10)


@tool_registry.register(description="突破判断：当日收盘价是否高于近期最高价。用于识别突破信号。", category="technical")
def close_above_high(data: pl.DataFrame, column: str = "close", high_column: str = "high", window: int = 20) -> pl.Series:
    """突破判断：当日收盘价是否高于近期最高价."""
    recent_high = data[high_column].rolling_max(window_size=window)
    return (data[column] > recent_high).cast(pl.Int32)
