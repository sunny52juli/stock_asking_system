"""表达式评估器 - 负责向量化评估筛选表达式和置信度."""

from __future__ import annotations

import re
import numpy as np
import polars as pl

from infrastructure.logging.logger import get_logger
from src.screening.namespace_builder import NamespaceBuilder

logger = get_logger(__name__)


class ExpressionEvaluator:
    """表达式评估器 - 负责向量化评估筛选表达式和置信度."""

    @staticmethod
    def evaluate_expression(
        expression: str,
        expression_vars: set[str],
        latest_namespace: dict,
        valid_stocks: list[str],
    ) -> tuple[list[str], dict[str, int]]:
        """向量化评估筛选表达式.
        
        Args:
            expression: 筛选表达式
            expression_vars: 表达式变量集合
            latest_namespace: 最新截面命名空间
            valid_stocks: 有效股票列表
            
        Returns:
            (匹配的股票列表, 统计信息)
        """
        stats = {
            "false_count": 0,
            "nan_count": 0,
            "eval_error_count": 0
        }
        stock_index = latest_namespace.get("_stock_index", valid_stocks)
        
        if not expression or not expression.strip():
            logger.warning(f"   ⚠️ 表达式为空，返回全部股票")
            return valid_stocks, stats
        
        # 确保所有表达式变量都在 namespace 中
        for var in expression_vars:
            if var not in latest_namespace:
                latest_namespace[var] = pl.Series([np.nan] * len(stock_index))
        
        try:
            # 收集所有 Series 变量
            var_series = [
                latest_namespace[v]
                for v in expression_vars
                if v in latest_namespace and isinstance(latest_namespace[v], pl.Series)
            ]
            
            if var_series:
                # Polars: 检测 NaN
                nan_counts = [s.null_count() + s.is_nan().sum() for s in var_series]
                stats["nan_count"] = max(nan_counts) if nan_counts else 0
            else:
                stats["nan_count"] = 0
            
            # 评估表达式
            match_result = eval(expression, {"__builtins__": {}}, latest_namespace)
            
            if isinstance(match_result, pl.Series):
                # Polars Series: 转换为布尔值
                match_bool = match_result.fill_null(False).cast(pl.Boolean)
                stats["false_count"] = int((~match_bool).sum()) - stats["nan_count"]
                stats["false_count"] = max(0, stats["false_count"])
                
                # 获取匹配的股票
                matched_mask = match_bool.to_list()
                matched_stocks = [
                    stock for stock, is_match in zip(stock_index, matched_mask)
                    if is_match
                ]
            elif isinstance(match_result, (bool, np.bool_)):
                matched_stocks = valid_stocks if match_result else []
                stats["false_count"] = 0 if match_result else len(valid_stocks)
            else:
                matched_stocks = valid_stocks if match_result else []
            
        except Exception as e:
            stats["eval_error_count"] = 1
            logger.error(f"   ⚠️ 向量化表达式评估失败：{e}")
            matched_stocks = []
        
        return matched_stocks, stats

    @staticmethod
    def calculate_confidence(
        confidence_formula: str,
        latest_namespace: dict,
        valid_stocks: list[str],
    ) -> list[float]:
        """计算置信度.
        
        Args:
            confidence_formula: 置信度公式
            latest_namespace: 最新截面命名空间
            valid_stocks: 有效股票列表
            
        Returns:
            置信度值列表
        """
        conf_vars = NamespaceBuilder.extract_variables(confidence_formula)
        for var in conf_vars:
            if var not in latest_namespace:
                latest_namespace[var] = pl.Series([np.nan] * len(valid_stocks))
        
        try:
            # 检查置信度公式是否包含函数调用（不支持）
            if re.search(r'\b[a-zA-Z_]\w*\s*\(', confidence_formula):
                logger.warning(f"   ⚠️ 置信度公式包含函数调用（不支持），使用默认值 0.5")
                logger.warning(f"      公式：{confidence_formula}")
                logger.warning(f"      建议：直接使用指标变量，如 volatility_20 / ma20")
                return [0.5] * len(valid_stocks)
            else:
                conf_raw = eval(confidence_formula, {"__builtins__": {}}, latest_namespace)
                if isinstance(conf_raw, pl.Series):
                    # Sigmoid 转换
                    return (1.0 / (1.0 + np.exp(-conf_raw.to_numpy()))).tolist()
                elif isinstance(conf_raw, (int, float)):
                    conf_val = 1.0 / (1.0 + np.exp(-conf_raw))
                    return [conf_val] * len(valid_stocks)
                else:
                    return [0.5] * len(valid_stocks)
        except Exception as e:
            logger.warning(f"   ⚠️ 置信度批量计算失败：{e}，使用默认值 0.5")
            return [0.5] * len(valid_stocks)
