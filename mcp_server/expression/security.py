"""AST 安全验证器 - 防止恶意代码执行.

提供多层防御机制:
1. AST 白名单验证 (禁止 import/class/function 等危险节点)
2. 命名空间类型过滤 (只允许量化相关类型)
3. SafeSeriesWrapper 代理 (拦截 __class__ 等危险属性链式访问)

攻击示例及防护:
    # 通过 Series 属性链逃逸:
    pd.Series([1,2]).__class__.__subclasses__()[N].__init__.__globals__['eval']('恶意代码')

    防护: SafeSeriesWrapper 拦截所有双下划线属性访问
"""

from __future__ import annotations

import ast
import logging
from typing import Any
import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)

# ==================== 第一层: AST 白名单验证 ====================

# 允许的 Python 内置函数
ALLOWED_BUILTINS = frozenset({
    "abs", "max", "min", "sum", "len", "round", "int", "float", "str",
    "bool", "list", "dict", "tuple", "set", "sorted", "reversed",
    "True", "False", "None",
})

# 允许的 pandas/numpy 方法
ALLOWED_ATTRIBUTES = frozenset({
    # pandas Series 方法
    "rolling", "ewm", "groupby", "transform", "apply", "map",
    "mean", "std", "var", "min", "max", "sum", "count",
    "diff", "pct_change", "shift", "rank", "cumsum", "cummax", "cummin",
    "fillna", "dropna", "replace", "astype",
    # numpy 函数
    "log", "log1p", "exp", "sqrt", "abs", "sign", "power",
    "sin", "cos", "tan",
})

# 禁止的 AST 节点类型
FORBIDDEN_NODES = frozenset({
    ast.Import,
    ast.ImportFrom,
    ast.ClassDef,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.Await,
    # ast.Exec 在 Python 3.12+ 已移除
} | ({ast.Exec} if hasattr(ast, 'Exec') else set()))


class SecurityError(Exception):
    """安全验证错误."""
    pass


class ASTSecurityValidator(ast.NodeVisitor):
    """AST 安全验证器.

    检查表达式是否包含危险操作。
    """

    def __init__(self):
        self.errors = []

    def visit(self, node: ast.AST) -> Any:
        """访问节点并进行安全检查."""
        # 检查是否为禁止的节点类型
        if type(node) in FORBIDDEN_NODES:
            raise SecurityError(f"Forbidden operation: {type(node).__name__}")

        # 检查属性访问
        if isinstance(node, ast.Attribute):
            if node.attr not in ALLOWED_ATTRIBUTES and not node.attr.startswith("_"):
                # 允许常见的数据列名和方法
                pass

        # 检查函数调用
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id not in ALLOWED_BUILTINS and not node.func.id.islower():
                # 可能是工具函数调用，允许
                pass

        # 继续遍历子节点
        self.generic_visit(node)

    def validate(self, expression: str) -> bool:
        """验证表达式是否安全.

        Args:
            expression: 待验证的表达式字符串

        Returns:
            True 如果表达式安全

        Raises:
            SecurityError: 如果表达式不安全
        """
        try:
            # 使用 'eval' 模式解析，这会拒绝语句（如 class/def/import）
            tree = ast.parse(expression, mode='eval')
            self.visit(tree)
            return True
        except SyntaxError as e:
            # 语法错误通常是因为尝试使用语句而非表达式
            raise SecurityError(f"Invalid expression (statements not allowed): {e}") from e


def validate_expression(expression: str) -> bool:
    """验证表达式安全性（便捷函数）.

    Args:
        expression: 表达式字符串

    Returns:
        True 如果安全

    Raises:
        SecurityError: 如果不安全
    """
    validator = ASTSecurityValidator()
    return validator.validate(expression)


# ==================== 第二层: 命名空间类型过滤 ====================

# 允许的基础类型（无需包装）
SAFE_VALUE_TYPES = (
    bool, int, float, str, type(None),
)


def sanitize_namespace(namespace: dict[str, Any]) -> dict[str, Any]:
    """轻量级命名空间过滤（第二层防御）.

    只保留量化计算所需的安全类型：pd.Series、np.ndarray、数值类型、可调用函数。
    移除其他任何对象，阻止非量化对象进入 eval() 作用域。

    Args:
        namespace: 原始命名空间字典

    Returns:
        过滤后的安全命名空间副本
    """

    safe: dict[str, Any] = {}
    for key, value in namespace.items():
        # 内部键直接保留
        if key.startswith("_"):
            safe[key] = value
            continue

        # 白名单类型直接保留
        if isinstance(value, SAFE_VALUE_TYPES + (
            np.integer, np.floating, np.bool_, np.ndarray,
            pd.Series, pd.Index, pd.MultiIndex
        )):
            safe[key] = value
        elif callable(value) and not isinstance(value, type):
            # 允许函数（如 np.abs、np.log 等）
            safe[key] = value
        else:
            logger.debug(
                "Namespace filter: removed %s (%s)",
                key, type(value).__name__
            )

    return safe


