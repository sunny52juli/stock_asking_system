"""同花顺概念数据加载器（兼容层）.

注意：此模块为向后兼容保留，建议使用 datahub.domain.ths_concept.ThsConcept
"""

from __future__ import annotations

import logging

import polars as pl

logger = logging.getLogger(__name__)


def get_ths_concepts(trade_date: str) -> pl.DataFrame:
    """获取同花顺概念成分股数据（兼容接口）.
    
    Args:
        trade_date: 交易日期（YYYYMMDD格式）
        
    Returns:
        DataFrame (concept_code, stock_code, stock_name, concept_name)
        - concept_code: 概念代码 (如 883300.TI)
        - stock_code: 股票代码 (如 000001.SZ)
        - stock_name: 股票名称 (如 平安银行)
        - concept_name: 概念名称 (如 沪深300样本股)
    """
    from datahub.entries import ThsConcept
    
    concept_domain = ThsConcept()
    return concept_domain.get_concepts(trade_date)


def aggregate_ths_concepts_by_stock(concept_df: pl.DataFrame) -> pl.DataFrame:
    """按股票聚合同花顺概念信息（兼容接口）.
    
    Args:
        concept_df: 概念成分股数据 (concept_code, stock_code, stock_name, concept_name)
        
    Returns:
        DataFrame (ts_code, ths_concepts)
        其中 ts_code 是股票代码，ths_concepts 是用 | 分隔的概念字符串
    """
    if concept_df.is_empty() or "concept_name" not in concept_df.columns:
        return pl.DataFrame(schema={"ts_code": pl.String, "ths_concepts": pl.String})
    
    # 确定股票代码列名（可能是 stock_code 或 con_code）
    stock_code_col = "stock_code" if "stock_code" in concept_df.columns else "con_code"
    
    aggregated = (
        concept_df
        .group_by(stock_code_col)  # 按股票代码分组
        .agg(
            pl.col("concept_name")  # 聚合概念名称
            .drop_nulls()
            .unique()
            .sort()
            .str.join("|")
            .alias("ths_concepts")
        )
        .rename({stock_code_col: "ts_code"})
    )
    
    logger.info(f"[OK] 聚合完成：{len(aggregated)} 只股票有概念信息")
    return aggregated
