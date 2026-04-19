"""Domain entry points: DataHub (single config) and Stock, Fund, Index, News, Feature, Calendar."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, TypeVar

from datahub.domain.calendar import Calendar as _Calendar
from datahub.domain.feature import Feature as _Feature
from datahub.domain.fund import Fund as _Fund
from datahub.domain.index import Index as _Index
from datahub.domain.news import News as _News
from datahub.domain.stock import Stock as _Stock
from datahub.factory import Factory
from datahub.protocols import (
    CalendarProtocol,
    FeatureProtocol,
    FundProtocol,
    IndexProtocol,
    NewsProtocol,
    StockProtocol,
)

T = TypeVar('T')


def _create_repo(
    *,
    root: str | Path | None = None,
    mode: str = "auto",
    token: str | None = None,
) -> object:

    root_str = str(root) if isinstance(root, Path) else root
    return Factory.create_repo(root=root_str, token=token, mode=mode)


def _create_domain_instance(
    domain_class: Callable[[object], T],
    root: str | Path | None = None,
    mode: str = "auto",
    token: str | None = None,
    repo: object | None = None,
) -> T:
    """Create a domain instance with DRY pattern.
    
    Args:
        domain_class: Domain class constructor (e.g., _Stock, _Fund)
        root: Cache root path
        mode: Repository mode (auto/local/remote)
        token: API token
        repo: Optional pre-created repository
        
    Returns:
        Domain instance
    """
    if repo is not None:
        return domain_class(repo)
    return domain_class(_create_repo(root=root, mode=mode, token=token))


class DataHub:
    """Single entry: configure once (env or kwargs), then Stock(), Fund(), etc. with no args."""

    __slots__ = ("_root", "_mode", "_token", "_repo")

    def __init__(
        self,
        root: str | Path | None = None,
        mode: str = "auto",
        token: str | None = None,
    ) -> None:
        self._root = root
        self._mode = mode
        self._token = token
        self._repo: object | None = None

    def _get_repo(self) -> object:
        if self._repo is None:
            self._repo = _create_repo(root=self._root, mode=self._mode, token=self._token)
        return self._repo

    def Stock(self) -> StockProtocol:
        """Return stock dataset (uses this DataHub config)."""
        return _Stock(self._get_repo())

    def Fund(self) -> FundProtocol:
        """Return fund dataset (uses this DataHub config)."""
        return _Fund(self._get_repo())

    def Index(self) -> IndexProtocol:
        """Return index dataset (uses this DataHub config)."""
        return _Index(self._get_repo())

    def News(self) -> NewsProtocol:
        """Return news dataset (uses this DataHub config)."""
        return _News(self._get_repo())

    def Calendar(self) -> CalendarProtocol:
        """Return trading calendar. Uses exchange_calendars library."""
        return _Calendar()

    def Feature(self, stock_instance: StockProtocol | None = None) -> FeatureProtocol:
        """Return feature dataset (uses this DataHub config; optional shared Stock)."""
        if stock_instance is None:
            stock_instance = _Stock(self._get_repo())
        return _Feature(stock_instance)


def Stock(
    root: str | Path | None = None,
    mode: str = "auto",
    token: str | None = None,
    repo: object | None = None,
) -> StockProtocol:
    """Return stock dataset. Config from env when root/token/repo not passed."""
    return _create_domain_instance(_Stock, root=root, mode=mode, token=token, repo=repo)


def Fund(
    root: str | Path | None = None,
    mode: str = "auto",
    token: str | None = None,
    repo: object | None = None,
) -> FundProtocol:
    """Return fund dataset. Config from env when root/token/repo not passed."""
    return _create_domain_instance(_Fund, root=root, mode=mode, token=token, repo=repo)


def Index(
    root: str | Path | None = None,
    mode: str = "auto",
    token: str | None = None,
    repo: object | None = None,
) -> IndexProtocol:
    """Return index dataset. Config from env when root/token/repo not passed."""
    return _create_domain_instance(_Index, root=root, mode=mode, token=token, repo=repo)


def News(
    root: str | Path | None = None,
    mode: str = "auto",
    token: str | None = None,
    repo: object | None = None,
) -> NewsProtocol:
    """Return news dataset. Config from env when root/token/repo not passed."""
    return _create_domain_instance(_News, root=root, mode=mode, token=token, repo=repo)


def Calendar(
    root: str | Path | None = None,
    mode: str = "auto",
    token: str | None = None,
) -> CalendarProtocol:
    """Return trading calendar. Uses exchange_calendars library."""
    return _Calendar()


def Feature(
    root: str | Path | None = None,
    mode: str = "auto",
    token: str | None = None,
    stock_instance: StockProtocol | None = None,
) -> FeatureProtocol:
    """Return feature dataset. Config from env when root/token not passed."""
    if stock_instance is None:
        repo = _create_repo(root=root, mode=mode, token=token)
        stock_instance = _Stock(repo)
    return _Feature(stock_instance)
