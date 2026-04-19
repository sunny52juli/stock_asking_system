"""安全命名空间包装器.

import logging
提供两层防御，防止 eval() 沙箱逃逸：

第一层（轻量）：sanitize_namespace()
    类型白名单过滤，移除命名空间中非量化用途的对象。
    只保留 pd.Series、np.ndarray、数值类型、可调用函数。
    这是借鉴 model-4 的轻量方案，零包装开销。

第二层（深度）：wrap_namespace()
    在第一层基础上，将 pd.Series 包装为 SafeSeriesWrapper 代理对象，
    拦截 __class__、__subclasses__() 等危险属性的链式访问。

攻击示例（双层防御均可拦截）:
    # 通过 Series 属性链逃逸：
    (pd.Series([1,2]).__class__
        .__subclasses__()[N]
        .__init__.__globals__['__builtins__']['eval']('恶意代码'))

推荐使用 wrap_namespace()（双层防御），对性能敏感场景可仅用 sanitize_namespace()。
"""

from __future__ import annotations

, Any


# 允许的基础类型（无需包装）
SAFE_BUILTIN_TYPES: tuple[type, ...] = (
    bool,
    int,
    float,
    str,
    type(None),
    list,
    tuple,
    dict,
    set,
    slice,
)


# 危险属性黑名单：禁止访问这些属性以防止沙箱逃逸
_DANGEROUS_ATTRS: frozenset[str] = frozenset(
    {
        "__class__",
        "__subclasses__",
        "__subclasshook__",
        "__init__",
        "__init_subclass__",
        "__globals__",
        "__code__",
        "__closure__",
        "__func__",
        "__self__",
        "__dict__",
        "__module__",
        "__weakref__",
        "__getattribute__",
        "__setattr__",
        "__delattr__",
        "__hash__",
        "__reduce__",
        "__reduce_ex__",
        "__repr__",
        "__str__",
        "__getstate__",
        "__setstate__",
        "__new__",
        "__del__",
        # 元类相关
        "__mro__",
        "__bases__",
        "__base__",
        "__objclass__",
        "__qualname__",
        "__doc__",
        "__slots__",
        "__abstractmethods__",
        # 描述器协议
        "__get__",
        "__set__",
        "__delete__",
        "__set_name__",
        # 包导入相关
        "__path__",
        "__package__",
        "__spec__",
    }
)


def _safe_getattr(self, name: str) -> Any:
    """拦截危险属性，透明转发安全属性到底层 Series."""
    if name in _DANGEROUS_ATTRS or (name.startswith("__") and name.endswith("__")):
        return _DangerousSentinel(name)
    # 透明转发到底层 Series（使用 object.__getattribute__ 避免无限递归）
    series = object.__getattribute__(self, "_series")
    return getattr(series, name)


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
        raise AttributeError(f"access denied: '{self._name}'")

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

    def __eq__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return object.__getattribute__(self, "_series") == other

    def __ne__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return object.__getattribute__(self, "_series") != other

    def __lt__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return object.__getattribute__(self, "_series") < other

    def __le__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return object.__getattribute__(self, "_series") <= other

    def __gt__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return object.__getattribute__(self, "_series") > other

    def __ge__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return object.__getattribute__(self, "_series") >= other

    def __add__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return object.__getattribute__(self, "_series") + other

    def __radd__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return other + object.__getattribute__(self, "_series")

    def __sub__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return object.__getattribute__(self, "_series") - other

    def __rsub__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return other - object.__getattribute__(self, "_series")

    def __mul__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return object.__getattribute__(self, "_series") * other

    def __rmul__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return other * object.__getattribute__(self, "_series")

    def __truediv__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return object.__getattribute__(self, "_series") / other

    def __rtruediv__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return other / object.__getattribute__(self, "_series")

    def __floordiv__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return object.__getattribute__(self, "_series") // other

    def __rfloordiv__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return other // object.__getattribute__(self, "_series")

    def __mod__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return object.__getattribute__(self, "_series") % other

    def __rmod__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return other % object.__getattribute__(self, "_series")

    def __pow__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return object.__getattribute__(self, "_series") ** other

    def __rpow__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return other ** object.__getattribute__(self, "_series")

    def __neg__(self) -> pd.Series:
        return -object.__getattribute__(self, "_series")

    def __pos__(self) -> pd.Series:
        return +object.__getattribute__(self, "_series")

    def __abs__(self) -> pd.Series:
        return abs(object.__getattribute__(self, "_series"))

    def __invert__(self) -> pd.Series:
        return ~object.__getattribute__(self, "_series")

    def __and__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return object.__getattribute__(self, "_series") & other

    def __rand__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return other & object.__getattribute__(self, "_series")

    def __or__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return object.__getattribute__(self, "_series") | other

    def __ror__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return other | object.__getattribute__(self, "_series")

    def __xor__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return object.__getattribute__(self, "_series") ^ other

    def __rxor__(self, other: Any) -> pd.Series:  # type: ignore[type-arg]
        return other ^ object.__getattribute__(self, "_series")

    # 透明转发所有其他属性访问（包括方法）
    def __getattribute__(self, name: str) -> Any:
        return _safe_getattr(self, name)


