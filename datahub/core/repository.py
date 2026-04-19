from abc import ABC, abstractmethod


from datahub.core.dataset import Dataset
from datahub.core.query import Query


class Repository(ABC):
    @abstractmethod
    def load(self, query: Query) -> "pl.DataFrame": ...

    @abstractmethod
    def save(self, dataset: Dataset, data: "pl.DataFrame", partition_key: str) -> bool: ...

    @abstractmethod
    def exists(self, dataset: Dataset, partition_key: str) -> bool: ...

    @abstractmethod
    def available_dates(self, dataset: Dataset) -> list[str]: ...

    @abstractmethod
    def latest_date(self, dataset: Dataset) -> str | None: ...
