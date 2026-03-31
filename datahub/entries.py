"""Domain entry points: DataHub (single config) and Stock, Fund, Index, News, Feature, Calendar."""

from __future__ import annotations

from pathlib import Path

from datahub.domain.calendar import Calendar as _Calendar
from datahub.domain.feature import Feature as _Feature
from datahub.domain.fund import Fund as _Fund
from datahub.domain.index import Index as _Index
from datahub.domain.news import News as _News
from datahub.domain.stock import Stock as _Stock
from datahub.protocols import (
    CalendarProtocol,
    FeatureProtocol,
    FundProtocol,
    IndexProtocol,
    NewsProtocol,
    StockProtocol,
)


def _create_repo(
    *,
    root: str | Path | None = None,
    mode: str = "auto",
    token: str | None = None,
) -> object:
    from datahub.factory import Factory

    root_str = str(root) if isinstance(root, Path) else root
    return Factory.create_repo(root=root_str, token=token, mode=mode)


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
    if repo is not None:
        return _Stock(repo)
    return _Stock(_create_repo(root=root, mode=mode, token=token))


def Fund(
    root: str | Path | None = None,
    mode: str = "auto",
    token: str | None = None,
    repo: object | None = None,
) -> FundProtocol:
    """Return fund dataset. Config from env when root/token/repo not passed."""
    if repo is not None:
        return _Fund(repo)
    return _Fund(_create_repo(root=root, mode=mode, token=token))


def Index(
    root: str | Path | None = None,
    mode: str = "auto",
    token: str | None = None,
    repo: object | None = None,
) -> IndexProtocol:
    """Return index dataset. Config from env when root/token/repo not passed."""
    if repo is not None:
        return _Index(repo)
    return _Index(_create_repo(root=root, mode=mode, token=token))


def News(
    root: str | Path | None = None,
    mode: str = "auto",
    token: str | None = None,
    repo: object | None = None,
) -> NewsProtocol:
    """Return news dataset. Config from env when root/token/repo not passed."""
    if repo is not None:
        return _News(repo)
    return _News(_create_repo(root=root, mode=mode, token=token))


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
