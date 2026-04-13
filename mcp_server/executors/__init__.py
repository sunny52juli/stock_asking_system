"""执行器统一注册中心.

所有工具执行器在此集中注册，提供统一的调用接口。
"""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd

# 导入所有执行器模块
from .math_tools import (
    abs_value,
    log_transform,
    sqrt_transform,
    power_transform,
    rank_normalize,
    zscore_normalize,
)
from .time_series_tools import (
    rolling_mean,
    pct_change,
    rolling_std,
    rolling_max,
    rolling_min,
    ewm,
    price_change,
    high_in_period,
)
from .technical_tools import (
    rsi,
    macd,
    kdj,
    atr,
    obv,
    amplitude,
    volume_ratio,
    close_above_high,
)
from .other_tools import (
    correlation,
    skewness,
    kurtosis,
    ts_rank,
    ts_argmax,
    ts_argmin,
    decay_linear,
    volatility,
    max_drawdown,
    filter_by_industry,
    filter_by_market,
)

# 工具函数注册表
TOOL_FUNCTIONS: dict[str, Callable[..., pd.Series]] = {
    # Math
    "abs_value": abs_value,
    "log_transform": log_transform,
    "sqrt_transform": sqrt_transform,
    "power_transform": power_transform,
    "rank_normalize": rank_normalize,
    "zscore_normalize": zscore_normalize,
    
    # Time Series
    "rolling_mean": rolling_mean,
    "pct_change": pct_change,
    "rolling_std": rolling_std,
    "rolling_max": rolling_max,
    "rolling_min": rolling_min,
    "ewm": ewm,
    "price_change": price_change,
    "high_in_period": high_in_period,
    
    # Technical
    "rsi": rsi,
    "macd": macd,
    "kdj": kdj,
    "atr": atr,
    "obv": obv,
    "amplitude": amplitude,
    "volume_ratio": volume_ratio,
    "close_above_high": close_above_high,
    
    # Statistical
    "correlation": correlation,
    "skewness": skewness,
    "kurtosis": kurtosis,
    
    # Feature Engineering
    "ts_rank": ts_rank,
    "ts_argmax": ts_argmax,
    "ts_argmin": ts_argmin,
    "decay_linear": decay_linear,
    
    # Risk Metrics
    "volatility": volatility,
    "max_drawdown": max_drawdown,
    
    # Screening
    "filter_by_industry": filter_by_industry,
    "filter_by_market": filter_by_market,
}


def execute_tool(tool_name: str, **kwargs) -> pd.Series:
    """执行指定工具.
    
    Args:
        tool_name: 工具名称
        **kwargs: 工具参数（必须包含 data）
        
    Returns:
        计算结果 Series
        
    Raises:
        ValueError: 工具不存在或缺少必要参数
        Exception: 工具执行失败
    """
    if tool_name not in TOOL_FUNCTIONS:
        available = list(TOOL_FUNCTIONS.keys())
        raise ValueError(f"Unknown tool: {tool_name}. Available: {available}")
    
    if 'data' not in kwargs:
        raise ValueError(f"Tool '{tool_name}' requires 'data' parameter")
    
    try:
        func = TOOL_FUNCTIONS[tool_name]
        return func(**kwargs)
    except ValueError:
        # ValueError 直接抛出，不包装
        raise
    except Exception as e:
        raise Exception(f"Tool '{tool_name}' failed: {e}") from e


def get_available_tools() -> list[str]:
    """获取所有可用工具列表."""
    return list(TOOL_FUNCTIONS.keys())
