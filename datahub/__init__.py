"""
datahub - 数据层统一入口, 仅暴露 DataHub 与五个域入口(驼峰命名)及协议.

推荐用法(配置从环境变量 .env 读取, 无需每次传 root/token):

  from datahub import Stock, Fund, Index, Feature, News, Calendar, DataNotFoundError

  s = Stock()
  df = s.price(date="20240301")
  cal = Calendar()
  trade_dates = cal.get_trade_dates("20240101", "20240131")
  fe = Feature()
  snap = fe.snapshot(factors=["momentum_1m"], date="20240301")

需要统一配置时用 DataHub(配置一次, 再取各域):

  from datahub import DataHub
  hub = DataHub(token="...", root="/path/to/cache")
  s = hub.Stock()
  cal = hub.Calendar()

环境变量: DATA_SOURCE_TOKEN, DATA_CACHE_ROOT. Factory/repo/DataService 不对外导出.

StockDataLoader / FactorDataLoader / load_latest_market_data / get_available_industries 来自 datahub.loaders;
可直接使用本模块的 Stock / Calendar / Feature 等, 或使用上述 loader 便捷接口。See docs/datahub_usage.md for full usage.
"""

__version__ = "3.0.0"

import datahub.registry  # noqa: F401 - side-effect: register datasets
from datahub.core.exceptions import DataNotFoundError
from datahub.entries import Calendar, DataHub, Feature, Fund, Index, News, Stock
from datahub.loaders import (
    FactorDataLoader,
    StockDataLoader,
    create_stock_data_loader,
    get_available_industries,
    load_latest_market_data,
)
from datahub.protocols import (
    CalendarProtocol,
    FeatureProtocol,
    FundProtocol,
    IndexProtocol,
    NewsProtocol,
    StockProtocol,
)

# Polars availability flag
try:
    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False

__all__ = [
    "DataHub",
    "Stock",
    "Fund",
    "Index",
    "Feature",
    "News",
    "Calendar",
    "StockDataLoader",
    "FactorDataLoader",
    "create_stock_data_loader",
    "load_latest_market_data",
    "get_available_industries",
    "StockProtocol",
    "FundProtocol",
    "IndexProtocol",
    "FeatureProtocol",
    "NewsProtocol",
    "CalendarProtocol",
    "DataNotFoundError",
    # Polars
    "POLARS_AVAILABLE",
]
