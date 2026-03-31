"""
统一数据加载模块

整合 backtest 和 screener_deepagent 的数据加载功能，
复用 datahub.loaders 中的 StockDataLoader 实现。
"""

from __future__ import annotations

import pandas as pd

from datahub.loaders import StockDataLoader, get_available_industries as _get_industries_from_datahub
from utils.logger import get_logger

logger = get_logger(__name__)


def load_market_data_for_backtest(
    *,
    exclude_st: bool = True,
    min_list_days: int = 180,
    index_code: str | None = None,
    force_reload: bool = False,
) -> pd.DataFrame:
    """Load market data for backtest using date range from strategy_des.
    
    Args:
        exclude_st: Whether to exclude ST stocks
        min_list_days: Minimum listing days
        index_code: Optional index code to restrict stock universe
        force_reload: Force reload from data source
        
    Returns:
        DataFrame with MultiIndex (trade_date, ts_code)
    """
    # 直接从 strategy_des 获取筛选日期和数据范围（run.py 专用）
    from utils.screening_tools import get_data_start_date
    from config.strategy_des import StrategyDescriptions
    
    screening_date = StrategyDescriptions.SCREENING_DATE
    start_date = get_data_start_date(screening_date)  # 往前推观察期
    
    # 重要：不使用持有期未来数据，只加载到筛选日期为止
    # end_date = StrategyDescriptions.get_data_end_date(screening_date)  # 这会往后推持有期，产生未来数据
    end_date = screening_date  # 直接使用筛选日期作为结束日期
    
    logger.info(f"📅 策略生成配置日期：screening_date={screening_date}")
    logger.info(f"📅 计算得到的数据范围：start_date={start_date}, end_date={end_date}")
    logger.info(f"使用配置的日期范围：{start_date} ~ {end_date}")
    
    # 使用 datahub 的 Stock 和 Calendar 直接加载数据
    from datahub import Stock, Calendar
    stock = Stock()


    stock_pool = _get_stock_pool(
        stock,
        index_code=index_code,
        trade_date=end_date,  # 明确传入配置的结束日期
        exclude_st=exclude_st,
        min_list_days=min_list_days,
    )
    
    if not stock_pool:
        raise ValueError("无法获取股票池数据，请检查本地数据是否存在")
    
    logger.info(f"📊 股票池共 {len(stock_pool)} 只股票")
    
    # 加载市场数据（使用配置的日期范围）
    logger.info(f"📊 加载数据：{start_date} ~ {end_date}")
    logger.info(f"🔍 调用 stock.price(start_date={start_date}, end_date={end_date})")
    df = stock.price(start_date=start_date, end_date=end_date)
    logger.info(f"📊 stock.price() 返回 DataFrame 形状：{df.shape if df is not None else 'None'}")
    
    if df is None or df.empty:
        raise ValueError(f"无法获取市场数据 ({start_date}~{end_date})")
    
    # 诊断信息：检查加载的数据范围
    if "trade_date" in df.columns:
        actual_min_date = df["trade_date"].min()
        actual_max_date = df["trade_date"].max()
        logger.warning(f"⚠️ 实际数据范围：{actual_min_date} ~ {actual_max_date} (请求范围：{start_date} ~ {end_date})")
    
    # 过滤到股票池
    df_filtered = df[df["ts_code"].isin(stock_pool)].copy()
    
    # 诊断信息：检查过滤后的数据
    if len(df_filtered) < len(df):
        logger.warning(f"⚠️ 股票池过滤：从 {len(df)} 条记录过滤到 {len(df_filtered)} 条记录")
    
    df = df_filtered
    
    # 补充行业信息
    if "industry" not in df.columns:
        df = _supplement_industry(df, stock)
    
    # 设置 MultiIndex
    df = _set_multi_index(df)
    
    logger.info(f"✅ 已加载市场数据：{len(df)} 条记录")
    return df


def load_market_data(
    *,
    exclude_st: bool = True,
    min_list_days: int = 180,
    index_code: str | None = None,
    force_reload: bool = False,
) -> pd.DataFrame:
    """Load market data using date range from strategy_des.
    
    这是 load_market_data_for_backtest 的别名，用于兼容 screener_deepagent。
    两者功能完全相同，都使用 strategy_des 配置的日期范围。
    
    Args:
        exclude_st: Whether to exclude ST stocks
        min_list_days: Minimum listing days
        index_code: Optional index code to restrict stock universe
        force_reload: Force reload from data source
        
    Returns:
        DataFrame with MultiIndex (trade_date, ts_code)
    """
    return load_market_data_for_backtest(
        exclude_st=exclude_st,
        min_list_days=min_list_days,
        index_code=index_code,
        force_reload=force_reload,
    )


