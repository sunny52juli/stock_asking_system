"""FactorDataLoader: backtest data and stock pool via datahub Stock and Calendar.

可选用; 更底层用法请直接用 datahub.Stock + datahub.Calendar。
"""

from __future__ import annotations

import pandas as pd

from datahub.entries import Calendar, Stock
from datahub.loaders.base import BaseDataLoader
from datahub.loaders.stock_loader import _get_stock_pool_from_datahub

try:
    from infrastructure.config.settings import StockConfig
except ImportError:
    StockConfig = None  # type: ignore[misc, assignment]

try:
    from infrastructure.errors.exceptions import DataLoadError, StockPoolError
except ImportError:
    DataLoadError = Exception  # type: ignore[misc, assignment]
    StockPoolError = Exception  # type: ignore[misc, assignment]


class FactorDataLoader(BaseDataLoader):
    """Load backtest data and stock pool using datahub.

    可选用; 更底层用法请直接用 datahub.Stock + datahub.Calendar。
    """

    def __init__(
        self,
        stock: Stock | None = None,
        calendar: Calendar | None = None,
    ) -> None:
        super().__init__()
        self._stock = stock or Stock()
        self._calendar = calendar or Calendar()

    def load_data(self, **kwargs: object) -> pd.DataFrame:
        return self.load_backtest_data(**kwargs)

    def get_stock_pool(
        self,
        index_code: str | None = None,
        exclude_st: bool = True,
        min_list_days: int = 180,
        trade_date: str | None = None,  # 新增参数，必须显式传入
    ) -> list[str]:
        """获取股票池
        
        Args:
            index_code: 指数代码
            exclude_st: 是否排除 ST 股票
            min_list_days: 最小上市天数
            trade_date: 交易日期（必须显式传入，禁止使用 latest_date() 避免未来函数）
            
        Returns:
            股票代码列表
        """
        if index_code is None and StockConfig is not None:
            index_code = getattr(StockConfig, "BACKTEST_DEFAULT_INDEX_CODE", None)
        if index_code:
            print(f"📊 使用指数 {index_code} 的成分股作为股票池")
        else:
            print("📊 使用全市场股票作为股票池")
        
        # trade_date 必须显式传入，禁止使用 latest_date() 获取未来日期
        if trade_date is None:
            raise ValueError("trade_date 参数必须显式传入，禁止使用 latest_date() 获取未来日期")
        self._stock_pool = _get_stock_pool_from_datahub(
            self._stock,
            index_code=index_code,
            trade_date=trade_date,
            exclude_st=exclude_st,
            min_list_days=min_list_days,
        )
        if not self._stock_pool:
            raise StockPoolError("无法获取股票池数据，请检查本地数据是否存在")
        print(f"📊 股票池共 {len(self._stock_pool)} 只股票")
        return self._stock_pool

    def load_market_data(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        stock_pool: list[str] | None = None,
    ) -> pd.DataFrame:
        # 使用筛选日期计算数据范围（包含持有期收益统计需要的未来数据）
        if start_date is None and StockConfig is not None:
            screening_date = getattr(StockConfig, "BACKTEST_SCREENING_DATE", None)
            if screening_date:
                start_date = StockConfig.get_data_start_date(screening_date)  # 往前推观察期
            else:
                start_date = "20200101"
        if end_date is None and StockConfig is not None:
            screening_date = getattr(StockConfig, "BACKTEST_SCREENING_DATE", None)
            if screening_date:
                end_date = StockConfig.get_data_end_date(screening_date)  # 往后推持有期
            else:
                end_date = "20240331"
        print(f"📊 加载回测数据: {start_date} ~ {end_date}")
        df = self._stock.price(start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            raise DataLoadError(
                f"无法获取回测时间范围内的数据 ({start_date}~{end_date})",
                details={"start_date": start_date, "end_date": end_date},
            )
        self._data = df.copy()
        pool = stock_pool or self._stock_pool
        if pool:
            self._data = self._data[self._data["ts_code"].isin(pool)]
        self._data = self.set_multi_index(self._data)
        print(f"✅ 已加载本地数据: {len(self._data)} 条记录")
        if isinstance(self._data.index, pd.MultiIndex):
            print(
                f"   时间范围: {self._data.index.get_level_values('trade_date').min()} ~ {self._data.index.get_level_values('trade_date').max()}"
            )
            print(f"   股票数量: {self._data.index.get_level_values('ts_code').nunique()} 只")
        print("   索引结构: MultiIndex(trade_date, ts_code)")
        return self._data

    def load_backtest_data(
        self,
        index_code: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        # 使用筛选日期作为股票池的 trade_date
        if end_date is None and StockConfig is not None:
            end_date = getattr(StockConfig, "BACKTEST_SCREENING_DATE", None)
        
        stock_pool = self.get_stock_pool(
            index_code=index_code,
            trade_date=end_date,  # 显式传入 end_date
        )
        return self.load_market_data(
            start_date=start_date,
            end_date=end_date,
            stock_pool=stock_pool,
        )

    def get_single_date_data(self, trade_date: str) -> pd.DataFrame:
        df = self._stock.price(date=trade_date)
        if df is None or df.empty:
            raise DataLoadError(
                f"无法获取 {trade_date} 的数据",
                details={"trade_date": trade_date},
            )
        return df

    def clean_data(self, data: pd.DataFrame | None = None) -> pd.DataFrame:
        cleaned = super().clean_data(data)
        print(f"✅ 数据清洗完成: {len(cleaned)} 条记录")
        return cleaned
