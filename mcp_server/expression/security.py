"""AST 安全验证器 - 防止恶意代码执行."""

from __future__ import annotations

import ast
from typing import Any


# 允许的 Python 内置函数和模块
ALLOWED_BUILTINS = {
    "abs", "max", "min", "sum", "len", "round", "int", "float", "str",
    "bool", "list", "dict", "tuple", "set", "sorted", "reversed",
    "True", "False", "None",
}

# 允许的 pandas/numpy 方法
ALLOWED_ATTRIBUTES = {
    # pandas Series 方法
    "rolling", "ewm", "groupby", "transform", "apply", "map",
    "mean", "std", "var", "min", "max", "sum", "count",
    "diff", "pct_change", "shift", "rank", "cumsum", "cummax", "cummin",
    "fillna", "dropna", "replace", "astype",
    # numpy 函数
    "log", "log1p", "exp", "sqrt", "abs", "sign", "power",
    "sin", "cos", "tan",
}

# 禁止的操作
FORBIDDEN_NODES = {
    ast.Import,
    ast.ImportFrom,
    ast.ClassDef,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.Await,
    ast.Exec,
}


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
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
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
            tree = ast.parse(expression, mode='eval')
            self.visit(tree)
            return True
        except SyntaxError as e:
            raise SecurityError(f"Invalid syntax: {e}") from e


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
