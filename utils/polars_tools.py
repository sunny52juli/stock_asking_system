"""Polars 高性能计算工具 - 纯 polars 实现.

替代旧的 polars_adapter，所有函数直接返回 polars DataFrame/Series，无 pandas 转换开销。
"""

from __future__ import annotations
import polars as pl
import numpy as np


    


def pivot_wide(price_df: "pl.DataFrame", col: str) -> "pl.DataFrame":
    """透视表操作：长格式转宽格式.
    
    Args:
        price_df: polars DataFrame (columns: trade_date, ts_code, {col})
        col: 要透视的列名
        
    Returns:
        polars DataFrame (index: trade_date, columns: ts_code)
    """
    if "trade_date" not in price_df.columns or "ts_code" not in price_df.columns:
        return pl.DataFrame()
    if col not in price_df.columns:
        return pl.DataFrame()
    
    return price_df.pivot(
        values=col,
        index="trade_date",
        columns="ts_code",
        aggregate_function="last"
    ).sort("trade_date")


def rolling_mean(df: "pl.DataFrame", column: str, window: int = 5, group_col: str | None = None) -> "pl.DataFrame":
    """移动平均计算.
    
    Args:
        df: polars DataFrame
        column: 列名
        window: 窗口大小
        group_col: 分组列（None表示不分组）
        
    Returns:
        polars DataFrame with new column {column}_ma
    """
    if group_col and group_col in df.columns:
        return df.with_columns(
            pl.col(column)
            .rolling_mean(window_size=window, min_samples=window)
            .over(group_col)
            .alias(f"{column}_ma")
        )
    else:
        return df.with_columns(
            pl.col(column).rolling_mean(window_size=window, min_samples=window).alias(f"{column}_ma")
        )


def rolling_std(df: "pl.DataFrame", column: str, window: int = 20, group_col: str | None = None) -> "pl.DataFrame":
    """移动标准差计算.
    
    Args:
        df: polars DataFrame
        column: 列名
        window: 窗口大小
        group_col: 分组列 (None表示不分组)
        
    Returns:
        polars DataFrame with new column {column}_std
    """
    if group_col and group_col in df.columns:
        return df.with_columns(
            pl.col(column)
            .rolling_std(window_size=window, min_samples=window)
            .over(group_col)
            .alias(f"{column}_std")
        )
    else:
        return df.with_columns(
            pl.col(column).rolling_std(window_size=window, min_samples=window).alias(f"{column}_std")
        )


def pct_change(df: "pl.DataFrame", column: str, periods: int = 1, group_col: str | None = None) -> "pl.DataFrame":
    """百分比变化计算.
    
    Args:
        df: polars DataFrame
        column: 列名
        periods: 期数
        group_col: 分组列 (None表示不分组)
        
    Returns:
        polars DataFrame with new column {column}_pct
    """
    if group_col and group_col in df.columns:
        return df.with_columns(
            pl.col(column)
            .pct_change(periods)
            .over(group_col)
            .alias(f"{column}_pct")
        )
    else:
        return df.with_columns(
            pl.col(column).pct_change(periods).alias(f"{column}_pct")
        )


def ts_rank(df: "pl.DataFrame", column: str, window: int = 10, group_col: str = "ts_code") -> "pl.DataFrame":
    """时间序列排名.
    
    Args:
        df: polars DataFrame
        column: 列名
        window: 窗口大小
        group_col: 分组列
        
    Returns:
        polars DataFrame with new column {column}_ts_rank
    """
    def rank_last(s: pl.Series) -> pl.Series:
        """计算窗口内最后一个值的排名百分比."""
        return s.rank() / len(s)
    
    return df.with_columns(
        pl.col(column)
        .rolling_map(rank_last, window_size=window, min_periods=1)
        .over(group_col)
        .alias(f"{column}_ts_rank")
    )


def decay_linear(df: "pl.DataFrame", column: str, window: int = 10, group_col: str = "ts_code") -> "pl.DataFrame":
    """线性衰减加权平均.
    
    Args:
        df: polars DataFrame
        column: 列名
        window: 窗口大小
        group_col: 分组列
        
    Returns:
        polars DataFrame with new column {column}_decay
    """
    
    # 预计算权重
    weights = np.arange(1, window + 1)
    weight_sum = weights.sum()
    
    def weighted_mean(s: pl.Series) -> pl.Series:
        """计算加权平均值."""
        if len(s) < window:
            w = np.arange(1, len(s) + 1)
            return (s * w).sum() / w.sum()
        return (s * weights).sum() / weight_sum
    
    return df.with_columns(
        pl.col(column)
        .rolling_map(weighted_mean, window_size=window, min_periods=1)
        .over(group_col)
        .alias(f"{column}_decay")
    )
