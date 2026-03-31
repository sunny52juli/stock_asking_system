from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


@unique
class Dataset(Enum):
    STOCK_DAILY = "stock_daily"
    STOCK_INDEX_WEIGHT = "stock_index_weight"
    STOCK_BASIC = "stock_basic"
    FUND_NAV = "fund_nav"
    STOCK_VALUATION = "stock_valuation"
    STOCK_HOLDER = "stock_holder"
    FUND_BASIC = "fund_basic"
    FUND_PORTFOLIO = "fund_portfolio"
    INDEX_DAILY = "index_daily"
    STOCK_ANNOUNCEMENT = "stock_announcement"
    ANALYST_REPORT = "analyst_report"
    EARNINGS_FORECAST = "earnings_forecast"
    STOCK_FINANCIALS_INCOME = "stock_financials_income"
    STOCK_FINANCIALS_BALANCE = "stock_financials_balance"
    STOCK_FINANCIALS_CASHFLOW = "stock_financials_cashflow"
    STOCK_DIVIDEND = "stock_dividend"
    STOCK_REPURCHASE = "stock_repurchase"
    STOCK_PLEDGE = "stock_pledge"
    STOCK_MARGIN = "stock_margin"
    FUND_DIVIDEND = "fund_dividend"
    INDEX_VALUATION = "index_valuation"
    INDEX_BASIC = "index_basic"
    TRADE_CALENDAR = "trade_calendar"


@dataclass(frozen=True)
class DatasetMeta:
    dataset: Dataset
    domain: str
    partition_by: str  # "date" | "composite" | "none"
    key_columns: list[str]
    storage_path: str
    date_column: str
    code_column: str
    partition_key_template: str  # e.g. "{date}" or "{index_code}_{date}"
    description: str = ""


@dataclass(frozen=True)
class FetchStep:
    api_name: str
    param_mapping: dict[str, str]  # API param name -> Query field name
    fixed_params: dict[str, Any] = field(default_factory=dict)
    fields: list[str] | None = None
    merge_on: list[str] = field(default_factory=list)
    optional: bool = False
    rate_limit_sleep: float = 0.3


class DatasetRegistry:
    _registry: ClassVar[dict[Dataset, tuple[DatasetMeta, list[FetchStep]]]] = {}

    @classmethod
    def register(cls, meta: DatasetMeta, pipeline: list[FetchStep]) -> None:
        if meta.dataset in cls._registry:
            logger.warning("Overwriting registration for %s", meta.dataset)
        cls._registry[meta.dataset] = (meta, pipeline)

    @classmethod
    def get(cls, dataset: Dataset) -> tuple[DatasetMeta, list[FetchStep]]:
        if dataset not in cls._registry:
            raise KeyError(f"Dataset {dataset!r} not registered")
        return cls._registry[dataset]

    @classmethod
    def list_datasets(cls) -> list[Dataset]:
        return list(cls._registry.keys())

    @classmethod
    def list_domains(cls) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for meta, _ in cls._registry.values():
            if meta.domain not in seen:
                seen.add(meta.domain)
                result.append(meta.domain)
        return result

    @classmethod
    def get_by_domain(cls, domain: str) -> list[Dataset]:
        return [meta.dataset for meta, _ in cls._registry.values() if meta.domain == domain]

    @classmethod
    def clear(cls) -> None:
        cls._registry.clear()
