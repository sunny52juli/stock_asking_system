"""StockDataLoader: market data + stock pool via datahub Stock and Calendar.

可选用; 更底层用法请直接用 datahub.Stock + datahub.Calendar。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from datahub.entries import Calendar, Stock
from datahub.loaders.base import BaseDataLoader


def _get_stock_pool_from_datahub(
    stock: Stock,
    index_code: str | None = None,
    trade_date: str | None = None,
    exclude_st: bool = True,
    min_list_days: int = 180,
) -> list[str]:
    """Return ts_code list: index constituents or full universe, filtered by ST and list_days.
    
    Args:
        stock: Stock 实例
        index_code: 指数代码，如果为 None 则使用全市场
        trade_date: 交易日期（必须显式传入，禁止使用 latest_date() 避免未来函数）
        exclude_st: 是否排除 ST 股票
        min_list_days: 最小上市天数
        
    Returns:
        股票代码列表
    """
    # trade_date 必须显式传入，禁止使用 latest_date() 获取未来日期
    if trade_date is None:
        raise ValueError("trade_date 参数必须显式传入，禁止使用 latest_date() 获取未来日期")
    basic = stock.universe()
    if basic is None or basic.empty:
        return []
    if "ts_code" not in basic.columns:
        return []
    if index_code:
        members = stock.universe_by_index(index_code, date=trade_date)
        if members is None or members.empty:
            return []
        code_col = "con_code" if "con_code" in members.columns else "ts_code"
        stock_list = members[code_col].astype(str).unique().tolist()
        basic = basic[basic["ts_code"].isin(stock_list)]
    else:
        stock_list = basic["ts_code"].astype(str).tolist()
    if exclude_st or min_list_days > 0:
        if "list_date" in basic.columns:
            basic = basic.copy()
            basic["list_date"] = pd.to_datetime(basic["list_date"], errors="coerce")
            ref = pd.Timestamp(trade_date[:4] + "-" + trade_date[4:6] + "-" + trade_date[6:8])
            basic["list_days"] = (ref - basic["list_date"]).dt.days
            basic = basic[basic["list_days"] >= min_list_days]
        if exclude_st and "name" in basic.columns:
            basic = basic[~basic["name"].astype(str).str.contains("ST", na=False)]
    return basic["ts_code"].astype(str).unique().tolist()


class StockDataLoader(BaseDataLoader):
    """Load market data and stock pool using datahub Stock + Calendar.

    可选用; 更底层用法请直接用 datahub.Stock + datahub.Calendar。
    """

    def __init__(
        self,
        exclude_st: bool = True,
        min_list_days: int = 180,
        index_code: str | None = None,
        stock: Stock | None = None,
        calendar: Calendar | None = None,
    ) -> None:
        super().__init__()
        self.exclude_st = exclude_st
        self.min_list_days = min_list_days
        self.index_code = index_code
        self._stock = stock or Stock()
        self._calendar = calendar or Calendar()
        self._available_industries: list[str] | None = None

    def load_data(self, **kwargs: object) -> pd.DataFrame:
        return self.load_market_data(**kwargs)

    def load_market_data(self, force_reload: bool = False, trade_date_for_pool: str | None = None, start_date: str | None = None, end_date: str | None = None, observation_days: int | None = None) -> pd.DataFrame:
        """Load market data.
        
        Args:
            force_reload: Force reload from data source
            trade_date_for_pool: Trade date for stock pool filtering. 
                                If None, uses the latest available trade date from cache/calendar.
                                Recommended to set explicitly to avoid future date issues.
            start_date: Start date for price data (YYYYMMDD). If None, auto-calculated from backtest_config or trade_date_for_pool
            end_date: End date for price data (YYYYMMDD). If None, uses trade_date_for_pool
            observation_days: Number of trading days for lookback period. If None, uses config default
        """
        if self._data is not None and not force_reload:
            print("📊 使用缓存的市场数据")
            return self._data
        print("📊 正在加载市场数据...")
        
        # 如果 trade_date_for_pool 未提供，尝试获取最新可用日期
        if trade_date_for_pool is None:
            trade_date_for_pool = self._get_latest_trade_date()
        
        # 如果没有提供 start_date 和 end_date，使用最新交易日期为基准
        if start_date is None or end_date is None:
            default_start, default_end = self._calculate_default_dates(trade_date_for_pool, observation_days)
            if start_date is None:
                start_date = default_start
            if end_date is None:
                end_date = default_end
        
        self._stock_pool = _get_stock_pool_from_datahub(
            self._stock,
            index_code=self.index_code,
            trade_date=trade_date_for_pool,  # 支持显式传入日期，避免使用 latest_date()
            exclude_st=self.exclude_st,
            min_list_days=self.min_list_days,
        )
        if not self._stock_pool:
            raise ValueError("无法获取股票池数据，请检查本地数据是否存在")
        print(f"📊 股票池共 {len(self._stock_pool)} 只股票")
        
        # 加载价格数据
        print(f"📊 加载数据：{start_date} ~ {end_date}")
        df = self._stock.price(start_date=start_date, end_date=end_date)
        
        if df is None or df.empty:
            raise ValueError(f"无法获取市场数据 ({start_date}~{end_date})")
        
        # 过滤到股票池
        df = df[df["ts_code"].isin(self._stock_pool)].copy()
        
        # 补充行业信息
        df = self._supplement_industry(df)
        
        # 设置 MultiIndex (trade_date, ts_code)
        if "trade_date" in df.columns:
            df = df.copy()
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            df = df.sort_values(["trade_date", "ts_code"])
            df = df.set_index(["trade_date", "ts_code"])
        
        self._data = df
        print(f"✅ 已加载市场数据：{len(df)} 条记录")
        return df


    def _get_latest_trade_date(self) -> str:
        """获取最新交易日期。
        
        Returns:
            交易日期字符串 (YYYYMMDD)
        """
        try:
            # 从 calendar 获取最新交易日
            calendar = self._calendar or Calendar()
            latest_date = calendar.latest_trade_date()
            if latest_date:
                return latest_date.strftime("%Y%m%d")
        except Exception:
            pass
        
        # 备用方案：使用当前日期
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d")
    
    def _calculate_default_dates(self, reference_date: str, observation_days: int | None = None) -> tuple[str, str]:
        """计算默认的 start_date 和 end_date。
        
        Args:
            reference_date: 参考日期 (YYYYMMDD)
            observation_days: 观察期长度（交易日），默认从配置读取
            
        Returns:
            (start_date, end_date) 元组
        """
        from utils.screening.screening_tools import get_data_start_date
        
        try:
            end_dt = datetime.strptime(reference_date, "%Y%m%d")
            end_date = reference_date
        except ValueError:
            # 如果解析失败，使用当前日期
            end_dt = datetime.now()
            end_date = end_dt.strftime("%Y%m%d")
        
        # 使用配置的 observation_days 计算起始日期
        start_date = get_data_start_date(end_date, observation_days)
        
        return start_date, end_date

    def _supplement_industry(self, data: pd.DataFrame) -> pd.DataFrame:
        if "industry" in data.columns:
            return data
        basic = self._stock.universe()
        if basic is not None and not basic.empty and "industry" in basic.columns:
            info = basic[["ts_code", "industry"]].drop_duplicates("ts_code")
            data = data.merge(info, on="ts_code", how="left")
        return data

    def get_available_industries(self) -> list[str]:
        if self._available_industries is not None:
            return self._available_industries
        if self._data is None:
            self.load_market_data()
        return self._available_industries or []

    def get_latest_date(self) -> datetime | None:
        if self._data is None:
            return None
        return self._data.index.get_level_values("trade_date").max()

    def get_stock_codes(self) -> list[str]:
        if self._data is None:
            return []
        return self._data.index.get_level_values("ts_code").unique().tolist()


def create_stock_data_loader(
    exclude_st: bool = True,
    min_list_days: int = 180,
    index_code: str | None = None,
) -> StockDataLoader:
    return StockDataLoader(
        exclude_st=exclude_st,
        min_list_days=min_list_days,
        index_code=index_code,
    )


def get_available_industries(data: pd.DataFrame | None = None) -> list[str]:
    """获取可用的行业列表
    
    Args:
        data: 可选的 DataFrame，如果提供则从中提取行业；否则从数据源加载
        
    Returns:
        行业列表（已排序）
    """
    if data is not None:
        # 从提供的 DataFrame 中提取
        if "industry" not in data.columns:
            return []
        if isinstance(data.index, pd.MultiIndex):
            industries = data.reset_index()["industry"].dropna().unique()
        else:
            industries = data["industry"].dropna().unique()
        return sorted([str(i) for i in industries if str(i).strip()])
    
    # 从数据源加载
    loader = StockDataLoader()
    loader.load_market_data()
    return loader.get_available_industries()


def load_latest_market_data(recent_days: int = 60) -> pd.DataFrame:
    """加载最近交易日的市场数据。
    
    自动从数据源拉取最新 N 天的数据，包含行业信息和 MultiIndex。
    
    Args:
        recent_days: 拉取最近多少天的数据，默认 60 天
        
    Returns:
        DataFrame with MultiIndex (trade_date, ts_code)
    """
    from datetime import datetime, timedelta
    
    # 计算日期范围
    today = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=recent_days)).strftime("%Y%m%d")
    
    # 使用 StockDataLoader 加载数据
    loader = StockDataLoader()
    return loader.load_market_data(
        start_date=start_date,
        end_date=today,
    )
