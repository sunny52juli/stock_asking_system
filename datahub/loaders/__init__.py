"""Loader-style API: StockDataLoader, FactorDataLoader, helpers. Uses datahub Stock/Calendar only.

更底层用法可直接使用 datahub.Stock / datahub.Calendar 等 API 组装所需逻辑。
"""

from datahub.loaders.factor_loader import FactorDataLoader
from datahub.loaders.stock_loader import (
    StockDataLoader,
    create_stock_data_loader,
    get_available_industries,
    load_latest_market_data,
    load_raw_market_data,
)
from datahub.loaders.ths_hot_loader import get_ths_hot_stocks
from datahub.loaders.ths_concept_loader import get_ths_concepts, aggregate_ths_concepts_by_stock

__all__ = [
    "StockDataLoader",
    "FactorDataLoader",
    "create_stock_data_loader",
    "load_latest_market_data",
    "load_raw_market_data",
    "get_available_industries",
    "get_ths_hot_stocks",
    "get_ths_concepts",
    "aggregate_ths_concepts_by_stock",
]
