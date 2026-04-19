"""命名空间构建器 - 管理工具计算的中间变量."""

from __future__ import annotations

import re
from typing import Any


class NamespaceBuilder:
    """命名空间构建器 - 管理工具计算的中间变量."""

    @staticmethod
    def build_namespace(data: pl.DataFrame) -> dict:
        """从数据构建初始命名空间."""
        namespace = {}
        # 添加基础数据列（polars Series）
        for col in data.columns:
            namespace[col] = data[col]
        return namespace

    @staticmethod
    def extract_variables(expression: str) -> set[str]:
        """从表达式中提取变量名.
        
        Args:
            expression: Python 表达式字符串
            
        Returns:
            变量名集合
        """
        
        # 简单提取：匹配标识符
        identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', expression)
        
        # 过滤掉 Python 关键字和内置函数
        keywords = {
            'True', 'False', 'None', 'and', 'or', 'not', 'if', 'else',
            'for', 'while', 'in', 'is', 'lambda', 'def', 'class', 'return'
        }
        builtins = {'abs', 'max', 'min', 'sum', 'len', 'int', 'float', 'str'}
        
        return set(identifiers) - keywords - builtins