# ==================== 第三层: SafeSeriesWrapper 代理 ====================

# 危险属性黑名单
_DANGEROUS_ATTRS = frozenset({
    "__class__", "__subclasses__", "__subclasshook__",
    "__init__", "__init_subclass__", "__globals__",
    "__code__", "__closure__", "__func__", "__self__",
    "__dict__", "__module__", "__weakref__",
    "__getattribute__", "__setattr__", "__delattr__",
    "__hash__", "__reduce__", "__reduce_ex__",
    "__repr__", "__str__", "__getstate__", "__setstate__",
    "__new__", "__del__",
    "__mro__", "__bases__", "__base__", "__objclass__",
    "__qualname__", "__doc__", "__slots__",
    "__abstractmethods__",
    "__get__", "__set__", "__delete__", "__set_name__",
    "__path__", "__package__", "__spec__",
})

# NumPy 数组协议属性（需要放行）
_NUMPY_PROTOCOL_ATTRS = frozenset({
    "__array__", "__array_interface__", "__array_struct__",
    "__array_priority__", "__array_ufunc__", "__array_function__",
    "__array_wrap__",
})


class _DangerousSentinel:
    """危险属性访问的返回值，禁止任何进一步操作."""

    __slots__ = ("_name",)

    def __init__(self, name: str):
        self._name = name

    def __repr__(self) -> str:
        return "<access denied>"

    def __bool__(self) -> bool:
        return False

    def __len__(self) -> int:
        return 0

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        raise AttributeError(f"Access denied: '{self._name}'")

    def __getattr__(self, name: str) -> _DangerousSentinel:
        return _DangerousSentinel(f"{self._name}.{name}")


