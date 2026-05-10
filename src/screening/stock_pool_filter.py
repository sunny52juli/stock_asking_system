"""股票池筛选器 - 根据配置过滤股票池."""

from __future__ import annotations
import polars as pl

from infrastructure.logging.logger import get_logger


from infrastructure.config.settings import StockPoolConfig
logger = get_logger(__name__)


class StockPoolFilter:
    """股票池筛选器.
    
    负责根据配置对股票池进行预筛选，包括：
    - ST 股票过滤
    - 停牌股票过滤
    - 上市天数过滤
    - 行业过滤（支持模糊匹配）
    - 价格、成交量、成交额、换手率过滤
    - 数据完整性过滤
    """
    
    def __init__(self, config: StockPoolConfig):
        """初始化股票池筛选器.
        
        Args:
            config: 股票池配置
        """
        self.config = config
    
    def filter_stock_pool(
        self,
        basic_df: pl.DataFrame,
        price_df: pl.DataFrame | None = None,
        latest_trade_date: str | None = None,
    ) -> tuple[list[str], pl.DataFrame]:
        """执行股票池筛选.
        
        Args:
            basic_df: 股票基本信息 DataFrame（包含 ts_code, name, list_date, industry 等）
            price_df: 价格数据 DataFrame（可选，用于价格/成交量过滤）
            latest_trade_date: 最新交易日期（YYYYMMDD 格式）
            
        Returns:
            (stock_codes, filtered_basic_df): 筛选后的股票代码列表和基本信息
        """
        df_pool = basic_df.clone()
        initial_count = len(df_pool)
        logger.info(f"[DATA] 初始股票池：{initial_count} 只股票")
        
        # 1. ST 股票过滤
        df_pool = self._filter_st(df_pool)
        
        # 2. 停牌股票过滤
        df_pool = self._filter_suspended(df_pool)
        
        # 3. 上市天数过滤
        if latest_trade_date:
            df_pool = self._filter_list_days(df_pool, latest_trade_date)
        
        # 4. 行业过滤
        df_pool = self._filter_industry(df_pool)
        

        # 获取股票代码列表
        if "ts_code" in df_pool.columns:
            ts_code_col = df_pool["ts_code"]
            stock_codes = ts_code_col.drop_nulls().unique().to_list()
        else:
            stock_codes = []
        
        # 5. 价格/成交量/成交额/换手率过滤（需要价格数据）
        if price_df is not None:
            if not price_df.is_empty():
                price_df = self._filter_price_data(price_df, stock_codes)
                # 更新 stock_codes 为过滤后的结果
                if "ts_code" in price_df.columns:
                    ts_code_col = price_df["ts_code"]
                    stock_codes = ts_code_col.drop_nulls().unique().to_list()
        
        # 6. 市值过滤（需要估值数据）
        if price_df is not None and not price_df.is_empty():
            stock_codes = self._filter_market_value(price_df, stock_codes)
        
        # 7. 数据完整性过滤
        if price_df is not None and not price_df.is_empty():
            stock_codes = self.filter_by_completeness(price_df, stock_codes)
        
        return stock_codes, df_pool
    
    def _filter_st(self, df: pl.DataFrame) -> pl.DataFrame:
        """过滤 ST 股票."""
        if not self.config.exclude_st or "name" not in df.columns:
            return df
        
        before_count = len(df)
        # 修复：使用 ^ 锚定开头，避免误匹配名称中包含 "ST" 的正常股票
        # 匹配规则：以 "ST" 或 "*ST" 开头的股票名称（不区分大小写）
        df = df.filter(~pl.col("name").cast(pl.String).str.to_uppercase().str.contains(r"^\*?ST"))
        removed = before_count - len(df)
        if removed > 0:
            logger.info(f"   [OK] ST过滤：-{removed} 只，剩余 {len(df)} 只")
        return df
    
    def _filter_suspended(self, df: pl.DataFrame) -> pl.DataFrame:
        """过滤停牌股票."""
        if "list_status" not in df.columns:
            return df
        
        before_count = len(df)
        df = df.filter(pl.col("list_status") == "L")
        removed = before_count - len(df)
        if removed > 0:
            logger.info(f"   [OK] 停牌过滤：-{removed} 只，剩余 {len(df)} 只")
        return df
    
    def _filter_list_days(self, df: pl.DataFrame, latest_trade_date: str) -> pl.DataFrame:
        """过滤上市天数不足的股票."""
        if self.config.min_list_days <= 0 or "list_date" not in df.columns:
            return df
        
        before_count = len(df)
        # Polars: 使用 with_columns() 代替列赋值
        df = df.with_columns([
            pl.col("list_date").str.strptime(pl.Date, "%Y%m%d", strict=False).alias("list_date"),
        ])
        ref_date = pl.lit(latest_trade_date).str.strptime(pl.Date, "%Y%m%d")
        df = df.with_columns([
            ((ref_date - pl.col("list_date")).dt.total_days()).alias("list_days")
        ])
        df = df.filter(pl.col("list_days") >= self.config.min_list_days)
        removed = before_count - len(df)
        if removed > 0:
            logger.info(f"   [OK] 上市天数过滤(>={self.config.min_list_days}天)：-{removed} 只，剩余 {len(df)} 只")
        return df
    
    def _filter_industry(self, df: pl.DataFrame) -> pl.DataFrame:
        """行业过滤（支持模糊匹配）."""
        if not self.config.industry or "industry" not in df.columns:
            return df
        
        before_count = len(df)
        mask = pl.lit(False)
        for industry_keyword in self.config.industry:
            mask = mask | pl.col("industry").cast(pl.String).str.contains(industry_keyword)
        df = df.filter(mask)
        removed = before_count - len(df)
        if removed > 0:
            logger.info(f"   [OK] 行业过滤({self.config.industry})：-{removed} 只，剩余 {len(df)} 只")
        return df
    
    def _filter_price_data(
        self,
        price_df: pl.DataFrame,
        stock_codes: list[str],
    ) -> pl.DataFrame:
        """过滤价格数据（价格、成交量、成交额、换手率）.
        
        注意：对于时序数据，使用观察期内的极值进行判断：
        - min_price: 观察期内最高价 >= 阈值
        - max_price: 观察期内最低价 <= 阈值
        - min_vol/amount/turnover: 观察期内最大值 >= 阈值
        """
        if not stock_codes:
            return price_df
        
        df = price_df.filter(pl.col("ts_code").is_in(stock_codes))
        before_count = len(df)
        ts_code_col = df["ts_code"]
        before_stock_count = ts_code_col.n_unique()
        logger.info(f"[DATA] 开始价格数据过滤，共 {before_stock_count} 只股票，{before_count} 条记录")
        
        filtered_stocks = set(stock_codes)  # 待过滤的股票集合
        
        # 按股票分组，计算每只股票的统计量
        stock_stats = df.group_by("ts_code").agg([
            pl.col("close").max().alias("close_max"),
            pl.col("close").min().alias("close_min"),
            pl.col("vol").max().alias("vol_max") if "vol" in df.columns else pl.lit(None).alias("vol_max"),
            pl.col("amount").max().alias("amount_max") if "amount" in df.columns else pl.lit(None).alias("amount_max"),
            pl.col("turnover_rate").max().alias("turnover_rate_max") if "turnover_rate" in df.columns else pl.lit(None).alias("turnover_rate_max"),
        ])
        
        # 价格过滤：观察期内最高价 >= min_price
        if "close_max" in stock_stats.columns and self.config.min_price > 0:
            before = len(filtered_stocks)
            valid_stocks_pl = stock_stats.filter(pl.col("close_max") >= self.config.min_price).select("ts_code")
            valid_stocks = set(valid_stocks_pl.to_series().to_list())
            filtered_stocks = filtered_stocks & valid_stocks
            removed = before - len(filtered_stocks)
            if removed > 0:
                logger.info(f"   [OK] 最低价过滤(观察期最高价>={self.config.min_price}元)：-{removed} 只，剩余 {len(filtered_stocks)} 只")
        
        # 价格过滤：观察期内最低价 <= max_price
        if "close_min" in stock_stats.columns and self.config.max_price < 999999:
            before = len(filtered_stocks)
            valid_stocks_pl = stock_stats.filter(pl.col("close_min") <= self.config.max_price).select("ts_code")
            valid_stocks = set(valid_stocks_pl.to_series().to_list())
            filtered_stocks = filtered_stocks & valid_stocks
            removed = before - len(filtered_stocks)
            if removed > 0:
                logger.info(f"   [OK] 最高价过滤(观察期最低价<={self.config.max_price}元)：-{removed} 只，剩余 {len(filtered_stocks)} 只")
        
        # 成交量过滤：观察期内最大成交量 >= min_vol
        if "vol_max" in stock_stats.columns and self.config.min_vol > 0:
            before = len(filtered_stocks)
            valid_stocks_pl = stock_stats.filter(pl.col("vol_max") >= self.config.min_vol).select("ts_code")
            valid_stocks = set(valid_stocks_pl.to_series().to_list())
            filtered_stocks = filtered_stocks & valid_stocks
            removed = before - len(filtered_stocks)
            if removed > 0:
                logger.info(f"   [OK] 成交量过滤(观察期最大成交量>={self.config.min_vol})：-{removed} 只，剩余 {len(filtered_stocks)} 只")
        
        # 成交金额过滤：观察期内最大成交额 >= min_amount
        if "amount_max" in stock_stats.columns and self.config.min_amount > 0:
            before = len(filtered_stocks)
            valid_stocks_pl = stock_stats.filter(pl.col("amount_max") >= self.config.min_amount).select("ts_code")
            valid_stocks = set(valid_stocks_pl.to_series().to_list())
            filtered_stocks = filtered_stocks & valid_stocks
            removed = before - len(filtered_stocks)
            if removed > 0:
                logger.info(f"   [OK] 成交额过滤(观察期最大成交额>={self.config.min_amount})：-{removed} 只，剩余 {len(filtered_stocks)} 只")
        
        # 换手率过滤：观察期内最大换手率 >= min_turnover
        if "turnover_rate_max" in stock_stats.columns and self.config.min_turnover > 0:
            before = len(filtered_stocks)
            valid_stocks_pl = stock_stats.filter(pl.col("turnover_rate_max") >= self.config.min_turnover).select("ts_code")
            valid_stocks = set(valid_stocks_pl.to_series().to_list())
            filtered_stocks = filtered_stocks & valid_stocks
            removed = before - len(filtered_stocks)
            if removed > 0:
                logger.info(f"   [OK] 换手率过滤(观察期最大换手率>={self.config.min_turnover}%)：-{removed} 只，剩余 {len(filtered_stocks)} 只")
        
        # 过滤 DataFrame
        df = df.filter(pl.col("ts_code").is_in(filtered_stocks))
        after_count = len(df)
        after_stock_count = len(filtered_stocks)
        
        if before_stock_count != after_stock_count:
            logger.info(f"[DATA] 价格数据过滤后：{before_stock_count} -> {after_stock_count} 只股票，{before_count} -> {after_count} 条记录")
        
        return df
    
    def _filter_market_value(
        self,
        price_df: pl.DataFrame,
        stock_codes: list[str],
    ) -> list[str]:
        """按市值过滤股票.
        
        Args:
            price_df: 价格数据 DataFrame（需包含 total_mv 字段）
            stock_codes: 待检查的股票代码列表
            
        Returns:
            符合市值要求的股票代码列表
        """
        if not stock_codes:
            return stock_codes
        
        # 检查是否有市值字段
        if "total_mv" not in price_df.columns:
            logger.warning("[WARN] 价格数据中缺少 total_mv 字段，跳过市值过滤")
            return stock_codes
        
        # 获取最新一天的市值数据
        latest_date = price_df["trade_date"].max()
        latest_data = price_df.filter(
            (pl.col("trade_date") == latest_date) & 
            pl.col("ts_code").is_in(stock_codes)
        )
        
        if latest_data.is_empty():
            return stock_codes
        
        filtered_stocks = set(stock_codes)
        
        # 最小市值过滤
        if self.config.min_total_mv > 0:
            before = len(filtered_stocks)
            valid_stocks_pl = latest_data.filter(pl.col("total_mv") >= self.config.min_total_mv).select("ts_code").unique()
            valid_stocks = set(valid_stocks_pl.to_series().to_list())
            filtered_stocks = filtered_stocks & valid_stocks
            removed = before - len(filtered_stocks)
            if removed > 0:
                logger.info(f"   [OK] 最小市值过滤(>={self.config.min_total_mv/1e4:.0f}亿)：-{removed} 只，剩余 {len(filtered_stocks)} 只")
        
        # 最大市值过滤
        if self.config.max_total_mv < 999999999:
            before = len(filtered_stocks)
            valid_stocks_pl = latest_data.filter(pl.col("total_mv") <= self.config.max_total_mv).select("ts_code").unique()
            valid_stocks = set(valid_stocks_pl.to_series().to_list())
            filtered_stocks = filtered_stocks & valid_stocks
            removed = before - len(filtered_stocks)
            if removed > 0:
                logger.info(f"   [OK] 最大市值过滤(<={self.config.max_total_mv/1e4:.0f}亿)：-{removed} 只，剩余 {len(filtered_stocks)} 只")
        
        return list(filtered_stocks)
    
    def filter_by_completeness(
        self,
        price_df: pl.DataFrame,
        stock_codes: list[str],
    ) -> list[str]:
        """按数据完整性过滤股票.
        
        Args:
            price_df: 价格数据 DataFrame
            stock_codes: 待检查的股票代码列表
            
        Returns:
            符合完整性要求的股票代码列表
        """
        if (
            self.config.min_completeness_ratio >= 1.0
            and self.config.max_missing_days >= 999999
        ):
            return stock_codes
        
        # 计算预期交易日数
        all_dates = price_df["trade_date"].unique()
        expected_days = len(all_dates)
        
        if expected_days == 0:
            return stock_codes
        
        # 按股票分组，检查每只股票的数据完整性
        subset_df = price_df.filter(pl.col("ts_code").is_in(stock_codes))
        stock_counts = subset_df.group_by("ts_code").agg(pl.count().alias("count"))
        
        valid_stocks = []
        for row in stock_counts.iter_rows(named=True):
            ts_code = row["ts_code"]
            count = row["count"]
            missing_days = expected_days - count
            completeness = count / expected_days
            
            meets_completeness = completeness >= self.config.min_completeness_ratio
            meets_missing_days = missing_days <= self.config.max_missing_days
            
            if meets_completeness and meets_missing_days:
                valid_stocks.append(ts_code)
        
        before_count = len(stock_counts)
        after_count = len(valid_stocks)
        
        if before_count != after_count:
            logger.info(
                f"🔍 数据完整性过滤（完整度>={self.config.min_completeness_ratio}, "
                f"缺失天数<={self.config.max_missing_days}）："
                f"{before_count} -> {after_count} 只股票"
            )
        
        return valid_stocks
