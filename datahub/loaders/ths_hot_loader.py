"""同花顺热门股加载器."""

from __future__ import annotations

import logging

import polars as pl

logger = logging.getLogger(__name__)


def get_ths_hot_stocks(trade_date: str, top_n: int = 100) -> list[str]:
    """获取同花顺热门股列表.
    
    Args:
        trade_date: 交易日期（YYYYMMDD格式）
        top_n: 获取前N只热门股
        
    Returns:
        热门股票代码列表
    """
    logger.info(f"[DATA] 正在从 TuShare 加载 {trade_date} 的热门股 (Top {top_n})...")
    
    try:
        from datahub.source.tushare_source import TushareSource
        from infrastructure.config.settings import get_settings
        
        settings = get_settings()
        source = TushareSource(token=settings.data.source_token)
        
        # 调用 ths_hot 接口
        hot_df = source.fetch("ths_hot", {"trade_date": trade_date})
        
        if hot_df.is_empty():
            logger.warning("[WARN] 未获取到热门股数据")
            return []
        
        # 取前 N 只股票
        if len(hot_df) > top_n:
            hot_df = hot_df.head(top_n)
        
        # 提取股票代码
        stock_codes = hot_df.select("ts_code").to_series().to_list()
        
        logger.info(f"[OK] 获取到 {len(stock_codes)} 只热门股")
        
        return stock_codes
            
    except Exception as e:
        logger.error(f"[ERROR] 加载热门股数据失败: {e}", exc_info=True)
        return []
