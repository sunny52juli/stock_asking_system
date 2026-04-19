"""统一筛选器接口 - 屏蔽底层实现差异.

from src.screening.executor import ScreeningExecutor
from utils.screening.stock_screener import StockScreener
根据使用场景自动选择合适的筛选器实现：
- Agent 实时筛选 → utils.screening.stock_screener.StockScreener
- 回测批量执行 → src.screening.executor.ScreeningExecutor
"""

from __future__ import annotations

from typing import Any, Optional
import pandas as pd


def create_screener(
    data: pd.DataFrame,
    screening_date: Optional[str] = None,
    stock_codes: Optional[list[str]] = None,
    index_data: Optional[pd.DataFrame] = None,
    mode: str = "agent",
):
    """创建筛选器实例.
    
    Args:
        data: 市场数据 DataFrame
        screening_date: 筛选日期 (YYYYMMDD)
        stock_codes: 预筛选股票代码列表
        index_data: 指数数据 DataFrame
        mode: 使用模式
            - "agent": Agent 实时筛选（默认）
            - "backtest": 回测批量执行
    
    Returns:
        筛选器实例
    """
    if mode == "agent":
        return StockScreener(
            data=data,
            screening_date=screening_date,
            stock_codes=stock_codes,
            index_data=index_data,
        )
    elif mode == "backtest":
        return ScreeningExecutor(
            data=data,
            screening_date=screening_date,
        )
    else:
        raise ValueError(f"不支持的模式: {mode}，请使用 'agent' 或 'backtest'")


# 便捷函数：Agent 筛选（最常用）
def screen_stocks(
    data: pd.DataFrame,
    screening_logic: dict,
    top_n: int = 20,
    screening_date: Optional[str] = None,
    stock_codes: Optional[list[str]] = None,
    index_data: Optional[pd.DataFrame] = None,
    query: str = "",
    iteration: int = 1,
) -> list[dict[str, Any]]:
    """执行股票筛选（Agent 模式）.
    
    Args:
        data: 市场数据
        screening_logic: 筛选逻辑配置
        top_n: 返回前 N 只股票
        screening_date: 筛选日期
        stock_codes: 预筛选股票池
        index_data: 指数数据
        query: 原始查询文本
        iteration: 重试次数
        
    Returns:
        候选股票列表
    """
    screener = create_screener(
        data=data,
        screening_date=screening_date,
        stock_codes=stock_codes,
        index_data=index_data,
        mode="agent",
    )
    
    return screener.execute_screening(
        screening_logic=screening_logic,
        top_n=top_n,
        query=query,
        iteration=iteration,
    )


__all__ = [
    "create_screener",
    "screen_stocks",
]
