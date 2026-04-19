"""导入白名单和安全函数检查.

定义允许在表达式中调用的函数和数据结构.
"""

from __future__ import annotations

# 允许在表达式中直接调用的函数名
ALLOWED_CALLABLES: set[str] = {
    # 内置函数
    "abs",
    "max",
    "min",
    "sum",
    "pow",
    "round",
    "divmod",
    "len",
    "int",
    "float",
    "str",
    "bool",
    "zip",
    "enumerate",
    "range",
    "sorted",
    "reversed",
    "any",
    "all",
    "map",
    "filter",
    "isinstance",
    "issubclass",
    "hasattr",
    # 数学/数值函数 (通过 namespace 提供)
    "sign",
    "clip",
    "where",
    "rank",
    "zscore",
    "percentile",
    "median",
    "mean",
    "std",
    "var",
    "correlation",
    "skewness",
    "kurtosis",
    "volatility",
    "max_drawdown",
    "ts_rank",
    "ts_argmax",
    "ts_argmin",
    "decay_linear",
    "pct_change",
    "lag",
    "delta",
    "ema",
    "ewm",
    "rolling_mean",
    "rolling_std",
    "rolling_max",
    "rolling_min",
    "rolling_sum",
    "rsi",
    "macd",
    "bollinger_position",
    "kdj",
    "atr",
    "obv",
    "log_transform",
    "sqrt_transform",
    "power_transform",
    "max_of",
    "min_of",
    "get_available_industries",
    "rank_normalize",
    "zscore_normalize",
    "corr",
    "corr_rank",
    "correlation_rank",
}

# 允许通过 np.xxx 调用的 NumPy 函数
ALLOWED_NUMPY_FUNCTIONS: set[str] = {
    "abs",
    "absolute",
    "arccos",
    "arcsin",
    "arctan",
    "arctan2",
    "cos",
    "sin",
    "tan",
    "ceil",
    "floor",
    "exp",
    "expm1",
    "log",
    "log10",
    "log1p",
    "log2",
    "sqrt",
    "square",
    "sign",
    "maximum",
    "minimum",
    "mean",
    "median",
    "std",
    "var",
    "sum",
    "prod",
    "cumsum",
    "cumprod",
    "diff",
    "roll",
    "shift",
    "where",
    "select",
    "clip",
    "isnan",
    "isinf",
    "isfinite",
    "nan_to_num",
    "nanmean",
    "nanstd",
    "nanmin",
    "nanmax",
    "percentile",
    "quantile",
    "rank",
    "argsort",
    "argmax",
    "argmin",
    "corrcoef",
    "cov",
    "polyfit",
    "polynomial",
    "identity",
    "full",
    "zeros",
    "ones",
    "linspace",
    "arange",
    "concatenate",
    "stack",
    "vstack",
    "hstack",
    "reshape",
    "transpose",
    "ravel",
    "flatten",
    "unique",
    "intersect1d",
    "setdiff1d",
    "union1d",
    "in1d",
}


def is_callable_allowed(func_name: str, namespace: dict | None = None) -> bool:
    """检查函数名是否在白名单中.

    Args:
        func_name: 函数名
        namespace: 命名空间（用于额外验证）

    Returns:
        是否允许调用
    """
    return func_name in ALLOWED_CALLABLES


def validate_namespace(namespace: dict) -> None:
    """验证命名空间中不包含危险对象.

    Args:
        namespace: 要验证的命名空间字典

    Raises:
        ValueError: 命名空间包含危险对象
    """
    dangerous_patterns = {
        "__",  # 双下划线属性
        "eval",
        "exec",
        "compile",
        "open",
        "import",
        "globals",
        "locals",
        "vars",
        "dir",
        "getattr",
        "setattr",
        "delattr",
        "breakpoint",
        "memoryview",
        "super",
    }

    for key, value in namespace.items():
        # 检查键名
        if any(pattern in key for pattern in dangerous_patterns):
            raise ValueError(f"命名空间包含危险键名: {key}")

        # 检查值的类型
        value_type = type(value).__name__
        if (
            value_type in {"module", "type", "function", "builtin_function_or_method"}
            and key not in ALLOWED_CALLABLES
            and not key.startswith("np.")
        ):
            # 只允许特定类型的函数
            raise ValueError(f"命名空间包含未授权的可调用对象: {key} ({value_type})")