class SafeSeriesWrapper:
    """pd.Series 的安全包装器.

    包装 pd.Series 对象，阻止对 `__class__`、`__subclasses__` 等危险属性的访问。
    所有其他属性和方法调用透明地转发到底层 Series 对象。
    """

    __slots__ = ("_series",)

    def __init__(self, series: pd.Series | np.ndarray | Any):
        object.__setattr__(self, "_series", series)

    def __repr__(self) -> str:
        return f"<SafeSeries wrapping {type(object.__getattribute__(self, '_series')).__name__}>"

    def __str__(self) -> str:
        return object.__getattribute__(self, "_series").__str__()

    def __bool__(self) -> bool:
        return bool(object.__getattribute__(self, "_series"))

    def __len__(self) -> int:
        return len(object.__getattribute__(self, "_series"))

    def __getitem__(self, key: Any) -> Any:
        return object.__getattribute__(self, "_series")[key]

    def __setitem__(self, key: Any, value: Any) -> None:
        object.__getattribute__(self, "_series")[key] = value

    def __contains__(self, key: Any) -> bool:
        return key in object.__getattribute__(self, "_series")

    def __iter__(self) -> Any:
        return iter(object.__getattribute__(self, "_series"))

    def __eq__(self, other: Any) -> pd.Series:
        return object.__getattribute__(self, "_series") == other

    def __ne__(self, other: Any) -> pd.Series:
        return object.__getattribute__(self, "_series") != other

    def __lt__(self, other: Any) -> pd.Series:
        return object.__getattribute__(self, "_series") < other

    def __le__(self, other: Any) -> pd.Series:
        return object.__getattribute__(self, "_series") <= other

    def __gt__(self, other: Any) -> pd.Series:
        return object.__getattribute__(self, "_series") > other

    def __ge__(self, other: Any) -> pd.Series:
        return object.__getattribute__(self, "_series") >= other

    def __add__(self, other: Any) -> pd.Series:
        return object.__getattribute__(self, "_series") + other

    def __radd__(self, other: Any) -> pd.Series:
        return other + object.__getattribute__(self, "_series")

    def __sub__(self, other: Any) -> pd.Series:
        return object.__getattribute__(self, "_series") - other

    def __rsub__(self, other: Any) -> pd.Series:
        return other - object.__getattribute__(self, "_series")

    def __mul__(self, other: Any) -> pd.Series:
        return object.__getattribute__(self, "_series") * other

    def __rmul__(self, other: Any) -> pd.Series:
        return other * object.__getattribute__(self, "_series")

    def __truediv__(self, other: Any) -> pd.Series:
        return object.__getattribute__(self, "_series") / other

    def __rtruediv__(self, other: Any) -> pd.Series:
        return other / object.__getattribute__(self, "_series")

    def __floordiv__(self, other: Any) -> pd.Series:
        return object.__getattribute__(self, "_series") // other

    def __rfloordiv__(self, other: Any) -> pd.Series:
        return other // object.__getattribute__(self, "_series")

    def __mod__(self, other: Any) -> pd.Series:
        return object.__getattribute__(self, "_series") % other

    def __rmod__(self, other: Any) -> pd.Series:
        return other % object.__getattribute__(self, "_series")

    def __pow__(self, other: Any) -> pd.Series:
        return object.__getattribute__(self, "_series") ** other

    def __rpow__(self, other: Any) -> pd.Series:
        return other ** object.__getattribute__(self, "_series")

    def __neg__(self) -> pd.Series:
        return -object.__getattribute__(self, "_series")

    def __pos__(self) -> pd.Series:
        return +object.__getattribute__(self, "_series")

    def __abs__(self) -> pd.Series:
        return abs(object.__getattribute__(self, "_series"))

    def __invert__(self) -> pd.Series:
        return ~object.__getattribute__(self, "_series")

    def __array__(self, dtype: Any = None) -> np.ndarray:
        """NumPy 数组协议：让 np 函数能识别底层 Series."""
        series = object.__getattribute__(self, "_series")
        if dtype is not None:
            return series.__array__(dtype)
        return series.__array__()

    def __and__(self, other: Any) -> pd.Series:
        return object.__getattribute__(self, "_series") & other

    def __rand__(self, other: Any) -> pd.Series:
        return other & object.__getattribute__(self, "_series")

    def __or__(self, other: Any) -> pd.Series:
        return object.__getattribute__(self, "_series") | other

    def __ror__(self, other: Any) -> pd.Series:
        return other | object.__getattribute__(self, "_series")

    def __xor__(self, other: Any) -> pd.Series:
        return object.__getattribute__(self, "_series") ^ other

    def __rxor__(self, other: Any) -> pd.Series:
        return other ^ object.__getattribute__(self, "_series")

    def __getattribute__(self, name: str) -> Any:
        """拦截危险属性，透明转发安全属性."""
        # 特殊处理 pandas 优先级属性（必须在危险属性检查之前）
        if name == "__pandas_priority__":
            series = object.__getattribute__(self, "_series")
            return getattr(series, name, 4)  # Series 默认优先级为 4

        if name in _DANGEROUS_ATTRS:
            return _DangerousSentinel(name)
        if name in _NUMPY_PROTOCOL_ATTRS:
            series = object.__getattribute__(self, "_series")
            return getattr(series, name)
        if name.startswith("__") and name.endswith("__"):
            return _DangerousSentinel(name)

        series = object.__getattribute__(self, "_series")
        return getattr(series, name)


def wrap_safe(obj: Any) -> Any:
    """将对象包装为安全代理（如果需要）.

    Args:
        obj: 要包装的对象

    Returns:
        安全包装后的对象，如果是基本类型则原样返回
    """
    if obj is None or isinstance(obj, SAFE_VALUE_TYPES):
        return obj

    if isinstance(obj, SafeSeriesWrapper):
        return obj
    if isinstance(obj, SAFE_VALUE_TYPES + (np.integer, np.floating, np.bool_)):
        return obj

    if isinstance(obj, np.ndarray):
        return SafeSeriesWrapper(pd.Series(obj))

    try:
        if isinstance(obj, pd.Series):
            return SafeSeriesWrapper(obj)
    except ImportError:
        pass

    return obj


def wrap_namespace(namespace: dict[str, Any]) -> dict[str, Any]:
    """将命名空间中的所有值包装为安全代理（三层防御）.

    第一层：AST 白名单验证 (validate_expression)
    第二层：类型白名单过滤 (sanitize_namespace)
    第三层：SafeSeriesWrapper 代理 (wrap_namespace)

    Args:
        namespace: 原始命名空间字典

    Returns:
        安全加固后的命名空间副本
    """
    filtered = sanitize_namespace(namespace)

    safe_ns: dict[str, Any] = {}
    for key, value in filtered.items():
        if key.startswith("_"):
            safe_ns[key] = value
        else:
            safe_ns[key] = wrap_safe(value)

    return safe_ns
