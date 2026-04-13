"""Common helpers for domain classes to reduce duplication."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from datahub.core.repository import Repository
    from datahub.core.dataset import Dataset


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
) -> pd.DataFrame:
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
        DataFrame with requested data
        
    Raises:
        ValueError: If neither date nor (start_date, end_date) is provided
    """
    from datahub.core.query import Query
    
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
