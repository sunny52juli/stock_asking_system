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
from infrastructure.logging.logger import get_logger
from src.agent.initialization.data_loader import DataLoader
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
        # 如果未提供数据，则自动加载
        if raw_data is None:
            logger.info("📊 StockPoolService 正在加载原始市场数据...")
            data_loader = DataLoader(self.settings)
            raw_data, stock_codes, index_data = data_loader.load_raw_market_data()
            
            # 如果 index_data 为空，尝试单独加载指数数据
            if index_data is None or (hasattr(index_data, 'is_empty') and index_data.is_empty()):
                logger.warning("⚠️ 指数数据为空，尝试重新加载...")
                try:
                    # 使用 DataLoader 实例的方法加载指数数据
                    index_data = data_loader._load_index_data(raw_data)
                    if index_data is not None:
                        logger.info(f"✅ 成功加载指数数据: {len(index_data)} 条记录")
                    else:
                        logger.error("❌ 指数数据加载失败，将使用空指数数据")
                except Exception as e:
                    logger.error(f"❌ 指数数据重新加载失败: {e}")
                    logger.debug(traceback.format_exc())
            
            logger.info(f"✅ 已加载 {len(raw_data)} 条记录，{len(stock_codes)} 只股票")
        else:
            # 从传入的数据中提取信息（回测模式）
            index_data = None
            
            # 需要单独加载指数数据
            logger.info("📊 回测模式：需要单独加载指数数据...")
            try:
                # 从 raw_data 中提取股票代码和日期范围
                if hasattr(raw_data, 'filter') and not hasattr(raw_data, 'loc'):
                    # Polars
                    stock_codes_list = raw_data.select(pl.col("ts_code").unique()).to_series().to_list()
                    dates = raw_data.select(pl.col("trade_date").unique()).to_series()
                else:
                    # Pandas
                    stock_codes_list = raw_data.index.get_level_values('ts_code').unique().tolist()
                    dates = raw_data.index.get_level_values('trade_date').unique()
                
                if len(dates) > 0 and stock_codes_list:
                    start_date = str(dates.min()).replace('-', '')[:8]
                    end_date = str(dates.max()).replace('-', '')[:8]
                    
                    data_loader = DataLoader(self.settings)
                    index_data = data_loader._load_index_data(stock_codes_list, start_date, end_date)
                    
                    if index_data is not None and not (hasattr(index_data, 'is_empty') and index_data.is_empty()):
                        logger.info(f"✅ 成功加载指数数据: {len(index_data)} 条记录")
                    else:
                        logger.warning("⚠️ 指数数据加载返回空结果")
                        index_data = None
                else:
                    logger.warning("⚠️ 无法从 raw_data 中提取股票代码或日期范围")
            except Exception as e:
                logger.error(f"❌ 指数数据加载失败: {e}")
                logger.debug(traceback.format_exc())
                index_data = None
        
        # 获取最新交易日期
        
        calendar = Calendar()
        today = datetime.now().strftime("%Y%m%d")
        latest_trade_date = calendar.get_latest_trade_date(today)
        
        if not latest_trade_date:
            latest_trade_date = today
        
        # 从 raw_data 中提取价格数据（已经是 MultiIndex 格式）
        df_price = self._extract_basic_info(raw_data)
        logger.info(f"📊 使用已加载的价格数据：{len(df_price)} 条记录")
        
        # 加载股票基本信息（用于 ST、上市天数等过滤）
        logger.info(f"📊 加载股票基本信息...")
        data_loader = DataLoader(self.settings)
        basic_df = data_loader._load_basic_info()
        
        # 1. 基础过滤（ST、停牌、上市天数）
        stock_codes = self._filter_stock_pool_basic(
            data=raw_data,
            basic_df=basic_df,
            latest_trade_date=latest_trade_date,
        )
        logger.info(f"📊 基础过滤后：{len(stock_codes)} 只股票")
        
        # 2. 行业过滤（LLM 智能匹配）
        if self.settings.stock_pool.industry:
            stock_codes = self._apply_industry_filter(df_price, basic_df, stock_codes)
        
        # 3. 价格/流动性过滤
        pool_filter = StockPoolFilter(self.settings.stock_pool)
        df_filtered = pool_filter._filter_price_data(df_price, stock_codes)
        
        # Polars: is_empty() 代替 .empty
        df_is_empty = (hasattr(df_filtered, 'is_empty') and df_filtered.is_empty()) or (hasattr(df_filtered, 'empty') and df_filtered.empty)
        if not df_is_empty and "ts_code" in df_filtered.columns:
            ts_code_col = df_filtered["ts_code"]
            if hasattr(ts_code_col, 'drop_nulls'):
                stock_codes = ts_code_col.drop_nulls().unique().to_list()
            else:
                stock_codes = ts_code_col.dropna().unique().tolist()
            logger.info(f"📊 价格/流动性过滤后：{len(stock_codes)} 只股票")
        
        # 4. 市值过滤
        stock_codes = pool_filter._filter_market_value(df_filtered, stock_codes)
        logger.info(f"📊 市值过滤后：{len(stock_codes)} 只股票")
        
        # 5. 数据完整性过滤
        stock_codes = pool_filter.filter_by_completeness(df_filtered, stock_codes)
        logger.info(f"📊 完整性过滤后：{len(stock_codes)} 只股票")
        
        # 过滤到最终股票池（保持 polars 格式）
        if hasattr(df_filtered, 'filter') and not hasattr(df_filtered, 'loc'):
            filtered_data = df_filtered.filter(pl.col("ts_code").is_in(stock_codes))
        else:
            filtered_data = df_filtered[df_filtered["ts_code"].isin(stock_codes)].copy()
        
        # 确保 index_data 不为 None
        if index_data is None:
            logger.warning("⚠️ 指数数据为 None，创建空 DataFrame")
            index_data = pl.DataFrame({
                "index_code": [],
                "trade_date": [],
                "close": []
            })
        
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
        # Polars: is_empty() 代替 .empty
        if basic_df is None or (hasattr(basic_df, 'is_empty') and basic_df.is_empty()) or (hasattr(basic_df, 'empty') and basic_df.empty):
            return []
        
        # Polars: drop_nulls() 代替 dropna()
        ts_code_col = basic_df["ts_code"]
        if hasattr(ts_code_col, 'drop_nulls'):
            stock_codes = ts_code_col.drop_nulls().unique().to_list()
        else:
            stock_codes = ts_code_col.dropna().unique().tolist()
        
        # 排除 ST 股票
        if self.settings.stock_pool.exclude_st:
            # Polars: str.contains() 不支持 na 参数，用 fill_null(False) 代替
            name_col = basic_df["name"]
            if hasattr(name_col, 'str'):
                st_mask = name_col.str.contains(r"ST|\*ST").fill_null(False)
            else:
                st_mask = name_col.str.contains(r"ST|\*ST", na=False)
            filtered_df = basic_df.filter(~st_mask) if hasattr(basic_df, 'filter') else basic_df[~st_mask]
            ts_code_col = filtered_df["ts_code"]
            if hasattr(ts_code_col, 'drop_nulls'):
                stock_codes = ts_code_col.drop_nulls().unique().to_list()
            else:
                stock_codes = ts_code_col.dropna().unique().tolist()
        
        # 排除停牌股票（vol=0）
        # Polars: is_empty() 代替 .empty
        data_is_empty = (hasattr(data, 'is_empty') and data.is_empty()) or (hasattr(data, 'empty') and data.empty)
        if not data_is_empty and "vol" in data.columns:
            # Polars: 用 filter() 代替索引访问
            if hasattr(data, 'filter') and not hasattr(data, 'loc'):
                latest_date_data = data.filter(pl.col("trade_date") == latest_trade_date)
            else:
                # Pandas MultiIndex
                if hasattr(data, 'index') and isinstance(data.index, pd.MultiIndex):
                    latest_date_data = data[data.index.get_level_values('trade_date') == pd.to_datetime(latest_trade_date)]
                else:
                    latest_date_data = data[data["trade_date"] == pd.to_datetime(latest_trade_date)]
            # Polars: is_empty() 代替 .empty
            latest_is_empty = (hasattr(latest_date_data, 'is_empty') and latest_date_data.is_empty()) or (hasattr(latest_date_data, 'empty') and latest_date_data.empty)
            if not latest_is_empty:
                # Polars: 直接用列过滤
                active_stocks = latest_date_data.filter(pl.col("vol") > 0).select("ts_code").unique().to_series().to_list()
                stock_codes = [code for code in stock_codes if code in active_stocks]
        
        # 排除上市天数不足的股票
        min_list_days = self.settings.stock_pool.min_list_days
        if min_list_days > 0 and "list_date" in basic_df.columns:
            cutoff_date = datetime.strptime(latest_trade_date, "%Y%m%d")
            valid_codes = []
            for code in stock_codes:
                row = basic_df.filter(pl.col("ts_code") == code)
                if not row.is_empty():
                    list_date_str = row.select("list_date").to_series().to_list()[0]
                    if isinstance(list_date_str, str):
                        try:
                            list_date = datetime.strptime(list_date_str, "%Y%m%d")
                            days_listed = (cutoff_date - list_date).days
                            if days_listed >= min_list_days:
                                valid_codes.append(code)
                        except ValueError:
                            pass
            stock_codes = valid_codes
        
        return stock_codes
    
    def _extract_basic_info(self, data: pl.DataFrame) -> pl.DataFrame:
        """从数据中提取基本信息.
        
        Args:
            data: 市场数据 DataFrame（polars）
            
        Returns:
            基本信息 DataFrame
        """
        return data.clone()
    
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
        logger.info(f"🎯 开始行业过滤，配置的行业：{self.settings.stock_pool.industry}")
        
        # 提取行业信息
        basic_df = self._extract_basic_info(raw_data)
        if "industry" not in basic_df.columns:
            logger.warning("⚠️ 数据中缺少 industry 列，跳过行业过滤")
            return stock_codes
        
        # 从 basic_df 中提取行业映射
        # Polars: unique() 代替 drop_duplicates()
        if hasattr(basic_df, 'unique'):
            industry_map = basic_df.select(["ts_code", "industry"]).unique(subset=["ts_code"], keep="first")
            industry_map = industry_map.rename({"industry": "industry_name"})
        else:
            industry_map = basic_df[["ts_code", "industry"]].drop_duplicates("ts_code", keep="first")
            industry_map = industry_map.rename(columns={"industry": "industry_name"})
        
        # 将价格数据转换为普通 DataFrame（处理 MultiIndex）
        df_price_flat = self._extract_basic_info(df_price)
        
        # 将行业信息合并到价格数据
        if "ts_code" in df_price_flat.columns:
            # Polars: join() 代替 merge()
            if hasattr(df_price_flat, 'join') and not hasattr(df_price_flat, 'loc'):
                df_with_industry = df_price_flat.join(industry_map, on="ts_code", how="left")
            else:
                df_with_industry = df_price_flat.merge(industry_map, on="ts_code", how="left")
        else:
            logger.warning("⚠️ 价格数据中缺少 ts_code 列，跳过行业过滤")
            return stock_codes
        
        # 检查 industry 列是否存在
        if "industry_name" not in df_with_industry.columns:
            logger.warning("⚠️ 合并后缺少 industry_name 列，跳过行业过滤")
            return stock_codes
        
        # 使用 LLM 匹配行业
        llm = build_llm_from_api_config(self.settings.llm.to_dict())
        matcher = IndustryMatcher(llm)
        
        available_industries = df_with_industry["industry_name"]
        if hasattr(available_industries, 'drop_nulls'):
            available_industries = available_industries.drop_nulls().unique().to_list()
        else:
            available_industries = available_industries.dropna().unique().tolist()
        matched_industries = matcher.match_industries(self.settings.stock_pool.industry, available_industries)
        
        if matched_industries:
            # Polars: filter() + is_in() 代替布尔索引
            if hasattr(df_with_industry, 'filter') and not hasattr(df_with_industry, 'loc'):
                df_with_industry = df_with_industry.filter(pl.col("industry_name").is_in(matched_industries))
            else:
                df_with_industry = df_with_industry[df_with_industry["industry_name"].isin(matched_industries)]
            ts_code_col = df_with_industry["ts_code"]
            if hasattr(ts_code_col, 'drop_nulls'):
                stock_codes = ts_code_col.drop_nulls().unique().to_list()
            else:
                stock_codes = ts_code_col.dropna().unique().tolist()
            logger.info(f"✅ 行业过滤：{len(matched_industries)} 个行业，{len(stock_codes)} 只股票")
        
        return stock_codes
