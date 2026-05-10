"""股票池服务 - 独立的股票池过滤模块.

职责：
1. 执行基础数据过滤（ST、停牌、上市天数）
2. 调用 IndustryMatcher 进行 LLM 行业匹配
3. 应用价格、市值、完整性等业务过滤规则
"""

from __future__ import annotations

import traceback
from datetime import datetime
from typing import Any
import polars as pl

from datahub import Calendar
from datahub.loaders import load_raw_market_data
from infrastructure.logging.logger import get_logger
from src.screening.industry_matcher import IndustryMatcher
from src.screening.stock_pool_filter import StockPoolFilter
from utils.agent.llm_helper import build_llm_from_api_config

logger = get_logger(__name__)


class StockPoolService:
    """股票池服务 - 负责股票池的过滤和管理."""
    
    def __init__(self, settings: Any):
        """初始化股票池服务.
        
        Args:
            settings: 全局配置对象
        """
        self.settings = settings
    
    def apply_filter(
        self, 
        raw_data: pl.DataFrame | None = None,
    ) -> tuple[pl.DataFrame, list[str], pl.DataFrame | None]:
        """应用股票池过滤.
        
        Args:
            raw_data: 原始市场数据 DataFrame（polars 或 pandas），如果为 None 则自动加载

        Returns:
            (过滤后的DataFrame, 过滤后的股票代码列表, 指数数据DataFrame)
        """
        # 1. 加载或验证原始数据
        if raw_data is None:
            logger.info("[DATA] StockPoolService 正在加载原始市场数据...")
            
            # 获取最新交易日期
            calendar = Calendar()
            today = datetime.now().strftime("%Y%m%d")
            latest_trade_date = calendar.get_latest_trade_date(today)
            if not latest_trade_date:
                latest_trade_date = today
            
            # 计算数据起始日期
            from datahub.calendar_utils import get_data_start_date
            observation_days = self.settings.observation_days
            start_date = get_data_start_date(latest_trade_date, observation_days=observation_days)
            
            # 加载原始市场数据
            raw_data = load_raw_market_data(
                start_date=start_date,
                end_date=latest_trade_date,
                exclude_st=False,
                min_list_days=0,
            )
            
            logger.info(f"[OK] 已加载 {len(raw_data)} 条记录")
        else:
            # 从传入的数据中提取日期范围（Polars）
            dates = raw_data.select(pl.col("trade_date").unique()).to_series()
            
            if len(dates) > 0:
                latest_trade_date = str(dates.max()).replace('-', '')[:8]
            else:
                raise ValueError("无法从 raw_data 中提取交易日期")
        
        # 2. 统一加载指数数据（所有模式都需要）
        index_data = self._load_index_data_from_raw(raw_data)
        
        # 从 raw_data 中提取价格数据（已经是 MultiIndex 格式）
        df_price = raw_data.clone()
        logger.info(f"[DATA] 使用已加载的价格数据：{len(df_price)} 条记录")
        
        # 加载股票基本信息（用于 ST、上市天数等过滤）
        logger.info(f"[DATA] 加载股票基本信息...")
        from datahub import Stock
        stock = Stock()
        basic_df = stock.universe()
        if basic_df is None or basic_df.is_empty():
            raise ValueError("无法获取股票基本信息")
        
        # 1. 基础过滤（ST、停牌、上市天数）
        stock_codes = self._filter_stock_pool_basic(
            data=raw_data,
            basic_df=basic_df,
            latest_trade_date=latest_trade_date,
        )
        logger.info(f"[DATA] 基础过滤后：{len(stock_codes)} 只股票")
        
        # 2. 行业过滤（LLM 智能匹配）
        if self.settings.stock_pool.industry:
            stock_codes = self._apply_industry_filter(df_price, basic_df, stock_codes)
        
        # 3. 价格/流动性过滤
        pool_filter = StockPoolFilter(self.settings.stock_pool)
        df_filtered = pool_filter._filter_price_data(df_price, stock_codes)
        
        if not df_filtered.is_empty() and "ts_code" in df_filtered.columns:
            stock_codes = df_filtered["ts_code"].drop_nulls().unique().to_list()
            logger.info(f"[DATA] 价格/流动性过滤后：{len(stock_codes)} 只股票")
        
        # 4. 市值过滤
        stock_codes = pool_filter._filter_market_value(df_filtered, stock_codes)
        logger.info(f"[DATA] 市值过滤后：{len(stock_codes)} 只股票")
        
        # 5. 数据完整性过滤
        stock_codes = pool_filter.filter_by_completeness(df_filtered, stock_codes)
        logger.info(f"[DATA] 完整性过滤后：{len(stock_codes)} 只股票")
        
        # 过滤到最终股票池
        filtered_data = df_filtered.filter(pl.col("ts_code").is_in(stock_codes))
        
        # index_data 可能为 None（指数数据加载失败），由调用方决定如何处理
        if index_data is None:
            logger.warning("[WARN] 指数数据加载失败，返回 None。使用指数相关工具时将无法正常工作。")
        
        return filtered_data, stock_codes, index_data
    
    def _filter_stock_pool_basic(
        self,
        data: pl.DataFrame,
        basic_df: pl.DataFrame,
        latest_trade_date: str,
    ) -> list[str]:
        """执行股票池基础过滤（ST、停牌、上市天数）。
        
        Args:
            data: 市场数据 DataFrame（包含价格信息）
            basic_df: 股票基本信息 DataFrame（包含 ts_code, name, industry, list_date 等）
            latest_trade_date: 最新交易日期（YYYYMMDD）
            
        Returns:
            过滤后的股票代码列表
        """
        if basic_df is None or basic_df.is_empty():
            return []
        
        stock_codes = basic_df["ts_code"].drop_nulls().unique().to_list()
        
        # 排除 ST 股票
        if self.settings.stock_pool.exclude_st:
            # 修复：使用 ^ 锚定开头，避免误匹配名称中包含 "ST" 的正常股票
            # 匹配规则：以 "ST" 或 "*ST" 开头的股票名称
            st_mask = basic_df["name"].str.contains(r"^\*?ST").fill_null(False)
            filtered_df = basic_df.filter(~st_mask)
            stock_codes = filtered_df["ts_code"].drop_nulls().unique().to_list()
            removed_count = len(basic_df) - len(filtered_df)
            if removed_count > 0:
                logger.info(f"   [OK] ST股票过滤：-{removed_count} 只，剩余 {len(stock_codes)} 只")
        
        # 排除停牌股票（vol=0）
        if not data.is_empty() and "vol" in data.columns:
            latest_date_data = data.filter(pl.col("trade_date") == latest_trade_date)
            if not latest_date_data.is_empty():
                active_stocks = latest_date_data.filter(pl.col("vol") > 0).select("ts_code").unique().to_series().to_list()
                stock_codes = [code for code in stock_codes if code in active_stocks]
        
        # 排除上市天数不足的股票（向量化操作）
        min_list_days = self.settings.stock_pool.min_list_days
        if min_list_days > 0 and "list_date" in basic_df.columns:
            cutoff_date = datetime.strptime(latest_trade_date, "%Y%m%d")
            
            # 向量化计算上市天数
            filtered_df = basic_df.with_columns(
                pl.col("list_date").str.strptime(pl.Date, format="%Y%m%d").alias("list_date_parsed")
            ).with_columns(
                ((pl.lit(cutoff_date) - pl.col("list_date_parsed")).dt.total_days()).alias("days_listed")
            ).filter(
                pl.col("days_listed") >= min_list_days
            )
            
            stock_codes = filtered_df["ts_code"].drop_nulls().unique().to_list()
        
        return stock_codes
    
    def _load_index_data_from_raw(self, raw_data: pl.DataFrame) -> pl.DataFrame | None:
        """从原始数据中自动加载指数数据.
        
        Args:
            raw_data: 原始市场数据 DataFrame
            
        Returns:
            指数数据 DataFrame，或 None
        """
        try:
            # 提取日期范围（Polars）
            dates = raw_data.select(pl.col("trade_date").unique()).to_series()
            
            if len(dates) == 0:
                logger.warning("[WARN] 无法从 raw_data 中提取日期")
                return None
            
            start_date = str(dates.min()).replace('-', '')[:8]
            end_date = str(dates.max()).replace('-', '')[:8]
            
            # 根据股票代码推导需要加载的指数代码
            stock_codes = raw_data.select(pl.col("ts_code").unique()).to_series().to_list()
            index_codes = self._derive_index_codes(stock_codes)
            
            logger.info(f"[DATA] 正在加载指数数据 ({start_date} ~ {end_date})...")
            index_data = self._load_index_data(index_codes, start_date, end_date)
            
            if index_data is not None and not index_data.is_empty():
                logger.info(f"[OK] 成功加载指数数据: {len(index_data)} 条记录")
            else:
                logger.warning("[WARN] 指数数据加载返回空结果")
                index_data = None
            
            return index_data
            
        except Exception as e:
            logger.error(f"[ERROR] 指数数据加载失败: {e}")
            logger.debug(traceback.format_exc())
            return None
    
    def _derive_index_codes(self, stock_codes: list[str]) -> list[str]:
        """根据股票代码推导对应的指数代码列表.
        
        Args:
            stock_codes: 股票代码列表
            
        Returns:
            去重后的指数代码列表
        """
        from datahub.domain.index_selector import get_index_code
        
        if not stock_codes:
            return []
        
        # 使用 Polars map_elements 批量获取指数代码
        stock_df = pl.DataFrame({"ts_code": stock_codes})
        stock_with_index = stock_df.with_columns(
            pl.col("ts_code").map_elements(get_index_code, return_dtype=pl.Utf8).alias("index_code")
        )
        
        # 分组统计
        index_stock_map = {}
        for idx_code, group_df in stock_with_index.group_by("index_code"):
            # Polars group_by 返回的 key 可能是 tuple，需要转换为字符串
            if isinstance(idx_code, tuple):
                idx_code = idx_code[0]
            codes = group_df["ts_code"].to_list()
            index_stock_map[idx_code] = codes
        
        logger.info(f"[DATA] 检测到 {len(index_stock_map)} 个指数板块")
        
        return list(index_stock_map.keys())
    
    def _load_index_data(self, index_codes: list[str], start_date: str, end_date: str) -> pl.DataFrame | None:
        """加载指数数据.
        
        Args:
            index_codes: 指数代码列表
            start_date: 起始日期
            end_date: 结束日期
            
        Returns:
            指数数据 DataFrame (polars)，或 None
        """
        try:
            from datahub import Index
            
            if not index_codes:
                logger.warning("[WARN] 指数代码列表为空")
                return None
            
            # 加载所有需要的指数数据
            from datahub import Index
            
            # 使用默认配置（从 .env 自动读取）
            index = Index()
            
            # 使用 batch_level 批量加载（内部已实现缓存和并行）
            combined_data = index.batch_level(
                index_codes=index_codes,
                start_date=start_date,
                end_date=end_date,
                freq="daily",
            )
            
            if combined_data is None or combined_data.is_empty():
                logger.warning("[WARN] 所有指数数据均为空")
                return None
            
            logger.info(f"[OK] 成功加载指数数据: {len(combined_data)} 条记录, {len(index_codes)} 个指数")
            return combined_data
            
        except Exception as e:
            logger.error(f"[ERROR] 加载指数数据失败: {e}")
            logger.debug(traceback.format_exc())
            return None
    

    
    def _apply_industry_filter(
        self, 
        df_price: pl.DataFrame, 
        raw_data: pl.DataFrame, 
        stock_codes: list[str]
    ) -> list[str]:
        """应用行业过滤.
        
        Args:
            df_price: 价格数据
            raw_data: 原始数据（包含行业信息）
            stock_codes: 当前股票代码列表
            
        Returns:
            过滤后的股票代码列表
        """
        logger.info(f"[TARGET] 开始行业过滤，配置的行业：{self.settings.stock_pool.industry}")
        
        # 提取行业信息
        basic_df = raw_data.clone()
        if "industry" not in basic_df.columns:
            logger.warning("[WARN] 数据中缺少 industry 列，跳过行业过滤")
            return stock_codes
        
        # 从 basic_df 中提取行业映射（Polars）
        industry_map = basic_df.select(["ts_code", "industry"]).unique(subset=["ts_code"], keep="first")
        industry_map = industry_map.rename({"industry": "industry_name"})
        
        # 将价格数据转换为普通 DataFrame（处理 MultiIndex）
        df_price_flat = df_price.clone()
        
        # 将行业信息合并到价格数据（Polars join）
        if "ts_code" in df_price_flat.columns:
            df_with_industry = df_price_flat.join(industry_map, on="ts_code", how="left", suffix="_dup")
            # 移除带 _dup 后缀的列
            dup_cols = [col for col in df_with_industry.columns if col.endswith("_dup")]
            if dup_cols:
                df_with_industry = df_with_industry.drop(dup_cols)
        else:
            logger.warning("[WARN] 价格数据中缺少 ts_code 列，跳过行业过滤")
            return stock_codes
        
        # 检查 industry 列是否存在
        if "industry_name" not in df_with_industry.columns:
            logger.warning("[WARN] 合并后缺少 industry_name 列，跳过行业过滤")
            return stock_codes
        
        # 使用 LLM 匹配行业
        llm = build_llm_from_api_config(self.settings.llm.to_dict())
        matcher = IndustryMatcher(llm)
        
        available_industries = df_with_industry["industry_name"].drop_nulls().unique().to_list()
        matched_industries = matcher.match_industries(self.settings.stock_pool.industry, available_industries)
        
        if matched_industries:
            # Polars 过滤
            df_with_industry = df_with_industry.filter(pl.col("industry_name").is_in(matched_industries))
            stock_codes = df_with_industry["ts_code"].drop_nulls().unique().to_list()
            logger.info(f"[OK] 行业过滤：{len(matched_industries)} 个行业，{len(stock_codes)} 只股票")
        
        return stock_codes
