"""Loader-style API: StockDataLoader, FactorDataLoader, helpers. Uses datahub Stock/Calendar only.

更底层用法可直接使用 datahub.Stock / datahub.Calendar 等 API 组装所需逻辑。
"""

from datahub.loaders.factor_loader import FactorDataLoader
from datahub.loaders.stock_loader import (
    StockDataLoader,
    create_stock_data_loader,
    get_available_industries,
    load_market_data,
)

__all__ = [
    "StockDataLoader",
    "FactorDataLoader",
    "create_stock_data_loader",
    "load_market_data",
    "get_available_industries",
]
