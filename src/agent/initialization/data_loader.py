"""数据加载器 - 负责加载和预处理市场数据."""

from __future__ import annotations
import pandas as pd
import polars as pl
from pathlib import Path
from typing import Any

from infrastructure.logging.logger import get_logger
from src.screening.stock_pool_filter import StockPoolFilter
from src.screening.industry_matcher import IndustryMatcher
from datahub.calendar_utils import get_data_start_date

from datahub import Calendar, Index
from datahub import Index
from datahub import Stock
from datahub import Stock, Calendar
from datahub.loaders import load_raw_market_data
from infrastructure.config.settings import get_settings
from mcp_server.executors.index_selector import get_index_code
from src.screening.stock_pool_filter import StockPoolFilter
from utils.agent.llm_helper import build_llm_from_api_config
import subprocess
import sys
import traceback
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
    
    def load_raw_market_data(self) -> tuple[pl.DataFrame, list[str], pl.DataFrame | None]:
        """加载原始市场数据（不过滤）.
        
        Returns:
            (原始DataFrame, 全量股票代码列表, 指数数据DataFrame)
        """
        
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
        
        # 使用 datahub 的统一函数加载原始数据
        df = load_raw_market_data(
            start_date=start_date,
            end_date=latest_trade_date,
            exclude_st=False,
            min_list_days=0,
        )
        
        # 获取全量股票代码（polars API）
        stock_codes = df.select(pl.col("ts_code").unique()).to_series().to_list()
        logger.info(f"📊 全量股票池：{len(stock_codes)} 只股票")
        
        # 加载指数数据
        index_df = self._load_index_data(stock_codes, start_date, latest_trade_date)
        
        return df, stock_codes, index_df
    
    def load_market_data(self) -> tuple[pd.DataFrame, list[str]]:
        """加载市场数据并执行股票池过滤.
        
        Returns:
            (处理后的DataFrame, 股票代码列表)
        """
        
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
        
        # 加载价格数据用于过滤
        logger.info(f"💰 开始加载价格数据用于过滤...")
        df_price = self._load_price_data(start_date, latest_trade_date, stock_codes)
        
        # 应用价格、成交量、成交额、换手率过滤
        logger.info(f"💰 应用价格和流动性过滤...")
        df_price = self._apply_price_filters(df_price, stock_codes)
        
        # 更新 stock_codes
        if not df_price.empty and "ts_code" in df_price.columns:
            stock_codes = df_price["ts_code"].dropna().unique().tolist()
            logger.info(f"📊 价格/流动性过滤后：{len(stock_codes)} 只股票")
        
        # 应用市值过滤
        logger.info(f"💰 应用市值过滤...")
        pool_filter = StockPoolFilter(self.settings.stock_pool)
        stock_codes = pool_filter._filter_market_value(df_price, stock_codes)
        logger.info(f"📊 市值过滤后：{len(stock_codes)} 只股票")
        
        # 应用数据完整性过滤
        logger.info(f"🔍 应用数据完整性过滤...")
        stock_codes = pool_filter.filter_by_completeness(df_price, stock_codes)
        logger.info(f"📊 完整性过滤后最终股票池：{len(stock_codes)} 只股票")
        
        # 重新加载最终股票池的完整价格数据
        logger.info(f"💰 加载最终股票池的完整数据...")
        df = self._load_price_data(start_date, latest_trade_date, stock_codes)
        
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
        
        # 执行基础过滤（ST、停牌、上市天数、行业）
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
    
    def _load_basic_info(self) -> pd.DataFrame:
        """加载股票基本信息.
        
        Returns:
            股票基本信息 DataFrame
        """
        
        cache_root = self.settings.data.cache_root
        if not cache_root.is_absolute():
            project_root = Path(__file__).resolve().parent.parent.parent
            cache_root = project_root / cache_root
        
        stock = Stock(root=str(cache_root))
        basic_df = stock.universe()
        if basic_df is None or basic_df.is_empty():
            raise ValueError("无法获取股票基本信息")
        
        return basic_df
    
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
        
        cache_root = self.settings.data.cache_root
        if not cache_root.is_absolute():
            project_root = Path(__file__).resolve().parent.parent.parent
            cache_root = project_root / cache_root
        
        stock = Stock(root=str(cache_root))
        df = stock.price(start_date=start_date, end_date=end_date)
        
        if df is None or df.is_empty():
            raise ValueError(f"无法获取市场数据 ({start_date}~{end_date})")
        
        logger.info(f"📊 原始数据：{len(df)} 条记录，日期范围：{df['trade_date'].min()} ~ {df['trade_date'].max()}")
        
        # 过滤到股票池
        df = df.filter(pl.col("ts_code").is_in(stock_codes))
        
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
    
    def _load_index_data(
        self,
        stock_codes: list[str],
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame | None:
        """加载指数数据。
        
        Args:
            stock_codes: 股票代码列表
            start_date: 起始日期
            end_date: 结束日期
            
        Returns:
            指数数据 DataFrame (MultiIndex: trade_date, index_code; columns: close, ...)
        """
        try:
            
            if not stock_codes:
                logger.warning("⚠️ 无法确定股票列表，跳过指数数据加载")
                return None
            
            # 收集所有唯一的指数代码（采样前100只股票）
            unique_indices: set[str] = set()
            for code in stock_codes[:100]:  # 采样避免遍历全部5500只
                idx_code = get_index_code(code)
                unique_indices.add(idx_code)
            
            indices_list = sorted(list(unique_indices))
            logger.info(f"📊 检测到 {len(indices_list)} 个指数: {', '.join(indices_list)}")
            
            # 使用 batch_level() 一次性批量加载所有指数数据
            index_domain = Index()
            
            try:
                logger.info(f"🔍 开始批量加载 {len(indices_list)} 个指数...")
                combined_index_data = index_domain.batch_level(
                    index_codes=indices_list,
                    start_date=start_date,
                    end_date=end_date,
                )
                
                if combined_index_data.is_empty():
                    logger.warning("⚠️ 批量加载返回空数据，尝试逐个加载...")
                    return self._load_indices_fallback(index_domain, indices_list, start_date, end_date)
                
                logger.info(f"✅ 批量加载成功，共 {len(combined_index_data)} 条记录")
                
                # 检查实际加载了多少个不同的指数
                col_name = 'index_code' if 'index_code' in combined_index_data.columns else 'ts_code'
                actual_indices = combined_index_data[col_name].unique().to_list()
                logger.info(f"✅ 实际加载了 {len(actual_indices)} 个指数: {', '.join(actual_indices)}")
                
                if len(actual_indices) < len(indices_list):
                    missing = set(indices_list) - set(actual_indices)
                    logger.warning(f"⚠️ 以下指数数据缺失: {', '.join(sorted(missing))}")
                    logger.info(f"🔄 尝试同步缺失的指数数据...")
                    
                    # 自动同步缺失的指数
                    self._sync_missing_indices(sorted(missing))
                    
                    # 重新批量加载所有指数
                    logger.info(f"🔄 重新批量加载所有指数...")
                    combined_index_data = index_domain.batch_level(
                        index_codes=indices_list,
                        start_date=start_date,
                        end_date=end_date,
                    )
                    
                    if not combined_index_data.is_empty():
                        actual_indices = combined_index_data[col_name].unique().to_list()
                        logger.info(f"✅ 重新加载后，实际加载了 {len(actual_indices)} 个指数: {', '.join(actual_indices)}")
                    else:
                        logger.error("❌ 重新加载后仍为空")
                        return None
                
                # 转换日期格式
                if 'trade_date' in combined_index_data.columns:
                    try:
                        combined_index_data = combined_index_data.with_columns(
                            pl.col('trade_date').cast(pl.Datetime)
                        )
                    except Exception:
                        pass
                
                # 重命名 ts_code 为 index_code（如果需要）
                if 'ts_code' in combined_index_data.columns:
                    combined_index_data = combined_index_data.rename({'ts_code': 'index_code'})
                
                logger.info(f"✅ 成功加载 {len(indices_list)} 个指数数据，共 {len(combined_index_data)} 条记录")
                return combined_index_data
                
            except Exception as e:
                logger.error(f"❌ 批量加载失败: {e}")
                logger.info(f"🔄 降级为逐个加载...")
                return self._load_indices_fallback(index_domain, indices_list, start_date, end_date)
            
        except Exception as e:
            logger.warning(f"⚠️ 加载指数数据失败: {e}")
            logger.debug(traceback.format_exc())
            return None
    
    def _load_indices_fallback(
        self,
        index_domain,
        indices_list: list[str],
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame | None:
        """降级方案：逐个加载指数数据。
        
        Args:
            index_domain: Index 实例
            indices_list: 指数代码列表
            start_date: 起始日期
            end_date: 结束日期
            
        Returns:
            合并后的指数数据 DataFrame
        """
        logger.info(f"🔄 使用降级方案：逐个加载 {len(indices_list)} 个指数...")
        dfs = []
        failed_indices = []
        
        for idx_code in indices_list:
            try:
                df = index_domain.level(
                    index_code=idx_code,
                    start_date=start_date,
                    end_date=end_date,
                )
                if not df.is_empty():
                    logger.info(f"   ✅ {idx_code}: {len(df)} 条记录")
                    dfs.append(df)
                else:
                    logger.warning(f"   ⚠️ {idx_code}: 空数据")
                    failed_indices.append(idx_code)
            except Exception as e:
                logger.error(f"   ❌ {idx_code}: {e}")
                failed_indices.append(idx_code)
        
        if not dfs:
            logger.warning("⚠️ 所有指数数据加载失败")
            return None
        
        combined_index_data = pl.concat(dfs)
        logger.info(f"✅ 降级方案成功，共 {len(combined_index_data)} 条记录")
        
        # 如果有失败的指数，尝试同步
        if failed_indices:
            logger.info(f"🔄 尝试同步缺失的指数: {', '.join(failed_indices)}")
            self._sync_missing_indices(failed_indices)
            
            # 重新加载失败的指数
            for idx_code in failed_indices:
                try:
                    df = index_domain.level(
                        index_code=idx_code,
                        start_date=start_date,
                        end_date=end_date,
                    )
                    if not df.is_empty():
                        logger.info(f"   ✅ {idx_code}: 重新加载成功")
                        dfs.append(df)
                except Exception as e:
                    logger.error(f"   ❌ {idx_code}: 重新加载失败 - {e}")
            
            if len(dfs) > len(combined_index_data):
                combined_index_data = pl.concat(dfs)
                logger.info(f"✅ 重新加载后共 {len(combined_index_data)} 条记录")
        
        # 转换日期格式
        if 'trade_date' in combined_index_data.columns:
            try:
                combined_index_data = combined_index_data.with_columns(
                    pl.col('trade_date').cast(pl.Datetime)
                )
            except Exception:
                pass
        
        # 重命名 ts_code 为 index_code
        if 'ts_code' in combined_index_data.columns:
            combined_index_data = combined_index_data.rename({'ts_code': 'index_code'})
        
        return combined_index_data
    
    def _sync_missing_indices(self, missing_indices: list[str]):
        """同步缺失的指数数据。
        
        Args:
            missing_indices: 缺失的指数代码列表
        """
        if not missing_indices:
            return
        
        try:
            
            codes_str = ','.join(missing_indices)
            sync_cmd = [
                sys.executable, '-m', 'datahub', 'sync',
                '--dataset', 'index_daily',
                '--codes', codes_str
            ]
            
            logger.info(f"   执行命令: {' '.join(sync_cmd)}")
            result = subprocess.run(
                sync_cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                logger.info(f"   ✅ 指数数据同步成功")
            else:
                logger.error(f"   ❌ 指数数据同步失败")
                if result.stderr:
                    logger.error(f"   错误信息: {result.stderr[:500]}")
        except subprocess.TimeoutExpired:
            logger.error(f"   ❌ 指数数据同步超时（超过5分钟）")
        except Exception as e:
            logger.error(f"   ❌ 自动同步失败: {e}")
    
    def _load_and_merge_index_data(
        self,
        df: pd.DataFrame,
        stock_codes: list[str],
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """加载指数数据并合并到股票数据中。
        
        根据股票代码自动选择对应的基准指数，并将指数价格数据合并到股票数据中。
        
        Args:
            df: 股票数据 DataFrame (columns: ts_code, trade_date, close, ...)
            stock_codes: 股票代码列表
            start_date: 起始日期
            end_date: 结束日期
            
        Returns:
            添加了 index_close 列的 DataFrame
        """
        try:
            
            # 确定需要加载指数的股票（采样前10只）
            codes_to_process = stock_codes[:10] if stock_codes else []
            
            if not codes_to_process:
                logger.warning("⚠️ 无法确定股票列表，跳过指数数据加载")
                return df
            
            # 统计各指数的出现次数，选择最常用的指数
            index_counts = {}
            for code in codes_to_process:
                idx_code = get_index_code(code)
                index_counts[idx_code] = index_counts.get(idx_code, 0) + 1
            
            # 选择出现次数最多的指数
            primary_index = max(index_counts, key=index_counts.get)
            logger.info(f"📊 主要使用指数: {primary_index} ({index_counts[primary_index]}/{len(codes_to_process)} 只股票)")
            
            # 加载指数数据
            index_domain = Index()
            index_df = index_domain.level(
                index_code=primary_index,
                start_date=start_date,
                end_date=end_date,
            )
            
            if index_df.empty or 'close' not in index_df.columns:
                logger.warning(f"⚠️ 指数 {primary_index} 数据为空或缺少 close 列")
                return df
            
            # 重命名列并准备合并
            index_df = index_df.rename(columns={'close': 'index_close'})
            
            # 将指数数据合并到股票数据中
            result_df = df.copy()
            
            # 如果 df 是 MultiIndex (trade_date, ts_code)
            if isinstance(df.index, pd.MultiIndex):
                # 从 MultiIndex 中提取 trade_date
                trade_dates = df.index.get_level_values('trade_date')
                
                # 创建映射：trade_date -> index_close
                if 'trade_date' in index_df.columns:
                    index_df['trade_date'] = pd.to_datetime(index_df['trade_date'])
                    index_map = index_df.set_index('trade_date')['index_close']
                    
                    # 映射到每行
                    result_df['index_close'] = trade_dates.map(index_map)
                else:
                    logger.warning("⚠️ 指数数据缺少 trade_date 列")
                    return df
            else:
                # 如果 df 是普通 DataFrame
                if 'trade_date' in df.columns and 'trade_date' in index_df.columns:
                    df_dates = pd.to_datetime(df['trade_date'])
                    index_df['trade_date'] = pd.to_datetime(index_df['trade_date'])
                    index_map = index_df.set_index('trade_date')['index_close']
                    result_df['index_close'] = df_dates.map(index_map)
                else:
                    logger.warning("⚠️ 数据格式不匹配，无法合并指数数据")
                    return df
            
            logger.info(f"✅ 成功加载指数数据: {primary_index}, {len(index_df)} 个交易日")
            return result_df
            
        except Exception as e:
            logger.warning(f"⚠️ 加载指数数据失败: {e}")
            logger.debug(traceback.format_exc())
            return df
