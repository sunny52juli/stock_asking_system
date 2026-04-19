"""DataService: optional generic API (query, get_dates, exists, latest, info). Domain access via stock(), fund(), index(), etc."""

from __future__ import annotations

from dataclasses import dataclass

from datahub.core.dataset import Dataset, DatasetRegistry
from datahub.core.query import Query
from datahub.core.repository import Repository


@dataclass
class DataInfo:
    records: int
    stocks: int
    date_range: tuple[str, str]
    total_dates: int
    fields: list[str]


class DataService:
    """Optional generic API: query, get_dates, exists, latest, info. For domain data use stock(), fund(), index(), feature(), news()."""

    def __init__(
        self,
        repo: Repository | None = None,
        root: str | None = None,
        mode: str = "auto",
    ) -> None:
        if repo is None:
            from datahub.factory import Factory
            self.repo = Factory.create_repo(root=root, mode=mode)
        else:
            self.repo = repo

    def query(self, dataset: Dataset, **kwargs) -> pd.DataFrame:
        q = Query(dataset=dataset, **kwargs)
        return self.repo.load(q)

    def get_dates(self, dataset: Dataset) -> list[str]:
        return self.repo.available_dates(dataset)

    def exists(self, dataset: Dataset, partition_key: str) -> bool:
        return self.repo.exists(dataset, partition_key)

    def latest(self, dataset: Dataset) -> str | None:
        return self.repo.latest_date(dataset)

    def info(self, dataset: Dataset) -> DataInfo:
        dates = self.repo.available_dates(dataset)
        if not dates:
            return DataInfo(0, 0, ("", ""), 0, [])
        meta, _ = DatasetRegistry.get(dataset)
        q = Query(dataset=dataset, date=dates[-1])
        latest_df = self.repo.load(q)
        return DataInfo(
            records=0,
            stocks=(
                latest_df[meta.code_column].nunique()
                if meta.code_column in latest_df.columns
                else 0
            ),
            date_range=(dates[0], dates[-1]),
            total_dates=len(dates),
            fields=latest_df.columns.tolist(),
        )
