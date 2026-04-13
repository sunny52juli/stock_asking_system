"""表达式引擎 - 解析和评估量化表达式."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .expression_parser import ExpressionParser
from .namespace_builder import NamespaceBuilder
from .security_validator import validate_expression


class ExpressionEvaluator:
    """表达式评估器.
    
    安全地评估量化表达式。
    """
    
    @staticmethod
    def evaluate(
        expression: str,
        data: pd.DataFrame,
        computed_vars: dict[str, Any] | None = None
    ) -> pd.Series:
        """评估表达式.
        
        Args:
            expression: 表达式字符串
            data: 数据 DataFrame
            computed_vars: 已计算的变量
            
        Returns:
            评估结果 Series
            
        Raises:
            Exception: 评估失败
        """
        # 1. 解析表达式（处理中文）
        parsed_expr = ExpressionParser.parse_expression(expression)
        
        # 2. 安全验证
        validate_expression(parsed_expr)
        
        # 3. 提取变量
        variables = ExpressionParser.extract_variables(parsed_expr)
        
        # 4. 构建命名空间
        namespace = NamespaceBuilder.build_namespace(data, computed_vars)
        
        # 5. 推断并添加缺失变量
        namespace = NamespaceBuilder.infer_and_add_variables(namespace, data, variables)
        
        # 6. 评估表达式
        try:
            result = eval(parsed_expr, {"__builtins__": {}}, namespace)
            
            # 确保返回 Series
            if not isinstance(result, pd.Series):
                result = pd.Series(result, index=data.index)
            
            return result
        except Exception as e:
            raise Exception(f"Expression evaluation failed: {e}") from e
    
    @staticmethod
    def evaluate_with_namespace(
        expression: str,
        namespace: dict[str, Any]
    ) -> pd.Series:
        """使用已有命名空间评估表达式.
        
        Args:
            expression: 表达式字符串
            namespace: 命名空间字典
            
        Returns:
            评估结果 Series
            
        Raises:
            Exception: 评估失败
        """
        # 1. 解析表达式
        parsed_expr = ExpressionParser.parse_expression(expression)
        
        # 2. 安全验证
        validate_expression(parsed_expr)
        
        # 3. 评估表达式
        try:
            result = eval(parsed_expr, {"__builtins__": {}}, namespace)
            
            # 获取 stock_index
            stock_index = namespace.get("_stock_index", pd.RangeIndex(0))
            
            # 确保返回 Series
            if not isinstance(result, pd.Series):
                result = pd.Series(result, index=stock_index)
            
            return result
        except Exception as e:
            raise Exception(f"Expression evaluation failed: {e}") from e


# 便捷函数
def evaluate_expression(
    expression: str,
    data: pd.DataFrame,
    computed_vars: dict[str, Any] | None = None
) -> pd.Series:
    """评估表达式（便捷函数）.
    
    Args:
        expression: 表达式字符串
        data: 数据 DataFrame
        computed_vars: 已计算的变量
        
    Returns:
        评估结果 Series
    """
    evaluator = ExpressionEvaluator()
    return evaluator.evaluate(expression, data, computed_vars)