class _SafeDataFrameWrapper:
    """pd.DataFrame 的安全包装器，阻止危险属性访问."""

    __slots__ = ("_df",)

    def __init__(self, df: pd.DataFrame):
        object.__setattr__(self, "_df", df)

    def __repr__(self) -> str:
        return f"<SafeDataFrame wrapping {type(object.__getattribute__(self, '_df')).__name__}>"

    def __getattribute__(self, name: str) -> Any:
        return _safe_getattr(self, name)


def wrap_safe(obj: Any) -> Any:
    """将对象包装为安全代理（如果需要）.

    Args:
        obj: 要包装的对象

    Returns:
        安全包装后的对象，如果是基本类型则原样返回
    """
    # 如果是基本安全类型，直接返回
    if obj is None or isinstance(obj, SAFE_BUILTIN_TYPES):
        return obj

    # 如果是已包装的对象，直接返回
    if isinstance(obj, SafeSeriesWrapper):
        return obj

    # 检查是否是数值类型

    if isinstance(obj, SAFE_BUILTIN_TYPES + (np.integer, np.floating, np.bool_)):
        return obj

    # 如果是 numpy 数组，转换为 Series 后包装
    if isinstance(obj, np.ndarray):

        return SafeSeriesWrapper(pd.Series(obj))

    # 如果是 pandas Series 或 DataFrame，包装
    try:

        if isinstance(obj, pd.Series):
            return SafeSeriesWrapper(obj)
        if isinstance(obj, pd.DataFrame):
            # DataFrame 包装
            return _SafeDataFrameWrapper(obj)
    except ImportError:
        pass

    return obj


def wrap_namespace(namespace: dict[str, Any]) -> dict[str, Any]:
    """将命名空间中的所有值包装为安全代理（双层防御）.

    第一层：调用 sanitize_namespace() 过滤非量化用途对象。
    第二层：将 pd.Series 包装为 SafeSeriesWrapper 代理，拦截危险属性链式访问。

    用于在 eval() 调用前对命名空间进行最强安全加固。

    Args:
        namespace: 原始命名空间字典

    Returns:
        安全加固后的命名空间副本
    """
    # 第一层：类型白名单过滤
    filtered = sanitize_namespace(namespace)

    # 第二层：对 Series/ndarray 对象做代理包装
    safe_ns: dict[str, Any] = {}
    for key, value in filtered.items():
        if key.startswith("_"):
            safe_ns[key] = value
        else:
            safe_ns[key] = wrap_safe(value)
    return safe_ns


def validate_namespace_types(namespace: dict[str, Any]) -> list[str]:
    """验证命名空间中值的类型，拒绝危险对象.

    Args:
        namespace: 要验证的命名空间字典

    Returns:
        危险对象对应的键名列表（空列表表示全部安全）
    """

    dangerous: list[str] = []

    for key, value in namespace.items():
        # 跳过内部键
        if key.startswith("_"):
            continue

        # 显式拒绝已知的危险类型
        if value is None or isinstance(value, SAFE_BUILTIN_TYPES):
            continue
        if isinstance(value, np.integer | np.floating | np.bool_ | np.ndarray):
            continue
        if isinstance(value, pd.Series):
            continue
        if isinstance(value, pd.DataFrame):
            continue
        if callable(value) and not isinstance(value, type):
            # 允许预定义的安全函数
            continue
        if isinstance(value, pd.Index | pd.MultiIndex):
            continue

        # 检查是否已包装
        if isinstance(value, SafeSeriesWrapper | _SafeDataFrameWrapper):
            continue

        # 其他未知类型记录但不拒绝（保守策略）
        dangerous.append(key)

    return dangerous


# 允许进入 eval() 命名空间的值类型白名单
_SAFE_VALUE_TYPES: tuple[type, ...] = (
    bool,
    int,
    float,
    str,
    type(None),
)


def sanitize_namespace(namespace: dict[str, Any]) -> dict[str, Any]:
    """轻量级命名空间过滤（第一层防御）.

    只保留量化计算所需的安全类型：pd.Series、np.ndarray、数值类型、可调用函数。
    移除其他任何对象，阻止非量化对象进入 eval() 作用域。

    相比 wrap_namespace()，本函数零包装开销，适合对性能敏感的场景。
    但建议与 wrap_namespace() 组合使用以获得最强防御。

    Args:
        namespace: 原始命名空间字典

    Returns:
        过滤后的安全命名空间副本
    """

    safe: dict[str, Any] = {}
    for key, value in namespace.items():
        # 内部键（如 _stock_index）直接保留
        if key.startswith("_"):
            safe[key] = value
            continue
        # 白名单类型直接保留
        if isinstance(
            value,
            _SAFE_VALUE_TYPES
            + (np.integer, np.floating, np.bool_, np.ndarray, pd.Series, pd.Index, pd.MultiIndex),
        ):
            safe[key] = value
        elif callable(value) and not isinstance(value, type):
            # 允许函数（如 np.abs、np.log 等）进入命名空间
            safe[key] = value
        else:

            logging.getLogger(__name__).debug(
                "eval namespace 过滤：移除非白名单类型变量 %s (%s)", key, type(value).__name__
            )
    return safe
