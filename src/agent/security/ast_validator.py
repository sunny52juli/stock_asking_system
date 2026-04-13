"""AST 白名单验证器.

在 eval() 调用前使用 AST 分析验证表达式安全性，防止代码注入攻击.
"""

from __future__ import annotations

import ast
import warnings
from dataclasses import dataclass, field

# 抑制弃用警告（兼容 Python 3.8-3.14）
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message="ast\\.(Num|Str|Bytes|NameConstant|Ellipsis) is deprecated",
)
warnings.filterwarnings("ignore", category=DeprecationWarning, message="ast\\.Index is deprecated")

# Python 3.12+ 中已移除或弃用的 AST 节点
# 使用 getattr 安全获取，兼容不同版本
_OLD_NODES: dict[str, type | None] = {}
for _node_name in ["Num", "Str", "Bytes", "NameConstant", "Ellipsis", "Index", "ExtSlice"]:
    node = getattr(ast, _node_name, None)
    if node is not None:
        _OLD_NODES[_node_name] = node


class ASTValidationError(ValueError):
    """表达式未通过 AST 安全检查."""


@dataclass
class ValidationRule:
    """AST 节点验证规则."""

    allow_nodes: set[type[ast.AST]] = field(default_factory=set)
    allow_attributes: set[str] = field(default_factory=set)
    allow_functions: set[str] = field(default_factory=set)
    allow_imports: set[str] = field(default_factory=set)
    block_nodes: set[type[ast.AST]] = field(default_factory=set)
    block_names: set[str] = field(default_factory=set)
    block_calls: set[str] = field(default_factory=set)
    max_depth: int = 20
    description: str = ""


# 构建兼容的节点集合，过滤掉 None 值
def _filter_none(nodes_dict: dict) -> set:
    return {v for v in nodes_dict.values() if v is not None}


# 算术/比较运算符节点类型
_OP_NODES = {
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.LShift,
    ast.RShift,
    ast.BitOr,
    ast.BitXor,
    ast.BitAnd,
    ast.MatMult,
    ast.And,
    ast.Or,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Is,
    ast.IsNot,
    ast.In,
    ast.NotIn,
    ast.UAdd,
    ast.USub,
    ast.Not,
    ast.Invert,
}

# AST 上下文节点类型 (Load, Store, Del 等)
_CTX_NODES = {
    ast.Load,
    ast.Store,
    ast.Del,
}

# 默认安全规则：只允许安全的表达式节点
_ALLOW_NODES = {
    ast.Expression,  # 根节点
    ast.Compare,  # 比较: >, <, ==, !=, >=, <=
    ast.BoolOp,  # 布尔运算: and, or
    ast.UnaryOp,  # 一元运算: not, +, -
    ast.BinOp,  # 二元运算: +, -, *, /, %, **, //, @
    ast.IfExp,  # 三元表达式: x if cond else y
    ast.Constant,  # 常量 (Python >= 3.8)
    ast.List,  # 列表字面量
    ast.Tuple,  # 元组字面量
    ast.Dict,  # 字典字面量
    ast.Set,  # 集合字面量
    ast.Subscript,  # 下标访问: arr[0], df['col']
    ast.Slice,  # 切片: a:b:c
    ast.Call,  # 函数调用
    ast.Attribute,  # 属性访问: obj.attr
    ast.keyword,  # 关键字参数
    ast.Starred,  # *args
    ast.FormattedValue,  # f-string 内部
    ast.JoinedStr,  # f-string
    ast.ListComp,  # 列表推导式
    ast.SetComp,  # 集合推导式
    ast.DictComp,  # 字典推导式
    ast.comprehension,  # 推导式迭代器
    # ast.Lambda 已移除：lambda 闭包可捕获命名空间对象，存在逃逸风险
    ast.arguments,  # lambda 参数（保留兼容，但 Lambda 本身已禁止）
    ast.arg,  # lambda 参数定义
    ast.Name,  # 变量名
}
# 添加运算符节点（Add, Sub, Mult 等）
_ALLOW_NODES.update(_OP_NODES)
# 添加上下文节点（Load, Store 等）
_ALLOW_NODES.update(_CTX_NODES)
# 添加兼容的旧节点类型
_ALLOW_NODES.update(
    _filter_none({k: v for k, v in _OLD_NODES.items() if k not in ("Exec", "Print", "Repr")})
)

