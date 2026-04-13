"""命名空间构建器 - 为表达式评估提供变量和函数环境."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


class NamespaceBuilder:
    """命名空间构建器.
    
    为表达式评估提供完整的变量和函数环境。
    """
    
    @staticmethod
    def build_namespace(
        data: pd.DataFrame,
        computed_vars: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """构建表达式的命名空间.
        
        Args:
            data: 数据 DataFrame
            computed_vars: 已计算的变量字典
            
        Returns:
            包含所有需要的变量和函数的命名空间字典
        """
        if computed_vars is None:
            computed_vars = {}
        
        namespace = {
            # 数据列
            **{col: data[col] for col in data.columns},
            
            # 已计算的变量
            **computed_vars,
            
            # NumPy 函数
            "np": np,
            "numpy": np,
            "abs": np.abs,
            "log": np.log,
            "log1p": np.log1p,
            "exp": np.exp,
            "sqrt": np.sqrt,
            "power": np.power,
            "sign": np.sign,
            
            # Pandas
            "pd": pd,
            "pandas": pd,
            
            # 数学常量
            "pi": np.pi,
            "e": np.e,
        }
        
        return namespace
    
    @staticmethod
    def infer_and_add_variables(
        namespace: dict[str, Any],
        data: pd.DataFrame,
        variable_names: list[str]
    ) -> dict[str, Any]:
        """推断并添加缺失的变量到命名空间.
        
        Args:
            namespace: 当前命名空间
            data: 数据 DataFrame
            variable_names: 需要推断的变量名列表
            
        Returns:
            更新后的命名空间
        """
        import re
        
        for var_name in variable_names:
            if var_name in namespace:
                continue
            
            # 尝试从数据列中获取
            if var_name in data.columns:
                namespace[var_name] = data[var_name]
                continue
            
            # 尝试推断技术指标
            inferred = NamespaceBuilder._infer_technical_indicator(data, var_name)
            if inferred is not None:
                namespace[var_name] = inferred
        
        return namespace
    
    @staticmethod
    def _infer_technical_indicator(data: pd.DataFrame, var_name: str) -> pd.Series | None:
        """推断技术指标.
        
        Args:
            data: 数据 DataFrame
            var_name: 变量名
            
        Returns:
            计算结果 Series 或 None
        """
        import re
        
        # MA{n}: 移动平均
        ma_match = re.match(r'(?:MA|ma)(\d+)', var_name, re.IGNORECASE)
        if ma_match:
            window = int(ma_match.group(1))
            return data['close'].rolling(window=window).mean()
        
        # EMA{n}: 指数移动平均
        ema_match = re.match(r'(?:EMA|ema)(\d+)', var_name, re.IGNORECASE)
        if ema_match:
            span = int(ema_match.group(1))
            return data['close'].ewm(span=span).mean()
        
        # RSI{n}: RSI 指标
        rsi_match = re.match(r'(?:RSI|rsi)(\d+)', var_name, re.IGNORECASE)
        if rsi_match:
            window = int(rsi_match.group(1))
            delta = data['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
            rs = gain / (loss + 1e-8)
            return 100 - (100 / (1 + rs))
        
        # STD{n}: 标准差
        std_match = re.match(r'(?:STD|std)(\d+)', var_name, re.IGNORECASE)
        if std_match:
            window = int(std_match.group(1))
            return data['close'].rolling(window=window).std()
        
        # VOL{n}: 成交量均值
        vol_match = re.match(r'(?:VOL|vol)(\d+)', var_name, re.IGNORECASE)
        if vol_match:
            window = int(vol_match.group(1))
            return data['vol'].rolling(window=window).mean()
        
        return None
