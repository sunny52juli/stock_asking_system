from __future__ import annotations

from dataclasses import dataclass

from datahub.core.dataset import Dataset


@dataclass
class Query:
    dataset: Dataset
    date: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    codes: list[str] | None = None
    fields: list[str] | None = None
    index_code: str | None = None

    def __post_init__(self) -> None:
        has_single = self.date is not None
        has_range = self.start_date is not None and self.end_date is not None
        if not has_single and not has_range:
            raise ValueError("Query requires either 'date' or both 'start_date' and 'end_date'")
        if has_single and has_range:
            raise ValueError("Query cannot have both 'date' and 'start_date'/'end_date'")

    @property
    def is_range(self) -> bool:
        return self.start_date is not None