_BLOCK_NODES = {
    ast.Import,  # import xxx
    ast.ImportFrom,  # from xxx import yyy
    ast.FunctionDef,  # def xxx():
    ast.AsyncFunctionDef,  # async def xxx():
    ast.ClassDef,  # class XXX:
    ast.Delete,  # del xxx
    ast.For,  # for xxx in yyy:
    ast.AsyncFor,  # async for xxx in yyy:
    ast.While,  # while xxx:
    ast.With,  # with xxx as yyy:
    ast.AsyncWith,  # async with xxx as yyy:
    ast.Raise,  # raise xxx
    ast.Try,  # try: ... except: ...
    ast.Assert,  # assert xxx
    ast.Global,  # global xxx
    ast.Nonlocal,  # nonlocal xxx
    ast.Pass,  # pass
    ast.Break,  # break
    ast.Continue,  # continue
    ast.Return,  # return xxx
    ast.Yield,  # yield xxx
    ast.YieldFrom,  # yield from xxx
    ast.Await,  # await xxx
}
# 添加兼容的旧节点类型（如果存在）
_BLOCK_NODES.update(
    _filter_none({k: v for k, v in _OLD_NODES.items() if k in ("Exec", "Print", "Repr")})
)

DEFAULT_RULES = ValidationRule(
    # 允许的 AST 节点类型
    allow_nodes=_ALLOW_NODES,
    # 明确禁止的 AST 节点类型
    block_nodes=_BLOCK_NODES,
    # 禁止使用的内置名称
    block_names={
        "__import__",
        "__builtins__",
        "eval",
        "exec",
        "compile",
        "open",
        "globals",
        "locals",
        "vars",
        "dir",
        "getattr",
        "setattr",
        "delattr",
        "hasattr",
        "breakpoint",
        "memoryview",
        "super",
        "type",
        "object",
        "__class__",
        "__base__",
        "__bases__",
        "__subclasses__",
        "__mro__",
        "__code__",
        "__func__",
        "__self__",
        "__module__",
        "__dict__",
        "__wrapped__",
        # 危险 dunder 属性（防止通过对象属性链逃逸沙箱）
        "__globals__",
        "__locals__",
        "__closure__",
        "__qualname__",
        "__init__",
        "__new__",
        "__del__",
        "__reduce__",
        "__reduce_ex__",
        "__getstate__",
        "__setstate__",
        "__slots__",
        "apply",
        "buffer",
        "coerce",
        "intern",
        "input",
        "raw_input",
        "reload",
        "unichr",
        "reduce",  # 虽然安全但通常不需要
        "sys",
        "os",
        "subprocess",
        "socket",
        "requests",
        "urllib",
        "shutil",
        "pathlib",
        "json",
        "pickle",
        "marshal",
        "shelve",
        "tempfile",
        "http",
        "xml",
        "builtins",
    },
    # 允许的属性名 (用于 Attribute 节点)
    allow_attributes={
        "shape",
        "dtype",
        "index",
        "columns",
        "values",
        "tolist",
        "item",
        "size",
        "ndim",
        "mean",
        "std",
        "min",
        "max",
        "sum",
        "abs",
        "all",
        "any",
        "argmax",
        "argmin",
        "argsort",
        "astype",
        "clip",
        "copy",
        "cumsum",
        "cumprod",
        "describe",
        "diff",
        "dot",
        "fillna",
        "head",
        "tail",
        "iloc",
        "loc",
        "iat",
        "at",
        "isin",
        "isna",
        "isnull",
        "notna",
        "notnull",
        "rolling",
        "ewm",
        "shift",
        "pct_change",
        "resample",
        "sort_values",
        "sort_index",
        "transpose",
        "T",
        "flatten",
        "ravel",
        "reshape",
        "real",
        "imag",
        "conjugate",
        "conj",
        "upper",
        "lower",
        "strip",
        "lstrip",
        "rstrip",
        "replace",
        "split",
        "join",
        "startswith",
        "endswith",
        "find",
        "count",
        "encode",
        "decode",
        "format",
        "capitalize",
        "title",
        "swapcase",
        "zfill",
        "ljust",
        "rjust",
        "center",
        "partition",
        "rpartition",
        "isalpha",
        "isdigit",
        "isnumeric",
        "isalnum",
        "isspace",
        "islower",
        "isupper",
        "istitle",
        "items",
        "keys",
        "get",
        "pop",
        "update",
        "clear",
        "fromkeys",
        "setdefault",
        "append",
        "extend",
        "insert",
        "remove",
        "sort",
        "reverse",
        "add",
        "discard",
        "union",
        "intersection",
        "difference",
        "symmetric_difference",
        "issubset",
        "issuperset",
        "isdisjoint",
    },
    description="默认表达式安全检查规则",
)


def validate_expression(
    expr: str,
    rules: ValidationRule | None = None,
    namespace: dict | None = None,
) -> ast.Expression:
    """验证表达式 AST 安全性.

    解析表达式并使用白名单规则检查 AST 节点，防止代码注入。

    Args:
        expr: 要验证的表达式字符串
        rules: 自定义验证规则，默认为 DEFAULT_RULES
        namespace: 命名空间（用于额外验证）

    Returns:
        解析后的 AST Expression 节点

    Raises:
        ASTValidationError: 表达式未通过安全检查
        SyntaxError: 表达式语法错误
    """
    if not expr or not expr.strip():
        raise ASTValidationError("表达式不能为空")

    rules = rules or DEFAULT_RULES

    # 解析 AST
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        # 语句（如 import/def/class）不是有效表达式，直接拒绝
        raise ASTValidationError(f"表达式语法错误（可能不是表达式）: {e}")

    # 验证 AST 节点
    _check_node(tree, rules, namespace, depth=0)

    return tree


