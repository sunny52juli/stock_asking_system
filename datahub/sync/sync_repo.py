import logging
import time
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from datahub.core.dataset import Dataset, DatasetMeta, DatasetRegistry, FetchStep
from datahub.core.exceptions import DataNotFoundError
from datahub.core.query import Query
from datahub.core.repository import Repository
from datahub.core.source import DataSource

logger = logging.getLogger(__name__)


class SyncRepository(Repository):
    def __init__(
        self,
        store: Repository,
        source: DataSource,
        auto_save: bool = True,
    ) -> None:
        self.store = store
        self.source = source
        self.auto_save = auto_save

    def load(self, query: Query) -> pd.DataFrame:
        meta, pipeline = DatasetRegistry.get(query.dataset)

        if not query.is_range:
            return self._load_single(query, meta, pipeline)

        if meta.partition_by == "date":
            return self._load_date_range(query, meta, pipeline)

        return self._fetch_range_direct(query, meta, pipeline)

    def save(self, dataset: Dataset, data: pd.DataFrame, partition_key: str) -> bool:
        return self.store.save(dataset, data, partition_key)

    def exists(self, dataset: Dataset, partition_key: str) -> bool:
        return self.store.exists(dataset, partition_key)

    def available_dates(self, dataset: Dataset) -> list[str]:
        return self.store.available_dates(dataset)

    def latest_date(self, dataset: Dataset) -> str | None:
        return self.store.latest_date(dataset)

    def _load_single(
        self,
        query: Query,
        meta: DatasetMeta,
        pipeline: list[FetchStep],
    ) -> pd.DataFrame:
        # 尝试从缓存加载
        try:
            result = self.store.load(query)
            logger.info("✅ Cache HIT: %s/%s", query.dataset.value, query.date)
            return result
        except DataNotFoundError as e:
            logger.debug("Cache not found: %s/%s, error=%s", query.dataset.value, query.date, e)
            pass

        # Cache MISS - 需要从数据源获取
        logger.info(
            "❌ Cache MISS: %s/%s, fetching from %s (fields=%s)",
            query.dataset.value,
            query.date,
            self.source.name,
            query.fields[:5] if query.fields else None,
        )
        data = self._execute_pipeline(pipeline, query)

        if data is None or data.empty:
            # 静默跳过空数据（可能是非交易日、节假日或数据不可用）
            raise DataNotFoundError(
                f"No data for {query.dataset.value}/{query.date} from local or {self.source.name}."
            )

        # 数据质量检测：检查 NaN 比例
        nan_ratio = self._check_data_quality(data)
        if nan_ratio > 0.5:  # 超过 50% 的单元格是 NaN
            logger.error(
                "❌ Data quality check FAILED: %s/%s has %.1f%% NaN values (threshold: 50%%). "
                "This data will NOT be saved to cache.",
                query.dataset.value,
                query.date,
                nan_ratio * 100,
            )
            # 即使 auto_save=True 也不保存低质量数据
            save_flag_backup = self.auto_save
            self.auto_save = False
            try:
                return self._apply_filters(data, query, meta)
            finally:
                self.auto_save = save_flag_backup
        elif nan_ratio > 0.1:  # 超过 10% 但不超过 50%，只警告但仍然保存
            logger.warning(
                "⚠️ Data quality WARNING: %s/%s has %.1f%% NaN values. "
                "Data will be saved but please verify the source.",
                query.dataset.value,
                query.date,
                nan_ratio * 100,
            )

        # 自动保存缓存（如果启用）
        if self.auto_save:
            partition_key = self._resolve_partition_key(query, meta)
            logger.info("💾 Auto-saving cache: %s/%s (key=%s)", query.dataset.value, query.date, partition_key)
            success = self._safe_save(query.dataset, data, partition_key)
            if success:
                logger.info("✅ Cache saved successfully: %s/%s", query.dataset.value, query.date)
            else:
                # _safe_save 已经记录了详细错误，这里只需要记录一个汇总警告
                logger.warning("⚠️ Cache save failed, will re-fetch next time: %s/%s", query.dataset.value, query.date)

        return self._apply_filters(data, query, meta)

    def _load_date_range(
        self,
        query: Query,
        meta: DatasetMeta,
        pipeline: list[FetchStep],
    ) -> pd.DataFrame:
        # 如果指定日期不是交易日，自动选择最近的交易日
        from datahub.domain.calendar import Calendar as CalendarDomain
        calendar_domain = CalendarDomain()
        
        adjusted_start_date = query.start_date
        adjusted_end_date = query.end_date
        
        # 只调整 end_date（往前找最近交易日），不调整 start_date（保证数据范围）
        if query.end_date and not calendar_domain.is_trade_day(query.end_date):
            # end_date 不是交易日，找到之前最后一个交易日
            latest_trade_date = calendar_domain.get_latest_trade_date(
                str(int(query.end_date) + 1)  # get_latest_trade_date 返回严格小于给定日期的交易日
            )
            if latest_trade_date and latest_trade_date >= (query.start_date or ""):
                adjusted_end_date = latest_trade_date
                logger.info(
                    "📅 End date %s is not a trade day, adjusted to %s",
                    query.end_date,
                    adjusted_end_date,
                )
            else:
                logger.warning("⚠️ No trade days found before %s, using original date", query.end_date)
        
        # 使用调整后的日期创建新的 query
        if adjusted_start_date != query.start_date or adjusted_end_date != query.end_date:
            query = Query(
                dataset=query.dataset,
                start_date=adjusted_start_date,
                end_date=adjusted_end_date,
                codes=query.codes,
                fields=query.fields,
                index_code=query.index_code,
            )
            logger.info(
                "📅 Date range adjusted: %s~%s → %s~%s",
                query.start_date, query.end_date,
                adjusted_start_date, adjusted_end_date,
            )
        
        # 优先使用交易日历过滤非交易日
        if query.start_date and query.end_date:
            try:
                from datahub.domain.calendar import Calendar as CalendarDomain
                calendar_domain = CalendarDomain()  # 不需要传 store 参数
                trade_dates = calendar_domain.get_trade_dates(query.start_date, query.end_date)
                logger.info(
                    "📅 Calendar call: start=%s, end=%s, result_count=%s",
                    query.start_date,
                    query.end_date,
                    len(trade_dates) if trade_dates else 0,
                )
                if trade_dates:
                    dates = trade_dates
                    logger.info(
                        "📅 Using trade calendar: %d trading days found (%s ~ %s)",
                        len(dates),
                        dates[0] if dates else "N/A",
                        dates[-1] if dates else "N/A",
                    )
                else:
                    # 交易日历为空（可能是非交易日或数据未缓存），使用原始日期范围
                    logger.warning("⚠️ Calendar returned empty list, using date range")
                    dates = self._get_date_range(query)
            except Exception as e:
                # 无法获取交易日历时（如缓存未命中），使用原始日期范围
                logger.error("❌ Calendar exception: %s", e)
                logger.warning("⚠️ Calendar error: %s, falling back to date range", e)
                dates = self._get_date_range(query)
        else:
            dates = self._get_date_range(query)
        
        # 优化：尝试直接批量加载整个日期范围，避免循环单个日期
        try:
            # 先尝试一次性加载整个范围的数据
            range_query = Query(
                dataset=query.dataset,
                start_date=query.start_date,
                end_date=query.end_date,
                codes=query.codes,
                fields=query.fields,
                index_code=query.index_code,
            )
            logger.info("🚀 Attempting direct range load: %s ~ %s", query.start_date, query.end_date)
            result = self._fetch_range_direct(range_query, meta, pipeline)
            if result is not None and not result.empty:
                # 验证返回的数据是否包含完整的日期范围
                if meta.date_column and meta.date_column in result.columns:
                    actual_dates = sorted(result[meta.date_column].unique().tolist())
                    min_date = str(actual_dates[0])[:10].replace("-", "")
                    max_date = str(actual_dates[-1])[:10].replace("-", "")
                    logger.info("✅ Loaded date range directly: %s~%s, shape=%s, actual_range=%s~%s", 
                               query.start_date, query.end_date, result.shape, min_date, max_date)
                    
                    # 如果实际数据范围与请求范围不一致，回退到逐日加载
                    if min_date > query.start_date or max_date < query.end_date:
                        logger.warning("⚠️ Direct range load returned incomplete data (%s~%s vs requested %s~%s), falling back to daily loop",
                                      min_date, max_date, query.start_date, query.end_date)
                        raise DataNotFoundError("Incomplete date range from direct load")
                else:
                    logger.info("✅ Loaded date range directly: %s~%s, shape=%s", query.start_date, query.end_date, result.shape)
                return result
        except Exception as e:
            # 如果批量加载失败，回退到逐日加载
            logger.error("❌ Direct range load failed: %s, falling back to daily loop", e)
            logger.debug("Direct range load failed, falling back to daily loop")
            pass
        
        # 原始逻辑：逐日加载
        dfs: list[pd.DataFrame] = []
        cache_misses: list[str] = []  # 收集 cache miss 的日期
        cache_hits: list[str] = []  # 收集 cache hit 的日期

        for d in dates:
            single_query = Query(
                dataset=query.dataset,
                date=d,
                codes=query.codes,
                fields=query.fields,
                index_code=query.index_code,
            )
            try:
                df = self._load_single(single_query, meta, pipeline)
                dfs.append(df)
                cache_hits.append(d)
            except DataNotFoundError:
                cache_misses.append(d)  # 先收集，不立即记录日志
                continue

        # 只在真正有缺失时才记录一次汇总日志
        if cache_misses:
            logger.error(
                "❌ Cache misses for %s: %d/%d dates missing (%s~%s). This is NORMAL - data will be fetched and cached automatically.",
                query.dataset.value,
                len(cache_misses),
                len(dates),
                min(cache_misses),
                max(cache_misses),
            )
        
        if cache_hits:
            logger.info(
                "✅ Cache hits: %d/%d dates loaded from cache (%s~%s)",
                len(cache_hits),
                len(dates),
                min(cache_hits),
                max(cache_hits),
            )

        if not dfs:
            raise DataNotFoundError(
                f"No data for {query.dataset.value} in {query.start_date}~{query.end_date}"
            )
        return pd.concat(dfs, ignore_index=True)

    def _fetch_range_direct(
        self,
        query: Query,
        meta: DatasetMeta,
        pipeline: list[FetchStep],
    ) -> pd.DataFrame:
        # 范围查询：先检查缓存完整性，缺失则逐日填充
        from datahub.domain.calendar import Calendar
        
        calendar = Calendar()
        trade_dates = calendar.get_trade_dates(query.start_date, query.end_date)
        
        if not trade_dates:
            raise DataNotFoundError(f"No trading days in {query.start_date}~{query.end_date}")
        
        logger.info("📅 Range query: checking %d trading days (%s ~ %s)", len(trade_dates), query.start_date, query.end_date)
        
        all_results: list[pd.DataFrame] = []
        missing_dates: list[str] = []
        
        # 第一步：检查每个交易日的缓存
        for trade_date in trade_dates:
            single_query = Query(
                dataset=query.dataset,
                date=trade_date,
                codes=query.codes,
                fields=query.fields,
                index_code=query.index_code,
            )
            
            try:
                cached = self.store.load(single_query)
                if not cached.empty:
                    all_results.append(cached)
                else:
                    missing_dates.append(trade_date)
            except DataNotFoundError:
                missing_dates.append(trade_date)
        
        # 第二步：如果有缺失日期，执行 pipeline 填充
        if missing_dates:
            logger.warning("⚠️ Missing %d dates, fetching from API: %s...", len(missing_dates), missing_dates[:3])
            
            for trade_date in missing_dates:
                day_result = self._execute_single_day_pipeline(pipeline, trade_date, query)
                if day_result is not None and not day_result.empty:
                    all_results.append(day_result)
                    
                    # 自动缓存
                    if meta.date_column and meta.date_column in day_result.columns:
                        pk = meta.partition_key_template.format(
                            date=trade_date,
                            index_code=(query.index_code or "").replace(".", "_"),
                        )
                        self._safe_save(query.dataset, day_result, pk)
        
        if not all_results:
            raise DataNotFoundError(f"No data for {query.dataset.value} range query")
        
        result = pd.concat(all_results, ignore_index=True)
        logger.info("✅ Range query completed: %d rows from %d days", len(result), len(all_results))
        
        # 数据质量检测
        nan_ratio = self._check_data_quality(result)
        if nan_ratio > 0.5:
            logger.error(
                "❌ Data quality check FAILED: %.1f%% NaN values. Not saving to cache.",
                nan_ratio * 100,
            )
        elif nan_ratio > 0.1:
            logger.warning("⚠️ Data quality WARNING: %.1f%% NaN values.", nan_ratio * 100)
        
        return self._apply_filters(result, query, meta)

    def _execute_pipeline(
        self,
        pipeline: list[FetchStep],
        query: Query,
    ) -> pd.DataFrame | None:
        base: pd.DataFrame | None = None

        for i, step in enumerate(pipeline):
            # 范围查询时，跳过只依赖 date 参数的可选步骤
            if query.is_range and step.optional:
                mapping_values = set(step.param_mapping.values())
                is_date_only_api = mapping_values <= {"date", "trade_date"}
                if is_date_only_api:
                    logger.debug(
                        "Skipping optional date-only step %s in range query",
                        step.api_name,
                    )
                    continue
            
            params = self._build_api_params(step, query)

            result = self.source.call(step.api_name, params)
            if step.rate_limit_sleep > 0:
                time.sleep(step.rate_limit_sleep)

            if result is None or result.empty:
                if i == 0:
                    return None
                if not step.optional:
                    logger.warning(
                        "Required step %s returned empty, continuing with partial data",
                        step.api_name,
                    )
                continue

            if step.fields:
                keep = list(set(step.fields) | set(step.merge_on))
                available = [c for c in keep if c in result.columns]
                result = result[available]

            if i == 0:
                base = result
            else:
                base = base.merge(  # type: ignore[union-attr]
                    result,
                    on=step.merge_on,
                    how="left",
                    suffixes=("", f"__{step.api_name}"),
                )

        if base is not None:
            base = self._clean_duplicate_columns(base)

        return base

    def _build_api_params(
        self,
        step: FetchStep,
        query: Query,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        for api_param, query_field in step.param_mapping.items():
            value = getattr(query, query_field, None)
            if value is not None:
                params[api_param] = value
        params.update(step.fixed_params)
        
        if step.fields:
            params["fields"] = ",".join(step.fields)
        return params

    def _resolve_partition_key(self, query: Query, meta: DatasetMeta) -> str:
        index_code_safe = ""
        if query.index_code:
            index_code_safe = query.index_code.replace(".", "_")
        return meta.partition_key_template.format(
            date=query.date or "",
            index_code=index_code_safe,
        )

    def _apply_filters(
        self,
        data: pd.DataFrame,
        query: Query,
        meta: DatasetMeta,
    ) -> pd.DataFrame:
        if query.codes and meta.code_column in data.columns:
            data = data[data[meta.code_column].isin(query.codes)]
        if query.fields:
            available = [c for c in query.fields if c in data.columns]
            if available:
                data = data[available]
        return data

    def _check_data_quality(self, data: pd.DataFrame) -> float:
        """
        检查数据质量，计算 NaN 比例。
        
        Args:
            data: 要检查的 DataFrame
            
        Returns:
            NaN 单元格占总单元格的比例 (0.0 ~ 1.0)
        """
        if data is None or data.empty:
            return 1.0  # 空数据视为 100% NaN
        
        total_cells = data.size
        if total_cells == 0:
            return 1.0
        
        nan_count = data.isna().sum().sum()
        nan_ratio = nan_count / total_cells
        
        return nan_ratio

    def _clean_duplicate_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        dupe_cols = [c for c in df.columns if "__" in c]
        if dupe_cols:
            df = df.drop(columns=dupe_cols)
        return df

    def _safe_save(
        self,
        dataset: Dataset,
        data: pd.DataFrame,
        partition_key: str,
    ) -> bool:
        """Save data and return True if successful, False otherwise."""
        try:
            result = self.store.save(dataset, data, partition_key)
            if result:
                logger.info("Auto-cached: %s/%s", dataset.value, partition_key)
            else:
                # 明确记录保存失败的原因（空数据或 save 返回 False）
                if data is None or data.empty:
                    logger.warning("⚠️ Auto-cache skipped: %s/%s (empty data)", dataset.value, partition_key)
                else:
                    logger.warning("⚠️ Auto-cache returned False: %s/%s (possible I/O error)", dataset.value, partition_key)
            return result
        except Exception as e:
            logger.error("❌ Auto-cache failed with exception: %s/%s, error=%s", dataset.value, partition_key, e)
            logger.debug("Exception details:", exc_info=True)
            return False

    def _get_date_range(self, query: Query) -> list[str]:
        """Return full calendar range [start_date, end_date] so missing dates are fetched, not skipped."""
        start_dt = datetime.strptime(query.start_date or "", "%Y%m%d")
        end_dt = datetime.strptime(query.end_date or "", "%Y%m%d")
        dates: list[str] = []
        current = start_dt
        while current <= end_dt:
            dates.append(current.strftime("%Y%m%d"))
            current += timedelta(days=1)
        return dates
    
    def _execute_single_day_pipeline(
        self,
        pipeline: list[FetchStep],
        trade_date: str,
        original_query: Query,
    ) -> pd.DataFrame | None:
        """执行单日的 pipeline。"""
        base: pd.DataFrame | None = None
        
        for i, step in enumerate(pipeline):
            # 构建单日查询参数
            single_query = Query(
                dataset=original_query.dataset,
                date=trade_date,
                codes=original_query.codes,
                fields=original_query.fields,
                index_code=original_query.index_code,
            )
            
            params = self._build_api_params(step, single_query)
            
            result = self.source.call(step.api_name, params)
            if step.rate_limit_sleep > 0:
                time.sleep(step.rate_limit_sleep)
            
            if result is None or result.empty:
                if i == 0:
                    return None
                if not step.optional:
                    logger.debug("Step %s returned empty for %s", step.api_name, trade_date)
                continue
            
            if step.fields:
                keep = list(set(step.fields) | set(step.merge_on))
                available = [c for c in keep if c in result.columns]
                result = result[available]
            
            if i == 0:
                base = result
            else:
                base = base.merge(
                    result,
                    on=step.merge_on,
                    how="left",
                    suffixes=("", f"__{step.api_name}"),
                )
        
        if base is not None:
            base = self._clean_duplicate_columns(base)
        
        return base
