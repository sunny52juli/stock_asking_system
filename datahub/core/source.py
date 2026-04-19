from abc import ABC, abstractmethod
from typing import  Any
import polars as pl


class DataSource(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def call(self, api_name: str, params: dict[str, Any]) -> "pl.DataFrame | None": ...

    @abstractmethod
    def ping(self) -> bool: ...
