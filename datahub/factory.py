from pathlib import Path
import os

from datahub.core.repository import Repository
from datahub.service.data_service import DataService
from datahub.source.tushare_source import TushareSource
from datahub.store.parquet_store import ParquetStore
from datahub.sync.sync_repo import SyncRepository


class Factory:
    @staticmethod
    def create(
        root: str | None = None,
        token: str | None = None,
        mode: str = "auto",
    ) -> DataService:
        repo = Factory.create_repo(root=root, token=token, mode=mode)
        return DataService(repo=repo)

    @staticmethod
    def create_repo(
        root: str | None = None,
        token: str | None = None,
        mode: str = "auto",
    ) -> Repository:
        # 从环境变量获取配置，不依赖 infrastructure
        cache_root = root or os.getenv("DATA_CACHE_ROOT", "data_cache")
        root_path = Path(cache_root)
        store = ParquetStore(root_path)

        if mode == "local":
            return store

        source = TushareSource(token=token)

        if mode == "remote":
            return SyncRepository(store, source, auto_save=False)

        return SyncRepository(store, source, auto_save=True)

    @staticmethod
    def store(root: str | None = None) -> ParquetStore:
        cache_root = root or os.getenv("DATA_CACHE_ROOT", "data_cache")
        return ParquetStore(Path(cache_root))

    @staticmethod
    def source(token: str | None = None) -> TushareSource:
        return TushareSource(token=token)