def _get_stock_pool(
    stock,
    *,
    index_code: str | None = None,
    trade_date: str,
    exclude_st: bool = True,
    min_list_days: int = 180,
) -> list[str]:
    """获取股票池列表
    
    复用 datahub.loaders.stock_loader 中的 _get_stock_pool_from_datahub 逻辑。
    
    Args:
        stock: Stock 实例
        index_code: 指数代码，如果为 None 则使用全市场
        trade_date: 交易日期
        exclude_st: 是否排除 ST 股票
        min_list_days: 最小上市天数
        
    Returns:
        股票代码列表
    """
    # 直接调用 datahub 的实现
    from datahub.loaders.stock_loader import _get_stock_pool_from_datahub
    
    return _get_stock_pool_from_datahub(
        stock=stock,
        index_code=index_code,
        trade_date=trade_date,
        exclude_st=exclude_st,
        min_list_days=min_list_days,
    )


def _set_multi_index(data: pd.DataFrame) -> pd.DataFrame:
    """设置 MultiIndex (trade_date, ts_code)
    
    Args:
        data: 原始 DataFrame
        
    Returns:
        设置索引后的 DataFrame
    """
    if data is None or len(data) == 0:
        return data
    
    # 处理日期列
    if "trade_date" in data.columns:
        data = data.copy()
        data["trade_date"] = pd.to_datetime(data["trade_date"])
    
    # 排序
    sort_cols = [c for c in ["trade_date", "ts_code"] if c in data.columns]
    if sort_cols:
        data = data.sort_values(sort_cols)
    
    # 设置 MultiIndex
    if "trade_date" in data.columns and "ts_code" in data.columns:
        data = data.set_index(["trade_date", "ts_code"])
    
    return data


def _supplement_industry(data: pd.DataFrame, stock=None) -> pd.DataFrame:
    """补充行业信息
    
    Args:
        data: 市场数据 DataFrame
        stock: Stock 实例，如果为 None 则创建新的实例
        
    Returns:
        补充行业信息后的 DataFrame
    """
    if "industry" in data.columns:
        return data
    
    if stock is None:
        from datahub import Stock
        stock = Stock()
    
    basic = stock.universe()
    if basic is not None and not basic.empty and "industry" in basic.columns:
        info = basic[["ts_code", "industry"]].drop_duplicates("ts_code")
        data = data.merge(info, on="ts_code", how="left")
    
    return data


def load_latest_market_data(recent_days=60) -> pd.DataFrame:
    """加载最近交易日的市场数据。
    
    自动从数据源拉取最新交易日数据，包含行业信息和 MultiIndex。
    
    Args:
        recent_days: 拉取最近多少天的数据，默认 60 天
        
    Returns:
        DataFrame with MultiIndex (trade_date, ts_code)
    """
    from datahub import Stock
    from datetime import datetime, timedelta
    
    stock = Stock()
    
    # 拉取最近 N 个自然日的数据（自动包含最新交易日）
    today = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=recent_days)).strftime("%Y%m%d")
    
    df = stock.price(start_date=start_date, end_date=today)
    
    # 补充行业信息
    df = _supplement_industry(df, stock)
    
    # 设置 MultiIndex (trade_date, ts_code) - 这是筛选工具必需的
    return _set_multi_index(df)


def get_available_industries(data: pd.DataFrame | None = None) -> list[str]:
    """获取可用的行业列表
    
    优先使用 datahub.loaders.get_available_industries 的实现。
    
    Args:
        data: 可选的 DataFrame，如果提供则从中提取行业
        
    Returns:
        行业列表
    """
    # 如果提供了 data，直接使用 datahub 的函数
    if data is not None:
        return _get_industries_from_datahub(data)
    
    # 否则从 datahub 加载最新数据
    try:
        loader = StockDataLoader()
        loader.load_market_data()
        return loader.get_available_industries()
    except Exception as e:
        logger.warning(f"从 datahub 加载行业信息失败：{e}，尝试备用方法")
        # 备用方法：直接从 Stock 获取
        from datahub import Stock
        stock = Stock()
        basic = stock.universe()
        if basic is None or basic.empty or "industry" not in basic.columns:
            return []
        industries = basic["industry"].dropna().unique()
        return sorted([str(i) for i in industries if str(i).strip()])


__all__ = [
    "load_market_data_for_backtest",
    "load_market_data",
    "load_latest_market_data",
    "get_available_industries",
]
