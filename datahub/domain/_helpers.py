"""Common helpers for domain classes to reduce duplication."""

from __future__ import annotations

from datahub.core.repository import Repository
from datahub.core.dataset import Dataset
from datahub.core.query import Query


def load_with_date_or_range(
    repo: "Repository",
    dataset: "Dataset",
    *,
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    codes: list[str] | None = None,
    fields: list[str] | None = None,
    index_code: str | None = None,
) -> "pl.DataFrame":
    """Load data supporting both single date and date range.
    
    This eliminates the repetitive if/else pattern in every domain method.
    
    Args:
        repo: Repository instance
        dataset: Target dataset
        date: Single date (YYYYMMDD)
        start_date: Start of date range
        end_date: End of date range
        codes: Optional stock/fund codes filter
        fields: Optional fields to select
        index_code: Optional index code
        
    Returns:
        Polars DataFrame with requested data
        
    Raises:
        ValueError: If neither date nor (start_date, end_date) is provided
    """
    if date is not None:
        return repo.load(
            Query(
                dataset=dataset,
                date=date,
                codes=codes,
                fields=fields,
                index_code=index_code,
            )
        )
    
    if start_date is not None and end_date is not None:
        return repo.load(
            Query(
                dataset=dataset,
                start_date=start_date,
                end_date=end_date,
                codes=codes,
                fields=fields,
                index_code=index_code,
            )
        )
    
    raise ValueError("Provide either date or (start_date, end_date)")
