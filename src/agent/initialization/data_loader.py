"""数据加载器 - 负责加载和预处理市场数据."""

from __future__ import annotations

import pandas as pd
from pathlib import Path
from typing import Any

from infrastructure.logging.logger import get_logger
from src.screening.stock_pool_filter import StockPoolFilter
from src.screening.industry_matcher import IndustryMatcher
from utils.screening.screening_tools import get_data_start_date

logger = get_logger(__name__)


class DataLoader:
    """数据加载器 - 封装所有数据加载和预处理逻辑."""
    
    def __init__(self, settings: Any):
        """初始化数据加载器.
        
        Args:
            settings: 全局配置对象
        """
        self.settings = settings
        self.industry_matcher: IndustryMatcher | None = None
    
    def load_market_data(self) -> tuple[pd.DataFrame, list[str]]:
        """加载市场数据并执行股票池过滤.
        
        Returns:
            (处理后的DataFrame, 股票代码列表)
        """
        from datahub import Stock, Calendar
        
        # 获取最新交易日期
        calendar = Calendar()
        today = pd.Timestamp.now().strftime("%Y%m%d")
        latest_trade_date = calendar.get_latest_trade_date(today)
        
        if not latest_trade_date:
            latest_trade_date = today
            logger.warning(f"⚠️ 无法获取最新交易日，使用今天：{today}")
        else:
            logger.info(f"📅 最新交易日期：{latest_trade_date}")
        
        # 计算数据起始日期（使用全局 observation_days 配置）
        observation_days = self.settings.observation_days
        logger.info(f"📊 配置观察期：{observation_days}个交易日")
        start_date = get_data_start_date(latest_trade_date, observation_days=observation_days)
        logger.info(f"📅 计算的数据范围：{start_date} ~ {latest_trade_date}（观察期：{observation_days}个交易日）")
        
        # 加载股票基本信息
        cache_root = self.settings.data.cache_root
        if not cache_root.is_absolute():
            project_root = Path(__file__).resolve().parent.parent.parent
            cache_root = project_root / cache_root
        
        stock = Stock(root=str(cache_root))
        basic_df = stock.universe()
        if basic_df is None or basic_df.empty:
            raise ValueError("无法获取股票基本信息")
        
        # 执行股票池过滤
        stock_codes, df_pool = self._filter_stock_pool(basic_df, latest_trade_date)
        
        # 加载价格数据
        df = self._load_price_data(start_date, latest_trade_date, stock_codes)
        
        # 应用价格和成交量过滤
        df = self._apply_price_filters(df, stock_codes)
        
        # 更新股票代码列表
        if "ts_code" in df.columns:
            stock_codes = df["ts_code"].dropna().unique().tolist()
            logger.info(f"📊 价格数据过滤后股票池：{len(stock_codes)} 只股票")
        
        # 应用完整性过滤
        pool_filter = StockPoolFilter(self.settings.stock_pool)
        stock_codes = pool_filter.filter_by_completeness(df, stock_codes)
        logger.info(f"📊 完整性过滤后最终股票池：{len(stock_codes)} 只股票")
        
        # 过滤到最终的 stock_codes
        df = df[df["ts_code"].isin(stock_codes)].copy()
        
        # 补充行业信息
        df = self._add_industry_info(df, basic_df)
        
        # 设置 MultiIndex
        df = self._setup_multiindex(df)
        
        return df, stock_codes
    
    def _filter_stock_pool(
        self, 
        basic_df: pd.DataFrame, 
        latest_trade_date: str
    ) -> tuple[list[str], pd.DataFrame]:
        """执行股票池基础过滤.
        
        Args:
            basic_df: 股票基本信息 DataFrame
            latest_trade_date: 最新交易日期
            
        Returns:
            (股票代码列表, 过滤后的DataFrame)
        """
        pool_filter = StockPoolFilter(self.settings.stock_pool)
        
        logger.info(f"🔧 股票池配置：min_price={self.settings.stock_pool.min_price}, "
                   f"min_amount={self.settings.stock_pool.min_amount}, "
                   f"min_turnover={self.settings.stock_pool.min_turnover}")
        
        # 执行基础过滤（ST、停牌、上市天数）
        stock_codes, df_pool = pool_filter.filter_stock_pool(
            basic_df=basic_df,
            price_df=None,
            latest_trade_date=latest_trade_date,
        )
        logger.info(f"📊 ST/停牌/上市天数过滤后：{len(stock_codes)} 只股票")
        
        # 行业过滤（支持 LLM 智能匹配）
        if self.settings.stock_pool.industry:
            logger.info(f"🎯 开始行业过滤，配置的行业：{self.settings.stock_pool.industry}")
            df_pool = self._filter_by_industry(df_pool, self.settings.stock_pool.industry)
            stock_codes = df_pool["ts_code"].dropna().unique().tolist() if "ts_code" in df_pool.columns else []
        else:
            logger.info("ℹ️ 未配置行业过滤，使用全市场股票池")
        
        return stock_codes, df_pool
    
    def _filter_by_industry(self, df_pool: pd.DataFrame, target_industries: list[str]) -> pd.DataFrame:
        """根据行业列表过滤股票池（使用 LLM 智能匹配）.
        
        Args:
            df_pool: 股票池 DataFrame
            target_industries: 目标行业列表（用户输入，可能不完整）
            
        Returns:
            过滤后的股票池
        """
        logger.info(f"🔍 检查 industry 列：{'industry' in df_pool.columns}")
        if "industry" not in df_pool.columns:
            logger.warning("⚠️ 数据中缺少 industry 列，跳过行业过滤")
            logger.info(f"📋 可用列：{df_pool.columns.tolist()[:10]}")
            return df_pool
        
        # 初始化行业匹配器（如果尚未初始化）
        if self.industry_matcher is None:
            from utils.agent.llm_helper import build_llm_from_api_config
            from infrastructure.config.settings import get_settings
            llm = build_llm_from_api_config(get_settings().llm.to_dict())
            self.industry_matcher = IndustryMatcher(llm)
        
        # 获取所有可用行业
        available_industries = df_pool["industry"].dropna().unique().tolist()
        logger.info(f"📋 可用行业共 {len(available_industries)} 个")
        logger.info(f"📋 前20个行业：{available_industries[:20]}")
        
        # 使用 LLM 进行智能行业匹配
        matched_industries = self.industry_matcher.match_industries(target_industries, available_industries)
        
        if not matched_industries:
            logger.warning(f"⚠️ 没有匹配到任何行业，使用全部股票池")
            return df_pool
        
        # 过滤股票池
        filtered_df = df_pool[df_pool["industry"].isin(matched_industries)]
        logger.info(f"✅ 行业过滤：{len(matched_industries)} 个行业，{len(filtered_df)} 只股票")
        logger.info(f"   匹配行业：{', '.join(matched_industries[:10])}{'...' if len(matched_industries) > 10 else ''}")
        
        return filtered_df
    
    def _load_price_data(
        self, 
        start_date: str, 
        end_date: str, 
        stock_codes: list[str]
    ) -> pd.DataFrame:
        """加载价格数据.
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            stock_codes: 股票代码列表
            
        Returns:
            价格数据 DataFrame
        """
        from datahub import Stock
        
        cache_root = self.settings.data.cache_root
        if not cache_root.is_absolute():
            project_root = Path(__file__).resolve().parent.parent.parent
            cache_root = project_root / cache_root
        
        stock = Stock(root=str(cache_root))
        df = stock.price(start_date=start_date, end_date=end_date)
        
        if df is None or df.empty:
            raise ValueError(f"无法获取市场数据 ({start_date}~{end_date})")
        
        logger.info(f"📊 原始数据：{len(df)} 条记录，日期范围：{df['trade_date'].min()} ~ {df['trade_date'].max()}")
        
        # 过滤到股票池
        df = df[df["ts_code"].isin(stock_codes)].copy()
        logger.info(f"📊 过滤到股票池后：{len(df)} 条记录")
        
        return df
    
    def _apply_price_filters(self, df: pd.DataFrame, stock_codes: list[str]) -> pd.DataFrame:
        """应用价格和成交量过滤.
        
        Args:
            df: 价格数据 DataFrame
            stock_codes: 股票代码列表
            
        Returns:
            过滤后的 DataFrame
        """
        from src.screening.stock_pool_filter import StockPoolFilter
        
        pool_filter = StockPoolFilter(self.settings.stock_pool)
        df = pool_filter._filter_price_data(df, stock_codes)
        
        return df
    
    def _add_industry_info(self, df: pd.DataFrame, basic_df: pd.DataFrame) -> pd.DataFrame:
        """补充行业信息.
        
        Args:
            df: 价格数据 DataFrame
            basic_df: 股票基本信息 DataFrame
            
        Returns:
            补充了行业信息的 DataFrame
        """
        if "industry" not in df.columns and "industry" in basic_df.columns:
            # 从 basic_df 中提取每只股票的最新行业（drop_duplicates 保留第一条，即最新）
            industry_map = basic_df[["ts_code", "industry"]].drop_duplicates("ts_code", keep="first")
            industry_map = industry_map.set_index("ts_code")["industry"]
            if "ts_code" in df.columns:
                df = df.merge(industry_map, on="ts_code", how="left")
                logger.info(f"📊 已补充行业信息，共 {df['industry'].notna().sum()} 只股票有行业标签")
        
        return df
    
    def _setup_multiindex(self, df: pd.DataFrame) -> pd.DataFrame:
        """设置 MultiIndex.
        
        Args:
            df: 数据 DataFrame
            
        Returns:
            设置了 MultiIndex 的 DataFrame
        """
        if "trade_date" in df.columns:
            df = df.copy()
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            df = df.sort_values(["trade_date", "ts_code"])
            df = df.set_index(["trade_date", "ts_code"])
            logger.info(f"✅ 已加载市场数据：{len(df)} 条记录")
        
        return df
