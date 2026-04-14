"""股票池服务 - 独立的股票池过滤模块.

职责：
1. 执行基础数据过滤（ST、停牌、上市天数）
2. 调用 IndustryMatcher 进行 LLM 行业匹配
3. 应用价格、市值、完整性等业务过滤规则
"""

from __future__ import annotations

import pandas as pd
from typing import Any
from datetime import datetime

from infrastructure.logging.logger import get_logger
from src.screening.stock_pool_filter import StockPoolFilter
from src.screening.industry_matcher import IndustryMatcher
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
        raw_data: pd.DataFrame, 
        raw_codes: list[str]
    ) -> tuple[pd.DataFrame, list[str]]:
        """应用股票池过滤.
        
        Args:
            raw_data: 原始市场数据 DataFrame（已加载，MultiIndex 格式）
            raw_codes: 原始股票代码列表
            
        Returns:
            (过滤后的DataFrame, 过滤后的股票代码列表)
        """
        # 获取最新交易日期
        from datahub import Calendar
        
        calendar = Calendar()
        today = pd.Timestamp.now().strftime("%Y%m%d")
        latest_trade_date = calendar.get_latest_trade_date(today)
        
        if not latest_trade_date:
            latest_trade_date = today
        
        # 从 raw_data 中提取价格数据（已经是 MultiIndex 格式）
        df_price = self._extract_basic_info(raw_data)
        logger.info(f"📊 使用已加载的价格数据：{len(df_price)} 条记录")
        
        # 加载股票基本信息（用于 ST、上市天数等过滤）
        logger.info(f"📊 加载股票基本信息...")
        from src.agent.initialization.data_loader import DataLoader
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
        if not df_filtered.empty and "ts_code" in df_filtered.columns:
            stock_codes = df_filtered["ts_code"].dropna().unique().tolist()
            logger.info(f"📊 价格/流动性过滤后：{len(stock_codes)} 只股票")
        
        # 4. 市值过滤
        stock_codes = pool_filter._filter_market_value(df_filtered, stock_codes)
        logger.info(f"📊 市值过滤后：{len(stock_codes)} 只股票")
        
        # 5. 数据完整性过滤
        stock_codes = pool_filter.filter_by_completeness(df_filtered, stock_codes)
        logger.info(f"📊 完整性过滤后：{len(stock_codes)} 只股票")
        
        # 过滤到最终股票池
        filtered_data = df_filtered[df_filtered["ts_code"].isin(stock_codes)].copy()
        
        # 设置 MultiIndex
        if "trade_date" in filtered_data.columns:
            filtered_data["trade_date"] = pd.to_datetime(filtered_data["trade_date"])
            filtered_data = filtered_data.sort_values(["trade_date", "ts_code"])
            filtered_data = filtered_data.set_index(["trade_date", "ts_code"])
        
        return filtered_data, stock_codes
    
    def _filter_stock_pool_basic(
        self,
        data: pd.DataFrame,
        basic_df: pd.DataFrame,
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
        if basic_df is None or basic_df.empty:
            return []
        
        stock_codes = basic_df["ts_code"].dropna().unique().tolist()
        
        # 排除 ST 股票
        if self.settings.stock_pool.exclude_st:
            st_mask = basic_df["name"].str.contains(r"ST|\*ST", na=False)
            stock_codes = basic_df[~st_mask]["ts_code"].dropna().unique().tolist()
        
        # 排除停牌股票（vol=0）
        if not data.empty and "vol" in data.columns:
            latest_date_data = data[data.index.get_level_values('trade_date') == pd.to_datetime(latest_trade_date)]
            if not latest_date_data.empty:
                # MultiIndex 需要 reset_index 后才能访问 ts_code
                latest_date_flat = latest_date_data.reset_index()
                active_stocks = latest_date_flat[latest_date_flat["vol"] > 0]["ts_code"].unique()
                stock_codes = [code for code in stock_codes if code in active_stocks]
        
        # 排除上市天数不足的股票
        min_list_days = self.settings.stock_pool.min_list_days
        if min_list_days > 0 and "list_date" in basic_df.columns:
            cutoff_date = datetime.strptime(latest_trade_date, "%Y%m%d")
            valid_codes = []
            for code in stock_codes:
                row = basic_df[basic_df["ts_code"] == code]
                if not row.empty:
                    list_date_str = row.iloc[0]["list_date"]
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
    
    def _extract_basic_info(self, data: pd.DataFrame) -> pd.DataFrame:
        """从数据中提取基本信息.
        
        Args:
            data: 市场数据 DataFrame（可能是 MultiIndex）
            
        Returns:
            基本信息 DataFrame
        """
        if hasattr(data, 'index') and isinstance(data.index, pd.MultiIndex):
            return data.reset_index()
        return data
    
    def _apply_industry_filter(
        self, 
        df_price: pd.DataFrame, 
        raw_data: pd.DataFrame, 
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
        industry_map = basic_df[["ts_code", "industry"]].drop_duplicates("ts_code", keep="first")
        industry_map = industry_map.rename(columns={"industry": "industry_name"})
        
        # 将价格数据转换为普通 DataFrame（处理 MultiIndex）
        df_price_flat = self._extract_basic_info(df_price)
        
        # 将行业信息合并到价格数据
        if "ts_code" in df_price_flat.columns:
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
        
        available_industries = df_with_industry["industry_name"].dropna().unique().tolist()
        matched_industries = matcher.match_industries(self.settings.stock_pool.industry, available_industries)
        
        if matched_industries:
            df_with_industry = df_with_industry[df_with_industry["industry_name"].isin(matched_industries)]
            stock_codes = df_with_industry["ts_code"].dropna().unique().tolist()
            logger.info(f"✅ 行业过滤：{len(matched_industries)} 个行业，{len(stock_codes)} 只股票")
        
        return stock_codes
