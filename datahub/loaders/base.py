"""Base loader and mixin: multi-index, filter, merge, extract industries, clean. No I/O."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
import pandas as pd


class BaseDataLoader(ABC):
    """Base data loader: common DataFrame ops and cache. Subclasses implement load_data."""

    def __init__(self) -> None:
        self._data: pd.DataFrame | None = None
        self._stock_pool: list[str] | None = None

    @property
    def data(self) -> pd.DataFrame | None:
        return self._data

    @property
    def stock_pool(self) -> list[str] | None:
        return self._stock_pool

    @abstractmethod
    def load_data(self, **kwargs: Any) -> pd.DataFrame:
        """Load data; subclasses implement."""
        ...

    def set_multi_index(self, data: pd.DataFrame) -> pd.DataFrame:
        """Set index to (trade_date, ts_code)."""
        if data is None or len(data) == 0:
            return data
        if "trade_date" in data.columns:
            data = data.copy()
            data["trade_date"] = pd.to_datetime(data["trade_date"])
        sort_cols = [c for c in ["trade_date", "ts_code"] if c in data.columns]
        if sort_cols:
            data = data.sort_values(sort_cols)
        if "trade_date" in data.columns and "ts_code" in data.columns:
            data = data.set_index(["trade_date", "ts_code"])
        return data

    def filter_by_stock_pool(
        self,
        data: pd.DataFrame,
        stock_pool: list[str] | None = None,
    ) -> pd.DataFrame:
        """Filter rows to stock_pool or self._stock_pool."""
        if data is None or len(data) == 0:
            return data
        pool = stock_pool or self._stock_pool
        if not pool:
            return data
        if isinstance(data.index, pd.MultiIndex):
            ts_codes = data.index.get_level_values("ts_code")
            return data.loc[ts_codes.isin(pool)]
        if "ts_code" in data.columns:
            return data[data["ts_code"].isin(pool)]
        return data

    def merge_data_dicts(self, data_dict: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Concat DataFrames from date -> df dict."""
        if not data_dict:
            return pd.DataFrame()
        return pd.concat(data_dict.values(), ignore_index=True)

    @staticmethod
    def extract_industries(data: pd.DataFrame) -> list[str]:
        """Unique sorted industry names from data."""
        if data is None:
            return []
        if isinstance(data.index, pd.MultiIndex):
            reset = data.reset_index()
            if "industry" not in reset.columns:
                return []
            industries = reset["industry"].dropna().unique()
        else:
            if "industry" not in data.columns:
                return []
            industries = data["industry"].dropna().unique()
        return sorted([str(i) for i in industries if str(i).strip()])

    def get_data_info(self) -> dict[str, Any]:
        """Summary of loaded data."""
        if self._data is None:
            return {"status": "not_loaded"}
        info: dict[str, Any] = {"status": "loaded", "record_count": len(self._data)}
        if isinstance(self._data.index, pd.MultiIndex):
            info["stock_count"] = self._data.index.get_level_values("ts_code").nunique()
            info["date_range"] = {
                "start": self._data.index.get_level_values("trade_date").min().strftime("%Y-%m-%d"),
                "end": self._data.index.get_level_values("trade_date").max().strftime("%Y-%m-%d"),
            }
        elif "ts_code" in self._data.columns:
            info["stock_count"] = self._data["ts_code"].nunique()
        return info

    def clean_data(self, data: pd.DataFrame | None = None) -> pd.DataFrame:
        """Drop all-na, key-field na, and zero vol rows."""
        if data is None:
            data = self._data
        if data is None:
            raise ValueError("没有数据可清洗")
        data = data.dropna(how="all")
        key_cols = ["open", "high", "low", "close", "vol"]
        existing = [c for c in key_cols if c in data.columns]
        if existing:
            data = data.dropna(subset=existing)
        if "vol" in data.columns:
            data = data[data["vol"] > 0]
        return data


class DataLoaderMixin:
    """Static helpers: set_dataframe_index, filter_stocks."""

    @staticmethod
    def set_dataframe_index(data: pd.DataFrame) -> pd.DataFrame:
        """Set (trade_date, ts_code) index."""
        if data is None or len(data) == 0:
            return data
        data = data.copy()
        data["trade_date"] = pd.to_datetime(data["trade_date"])
        data = data.sort_values(["trade_date", "ts_code"])
        return data.set_index(["trade_date", "ts_code"])

    @staticmethod
    def filter_stocks(data: pd.DataFrame, stock_pool: list[str]) -> pd.DataFrame:
        """Filter rows to stock_pool."""
        if data is None or len(data) == 0 or not stock_pool:
            return data
        if isinstance(data.index, pd.MultiIndex):
            ts_codes = data.index.get_level_values("ts_code")
            return data.loc[ts_codes.isin(stock_pool)]
        if "ts_code" in data.columns:
            return data[data["ts_code"].isin(stock_pool)]
        return data
