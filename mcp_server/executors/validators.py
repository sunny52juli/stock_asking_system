"""工具参数验证器 - 基于自动验证 + 手动补充.

from .feature_tools import (
from .math_tools import (
from .risk_tools import (
from .statistical_tools import (
from .technical_tools import (
from .time_series_tools import (
使用 Pydantic 进行类型检查，通过装饰器自动生成验证规则。
对于有特殊约束的工具，保留手动验证器。
"""

from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, Field, model_validator

from .auto_validator import validate_tool_params_auto


# ==================== 手动验证器（特殊约束）====================

class ZscoreNormalizeParams(BaseModel):
    """zscore_normalize 参数验证 - 需要 column 或 values 至少一个."""
    column: str | None = Field(None, description="数据列名")
    values: str | None = Field(None, description="变量名")
    
    @model_validator(mode='after')
    def validate_input(self) -> 'ZscoreNormalizeParams':
        if not self.column and not self.values:
            raise ValueError("必须提供 column 或 values 参数")
        return self


# 手动验证器映射
MANUAL_VALIDATORS = {
    "zscore_normalize": ZscoreNormalizeParams,
}


# ==================== 工具函数映射表 ====================
# 从各个工具模块导入函数，建立名称到函数的映射

def _get_tool_functions() -> dict[str, Callable]:
    """获取所有工具函数的映射."""
        abs_value,
        log_transform,
        sqrt_transform,
        power_transform,
        rank_normalize,
        zscore_normalize,
    )
        rolling_mean,
        pct_change,
        rolling_std,
        rolling_max,
        rolling_min,
        ewm,
        price_change,
        high_in_period,
    )
        rsi,
        macd,
        kdj,
        atr,
        obv,
        amplitude,
        volume_ratio,
        close_above_high,
        beta,
        alpha,
        outperform_rate,
        correlation_with_index,
        tracking_error,
        information_ratio,
    )
        correlation,
        skewness,
        kurtosis,
    )
        ts_rank,
        ts_argmax,
        ts_argmin,
        decay_linear,
    )
        volatility,
        max_drawdown,
    )
    
    return {
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
        
        # Index Correlation
        "beta": beta,
        "alpha": alpha,
        "outperform_rate": outperform_rate,
        "correlation_with_index": correlation_with_index,
        "tracking_error": tracking_error,
        "information_ratio": information_ratio,
        
        # Statistical & Feature Engineering
        "correlation": correlation,
        "skewness": skewness,
        "kurtosis": kurtosis,
        "ts_rank": ts_rank,
        "ts_argmax": ts_argmax,
        "ts_argmin": ts_argmin,
        "decay_linear": decay_linear,
        
        # Risk Metrics
        "volatility": volatility,
        "max_drawdown": max_drawdown,

    }


# 缓存工具函数映射（避免重复导入）
_TOOL_FUNCTIONS_CACHE: dict[str, Callable] | None = None


def _get_tool_function(tool_name: str) -> Callable | None:
    """获取工具函数."""
    global _TOOL_FUNCTIONS_CACHE
    if _TOOL_FUNCTIONS_CACHE is None:
        _TOOL_FUNCTIONS_CACHE = _get_tool_functions()
    return _TOOL_FUNCTIONS_CACHE.get(tool_name)


def validate_tool_params(tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """验证工具参数（自动从函数签名生成验证规则）.
    
    Args:
        tool_name: 工具名称
        params: 原始参数字典
        
    Returns:
        验证后的参数字典（未注册的直接返回）
        
    Raises:
        ValueError: 参数验证失败
    """
    # 1. 检查是否有手动验证器（特殊约束）
    manual_validator = MANUAL_VALIDATORS.get(tool_name)
    if manual_validator:
        try:
            validated = manual_validator(**params)
            return validated.model_dump(exclude_none=True)
        except Exception as e:
            error_details = []
            if hasattr(e, 'errors'):
                for error in e.errors():
                    loc = " -> ".join(str(x) for x in error.get('loc', []))
                    msg = error.get('msg', '未知错误')
                    error_details.append(f"字段 '{loc}': {msg}")
            
            if error_details:
                raise ValueError(
                    f"工具 '{tool_name}' 参数验证失败:\n" + "\n".join(error_details)
                ) from e
            else:
                raise ValueError(f"工具 '{tool_name}' 参数验证失败: {e}") from e
    
    # 2. 使用自动验证（从函数签名生成）
    tool_func = _get_tool_function(tool_name)
    
    if tool_func is None:
        # 未知工具，跳过验证
        return params
    
    # 使用自动验证器
    return validate_tool_params_auto(tool_func, params)
