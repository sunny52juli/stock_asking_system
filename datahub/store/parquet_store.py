import logging
from pathlib import Path

import pandas as pd

from datahub.core.dataset import Dataset, DatasetMeta, DatasetRegistry
from datahub.core.exceptions import DataNotFoundError
from datahub.core.query import Query
from datahub.core.repository import Repository

logger = logging.getLogger(__name__)


class ParquetStore(Repository):
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def load(self, query: Query) -> pd.DataFrame:
        meta, _ = DatasetRegistry.get(query.dataset)

        if not query.is_range:
            return self._load_partition(query, meta)

        if meta.partition_by == "none":
            single = Query(
                dataset=query.dataset,
                date=query.start_date or "",
                codes=query.codes,
                fields=query.fields,
                index_code=query.index_code,
            )
            return self._load_partition(single, meta)

        dates = self._filter_dates(meta, query.start_date, query.end_date)
        dfs: list[pd.DataFrame] = []
        for d in dates:
            single = Query(
                dataset=query.dataset,
                date=d,
                codes=query.codes,
                fields=query.fields,
                index_code=query.index_code,
            )
            try:
                dfs.append(self._load_partition(single, meta))
            except DataNotFoundError:
                continue

        if not dfs:
            raise DataNotFoundError(
                f"No data for {query.dataset.value} in {query.start_date}~{query.end_date}"
            )
        return pd.concat(dfs, ignore_index=True)

    def save(self, dataset: Dataset, data: pd.DataFrame, partition_key: str) -> bool:
        if data is None or data.empty:
            logger.warning("⚠️ Empty data, skip save: %s/%s", dataset.value, partition_key)
            return False

        meta, _ = DatasetRegistry.get(dataset)
        directory = self.root / meta.storage_path
        
        # 检查目录是否可写
        try:
            directory.mkdir(parents=True, exist_ok=True)
            if not directory.exists():
                logger.error("❌ Cannot create cache directory: %s", directory)
                return False
        except Exception as e:
            logger.error("❌ Cannot create cache directory: %s, error=%s", directory, e)
            return False
        
        path = directory / f"{partition_key}.parquet"
        
        # 检查文件是否已存在（避免重复写入）
        if path.exists():
            logger.debug("Cache already exists: %s (will overwrite)", path)

        try:
            data.to_parquet(path, engine="pyarrow", compression="snappy")
            logger.info("✅ Saved: %s (%d rows, %d cols)", path, len(data), len(data.columns))
            return True
        except Exception as e:
            logger.error("❌ Save failed: %s, error=%s (type=%s, rows=%d)", path, e, type(e).__name__, len(data))
            # 尝试删除可能损坏的文件
            if path.exists():
                try:
                    path.unlink()
                    logger.info("Removed potentially corrupted file: %s", path)
                except Exception as cleanup_error:
                    logger.warning("Failed to remove corrupted file: %s, error=%s", path, cleanup_error)
            return False

    def exists(self, dataset: Dataset, partition_key: str) -> bool:
        meta, _ = DatasetRegistry.get(dataset)
        path = self.root / meta.storage_path / f"{partition_key}.parquet"
        return path.exists()

    def available_dates(self, dataset: Dataset) -> list[str]:
        meta, _ = DatasetRegistry.get(dataset)
        if meta.partition_by != "date":
            return []
        directory = self.root / meta.storage_path
        if not directory.exists():
            return []
        return sorted(f.stem for f in directory.glob("*.parquet"))

    def latest_date(self, dataset: Dataset) -> str | None:
        dates = self.available_dates(dataset)
        return dates[-1] if dates else None

    def _load_partition(self, query: Query, meta: DatasetMeta) -> pd.DataFrame:
        partition_key = self._resolve_partition_key(query, meta)
        path = self.root / meta.storage_path / f"{partition_key}.parquet"

        if not path.exists():
            logger.info("❌ Cache MISS: %s (file not found)", path.name)
            raise DataNotFoundError(f"Not found: {path}")

        df = pd.read_parquet(path)
        logger.info("✅ Cache HIT: %s (%d rows, %d cols)", path.name, len(df), len(df.columns))

        if query.codes and meta.code_column in df.columns:
            df = df[df[meta.code_column].isin(query.codes)]
        if query.fields:
            available = [c for c in query.fields if c in df.columns]
            if available:
                df = df[available]

        return df

    def _resolve_partition_key(self, query: Query, meta: DatasetMeta) -> str:
        index_code_safe = ""
        if query.index_code:
            index_code_safe = query.index_code.replace(".", "_")
        return meta.partition_key_template.format(
            date=query.date or "",
            index_code=index_code_safe,
        )

    def _filter_dates(
        self,
        meta: DatasetMeta,
        start: str | None,
        end: str | None,
    ) -> list[str]:
        all_dates = self.available_dates(meta.dataset)
        if not start or not end:
            return all_dates
        return [d for d in all_dates if start <= d <= end]
