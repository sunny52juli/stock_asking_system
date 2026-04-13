"""表达式解析器 - 处理中文字段映射和变量推断."""

from __future__ import annotations

import re


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
