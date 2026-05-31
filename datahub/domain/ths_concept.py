"""ThsConcept domain: 同花顺概念成分股数据.

特性：
- 按日缓存：每天的概念数据缓存为一个Parquet文件
- 缓存路径：使用 .env 中的 DATA_CACHE_ROOT/ths_concept
- 自动合并：所有概念的成分股合并后保存为单个文件
"""

from __future__ import annotations

import logging
from datetime import datetime

import polars as pl

from datahub.core.dataset import Dataset
from datahub.core.query import Query
from datahub.core.repository import Repository

logger = logging.getLogger(__name__)


class ThsConcept:
    """同花顺概念数据领域层实现。
    
    负责从Tushare API获取概念数据，并通过Repository进行缓存管理。
    """

    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    def get_concepts(self, trade_date: str | None = None) -> pl.DataFrame:
        """获取指定日期的概念成分股数据。
        
        Args:
            trade_date: 交易日期（YYYYMMDD格式），如果为None则使用最新可用日期
            
        Returns:
            DataFrame (concept_code, stock_code, stock_name, concept_name)
            - concept_code: 概念代码 (如 883300.TI)
            - stock_code: 股票代码 (如 000001.SZ)
            - stock_name: 股票名称 (如 平安银行)
            - concept_name: 概念名称 (如 沪深300样本股)
        """
        if trade_date is None:
            trade_date = self._get_latest_available_date()
            if trade_date is None:
                logger.warning("[WARN] 无可用日期，将从API获取")
                trade_date = datetime.now().strftime("%Y%m%d")
        
        logger.info(f"[DATA] 正在加载 {trade_date} 的概念数据...")
        
        # 尝试从缓存加载（按月）
        try:
            # 将日期转换为月份格式 (YYYYMM)
            month_key = trade_date[:6]  # 取前6位，如 "202501"
            query = Query(
                dataset=Dataset.THS_CONCEPT,
                date=month_key,  # 使用月份作为缓存键
            )
            cached_data = self._repo.load(query)
            
            if not cached_data.is_empty():
                logger.info(f"[OK] 从缓存加载概念数据（{month_key}）：{len(cached_data)} 条记录")
                return cached_data
        except Exception as e:
            logger.debug(f"缓存加载失败：{e}")
        
        # 缓存未命中，从API获取
        logger.info("[DATA] 缓存未命中，从 Tushare API 获取...")
        fresh_data = self._fetch_from_api(trade_date)
        
        if fresh_data.is_empty():
            logger.warning("[WARN] 从API获取的数据为空")
            return fresh_data
        
        # 保存到缓存（按月）
        try:
            # 将日期转换为月份格式 (YYYYMM)
            month_key = trade_date[:6]  # 取前6位，如 "202501"
            self._repo.save(Dataset.THS_CONCEPT, fresh_data, month_key)
            logger.info(f"[OK] 概念数据已缓存（{month_key}）：{len(fresh_data)} 条记录")
        except Exception as e:
            logger.error(f"[ERROR] 缓存保存失败：{e}")
        
        return fresh_data

    def get_aggregated_concepts(self, trade_date: str | None = None) -> pl.DataFrame:
        """获取按股票聚合的概念信息。
        
        Args:
            trade_date: 交易日期（YYYYMMDD格式）
            
        Returns:
            DataFrame (stock_code, ths_concepts)
            其中 stock_code 是股票代码，ths_concepts 是用 | 分隔的概念字符串
        """
        concept_df = self.get_concepts(trade_date)
        
        if concept_df.is_empty() or "concept_name" not in concept_df.columns:
            return pl.DataFrame(schema={"stock_code": pl.String, "ths_concepts": pl.String})
        
        aggregated = (
            concept_df
            .group_by("stock_code")  # 按股票代码分组
            .agg(
                pl.col("concept_name")  # 聚合概念名称
                .drop_nulls()
                .unique()
                .sort()
                .str.join("|")
                .alias("ths_concepts")
            )
        )
        
        logger.info(f"[OK] 聚合完成：{len(aggregated)} 只股票有概念信息")
        return aggregated

    def available_dates(self) -> list[str]:
        """获取可用的概念数据日期列表。"""
        return self._repo.available_dates(Dataset.THS_CONCEPT)

    def latest_date(self) -> str | None:
        """获取最新的概念数据日期。"""
        return self._repo.latest_date(Dataset.THS_CONCEPT)

    def _get_latest_available_date(self) -> str | None:
        """获取最新可用日期（优先从缓存，否则返回None）。"""
        latest_month = self.latest_date()
        if latest_month:
            # 将月份格式 (YYYYMM) 转换为日期格式 (YYYYMMDD)，取月末
            try:
                year = int(latest_month[:4])
                month = int(latest_month[4:6])
                # 简单处理：取当月1日
                return f"{year:04d}{month:02d}01"
            except Exception:
                pass
        
        # 如果缓存中没有，尝试从日历获取最新交易日
        try:
            from datahub.domain.calendar import Calendar
            calendar = Calendar()
            latest_trade = calendar.latest_trade_date()
            if latest_trade:
                return latest_trade.strftime("%Y%m%d")
        except Exception:
            pass
        
        return None

    def _fetch_from_api(self, trade_date: str) -> pl.DataFrame:
        """从 Tushare API 获取概念数据。
        
        Args:
            trade_date: 交易日期（YYYYMMDD格式）
            
        Returns:
            DataFrame (concept_code, stock_code, stock_name, concept_name)
            - concept_code: 概念代码 (如 883300.TI)
            - stock_code: 股票代码 (如 000001.SZ)
            - stock_name: 股票名称 (如 平安银行)
            - concept_name: 概念名称 (如 沪深300样本股)
        """
        try:
            from datahub.source.tushare_source import TushareSource
            from infrastructure.config.settings import get_settings
            
            settings = get_settings()
            source = TushareSource(token=settings.data.source_token)
            
            # Step 1: 获取所有同花顺概念指数列表
            logger.info("  [1/2] 获取概念指数列表...")
            concept_index_df = source.fetch("ths_index", {"type": "N"})
            
            if concept_index_df is None or concept_index_df.is_empty():
                logger.warning("[WARN] 未获取到概念指数列表")
                return pl.DataFrame()
            
            concept_codes = concept_index_df.select("ts_code").to_series().to_list()
            logger.info(f"    ✅ 获取到 {len(concept_codes)} 个概念指数")
            
            # Step 2: 批量获取每个概念的成分股
            logger.info(f"  [2/2] 批量获取成分股 (共 {len(concept_codes)} 个概念)...")
            
            # 创建概念代码到名称的映射
            concept_name_map = concept_index_df.select(["ts_code", "name"]).rename({
                "ts_code": "concept_code",  # 重命名为concept_code
                "name": "concept_name"       # 概念名称
            })
            
            all_members = []
            total = len(concept_codes)
            
            for idx, code in enumerate(concept_codes, 1):
                try:
                    members_df = source.fetch("ths_member", {"ts_code": code})
                    if members_df is not None and not members_df.is_empty():
                        # 重命名字段为清晰的名称
                        members_df = members_df.rename({
                            "ts_code": "concept_code",  # API返回的ts_code实际是概念代码
                            "con_code": "stock_code",   # API返回的con_code实际是股票代码
                            "con_name": "stock_name"    # API返回的con_name实际是股票名称
                        })
                        all_members.append(members_df)
                    
                    # 每50个打印进度
                    if idx % 50 == 0 or idx == total:
                        logger.info(f"    进度: {idx}/{total} ({idx*100//total}%)")
                        
                except Exception as e:
                    logger.debug(f"    获取概念 {code} 成分股失败: {e}")
                    continue
            
            if all_members:
                result = pl.concat(all_members)
                logger.info(f"    ✅ 共获取 {len(result)} 条成分股记录")
                logger.info(f"    📋 原始字段: {result.columns}")
                
                # 添加概念名称（通过concept_code进行join）
                result = result.join(concept_name_map, on="concept_code", how="left")
                logger.info(f"    ✅ 已添加概念名称字段")
                logger.info(f"    📋 最终字段: {result.columns}")
            else:
                result = pl.DataFrame()
                logger.warning("    ⚠️  未获取到任何成分股")
            
            return result
                
        except Exception as e:
            logger.error(f"[ERROR] 从API加载概念数据失败: {e}", exc_info=True)
            return pl.DataFrame()