def _check_node(
    node: ast.AST,
    rules: ValidationRule,
    namespace: dict | None,
    depth: int,
) -> None:
    """递归检查 AST 节点."""
    if depth > rules.max_depth:
        raise ASTValidationError(f"表达式嵌套过深 (最大 {rules.max_depth} 层)")

    node_type = type(node)

    # 检查是否在禁止列表中
    if node_type in rules.block_nodes:
        raise ASTValidationError(f"不允许使用 {node_type.__name__} 节点")

    # 检查是否在允许列表中
    if node_type not in rules.allow_nodes:
        raise ASTValidationError(f"不允许使用 {node_type.__name__} 节点类型")

    # 检查特定节点类型
    if isinstance(node, ast.Name):
        if node.id in rules.block_names:
            raise ASTValidationError(f"不允许使用名称: {node.id}")
        if node.id.startswith("__") and node.id.endswith("__"):
            raise ASTValidationError(f"不允许使用魔法名称: {node.id}")

    elif isinstance(node, ast.Call):
        _check_call_node(node, rules)

    elif isinstance(node, ast.Attribute):
        if node.attr in rules.block_names:
            raise ASTValidationError(f"不允许访问属性: {node.attr}")
        # 明确禁止所有双下划线属性访问（__xxx__ 形式）
        if node.attr.startswith("__") and node.attr.endswith("__"):
            raise ASTValidationError(f"不允许访问双下划线属性: {node.attr}")
        if (
            node.attr not in rules.allow_attributes
            and rules.allow_attributes
            and node.attr.startswith("_")
        ):
            # 如果在属性白名单模式下，检查属性名
            raise ASTValidationError(f"不允许访问私有属性: {node.attr}")
        # 递归检查属性对象
        _check_node(node.value, rules, namespace, depth + 1)
        return

    elif isinstance(node, ast.Constant):
        # 检查常量值
        if isinstance(node.value, str) and ("__" in node.value or "import" in node.value.lower()):
            # 检查字符串中是否包含可疑内容
            raise ASTValidationError("字符串常量包含可疑内容")

    # 递归检查子节点
    for child in ast.iter_child_nodes(node):
        _check_node(child, rules, namespace, depth + 1)


def _check_call_node(node: ast.Call, rules: ValidationRule) -> None:
    """检查函数调用节点."""
    func = node.func

    if isinstance(func, ast.Name):
        func_name = func.id
        if func_name in rules.block_calls:
            raise ASTValidationError(f"不允许调用函数: {func_name}")
        if rules.allow_functions and func_name not in rules.allow_functions:
            raise ASTValidationError(f"函数 {func_name} 不在白名单中")

    elif isinstance(func, ast.Attribute):
        # 检查模块.函数 调用模式 (如 np.abs)
        if isinstance(func.value, ast.Name):
            module_name = func.value.id
            attr_name = func.attr
            # 允许 np.xxx 调用
            if module_name == "np" and attr_name.startswith("_"):
                raise ASTValidationError(f"不允许调用 NumPy 私有方法: np.{attr_name}")
            if module_name == "pd" and attr_name.startswith("_"):
                raise ASTValidationError(f"不允许调用 pandas 私有方法: pd.{attr_name}")
            # 禁止 pandas 的 eval/query（可执行任意表达式）
            if module_name == "pd" and attr_name in {"eval", "query"}:
                raise ASTValidationError(f"不允许调用 pandas 危险方法: pd.{attr_name}")
            if module_name not in {"np", "pd"}:
                raise ASTValidationError(f"不允许从 {module_name} 模块调用")
        else:
            # 其他属性调用（如 obj.method()）：检查方法名在白名单中
            if func.attr.startswith("_"):
                raise ASTValidationError(f"不允许调用私有方法: {func.attr}")
            if func.attr in rules.block_calls:
                raise ASTValidationError(f"不允许调用方法: {func.attr}")
            if rules.allow_attributes and func.attr not in rules.allow_attributes:
                raise ASTValidationError(f"方法 {func.attr} 不在属性白名单中")

    else:
        raise ASTValidationError(f"不支持的函数调用形式: {type(func).__name__}")

    # 检查关键字参数
    for keyword in node.keywords:
        if keyword.arg and keyword.arg.startswith("_"):
            raise ASTValidationError(f"不允许使用私有关键字参数: {keyword.arg}")
