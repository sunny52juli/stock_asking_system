"""行业匹配服务 - 使用 LLM 智能匹配行业名称."""

from __future__ import annotations

import pandas as pd
import polars as pl
from typing import Any

from infrastructure.logging.logger import get_logger
from src.screening.industry_matcher import IndustryMatcher
from utils.agent.llm_helper import build_llm_from_api_config

logger = get_logger(__name__)


class IndustryMatcherService:
    """行业匹配服务 - 封装 LLM 行业匹配逻辑."""
    
    def __init__(self, settings: Any):
        """初始化.
        
        Args:
            settings: 全局配置对象
        """
        self.settings = settings
        self._matcher: IndustryMatcher | None = None
    
    def filter_by_industry(
        self, 
        df_pool: pd.DataFrame, 
        target_industries: list[str]
    ) -> pd.DataFrame:
        """根据行业列表过滤股票池（使用 LLM 智能匹配）.
        
        Args:
            df_pool: 股票池 DataFrame
            target_industries: 目标行业列表（用户输入，可能不完整）
            
        Returns:
            过滤后的 DataFrame
        """
        if not target_industries:
            logger.info("[INFO] 未指定行业，跳过行业过滤")
            return df_pool
        
        # 初始化行业匹配器
        if self._matcher is None:
            self._matcher = self._create_industry_matcher()
        
        # 执行行业匹配
        matched_industries = self._matcher.match_industries(target_industries, df_pool["industry"].drop_nulls().unique().to_list() if hasattr(df_pool, 'drop_nulls') else df_pool["industry"].dropna().unique().tolist())
        
        # 过滤 DataFrame
        if matched_industries:
            if hasattr(df_pool, 'filter') and not hasattr(df_pool, 'loc'):
                # Polars
                matched_df = df_pool.filter(pl.col("industry").is_in(matched_industries))
            else:
                # Pandas
                matched_df = df_pool[df_pool["industry"].isin(matched_industries)]
        else:
            logger.warning(f"[WARN] 未匹配到任何行业，返回空 DataFrame")
            matched_df = df_pool.head(0) if hasattr(df_pool, 'head') else df_pool[:0]
        
        # Polars: is_empty() 代替 .empty
        df_is_empty = (hasattr(matched_df, 'is_empty') and matched_df.is_empty()) or (hasattr(matched_df, 'empty') and matched_df.empty)
        if df_is_empty:
            logger.warning(f"[WARN] 行业过滤后无股票：{target_industries}")
        else:
            logger.info(f"[OK] 行业过滤后：{len(matched_df)} 只股票")
        
        return matched_df
    
    def _create_industry_matcher(self) -> IndustryMatcher:
        """创建行业匹配器.
        
        Returns:
            IndustryMatcher 实例
        """
        try:
            llm = build_llm_from_api_config(self.settings.llm)
            matcher = IndustryMatcher(llm=llm)
            logger.info("[OK] 行业匹配器初始化成功")
            return matcher
        except Exception as e:
            logger.error(f"[ERROR] 创建行业匹配器失败：{e}", exc_info=True)
            raise
