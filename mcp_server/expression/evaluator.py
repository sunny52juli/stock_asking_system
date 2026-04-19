"""表达式引擎 - 解析和评估量化表达式."""

from __future__ import annotations

import re
from typing import Any

from .namespace import NamespaceBuilder
from .security import validate_expression


from .security import wrap_namespace
class ExpressionParser:
    """表达式解析器.
    
    处理中文字段映射和变量推断。
    """
    
    # 中文字段映射
    FIELD_MAP = {
        '开盘价': 'open',
        '最高价': 'high',
        '最低价': 'low',
        '收盘价': 'close',
        '成交量': 'vol',
        '成交额': 'amount',
        '前收盘': 'pre_close',
    }
    
    @classmethod
    def parse_expression(cls, expr: str) -> str:
        """解析表达式，替换中文字段名.
        
        Args:
            expr: 原始表达式
            
        Returns:
            解析后的表达式
        """
        parsed = expr
        
        # 替换基础字段
        for cn, en in cls.FIELD_MAP.items():
            parsed = parsed.replace(cn, en)
        
        # 处理中文变量名模式：N日字段名 -> 字段名_Nd
        pattern1 = r'(\d+)日(open|high|low|close|vol|amount)'
        parsed = re.sub(pattern1, r'\2_\1d', parsed)
        
        # 处理：N日平均字段名 -> 字段名_avg_Nd
        pattern2 = r'(\d+)日平均(open|high|low|close|vol|amount)'
        parsed = re.sub(pattern2, r'\2_avg_\1d', parsed)
        
        return parsed
    
    @classmethod
    def extract_variables(cls, expr: str) -> list[str]:
        """提取表达式中的变量名.
        
        Args:
            expr: 表达式字符串
            
        Returns:
            变量名列表
        """
        # 匹配标识符（排除数字、运算符、函数名等）
        tokens = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', expr)
        
        # 过滤掉 Python 关键字和常见函数名
        keywords = {
            'and', 'or', 'not', 'in', 'is', 'if', 'else', 'for', 'while',
            'True', 'False', 'None', 'np', 'pd', 'numpy', 'pandas',
            'abs', 'log', 'sqrt', 'exp', 'power', 'max', 'min', 'sum',
        }
        
        return [t for t in tokens if t not in keywords]


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
        
        # 6. 应用三层安全防护
        safe_namespace = wrap_namespace(namespace)
        
        # 7. 评估表达式（使用安全命名空间）
        try:
            result = eval(parsed_expr, {"__builtins__": {}}, safe_namespace)
            
            # 确保返回 Series
            if not isinstance(result, pd.Series):
                result = pd.Series(result, index=data.index)
            
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
