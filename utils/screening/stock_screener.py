#!/usr/bin/env python3
"""
股票筛选执行引擎 (Utils) - 向后兼容适配层

本模块为向后兼容保留，实际实现已迁移至 src.screening.executor。
新代码应直接使用 src.screening.executor.ScreeningExecutor。

示例:
    # 推荐方式
    executor = ScreeningExecutor(data, screening_date=screening_date)
    results = executor.run_screening(screening_logic, top_n=20)
    
    # 兼容旧代码（本模块）
    screener = StockScreener(data, screening_date=screening_date)
    results = screener.execute_screening(screening_logic, top_n=20)
"""

from typing import Any, Optional
import polars as pl

from infrastructure.logging.logger import get_logger
from src.agent.services.index_loader import IndexDataLoader
from src.screening.executor import ScreeningExecutor

logger = get_logger(__name__)


class StockScreener:
    """股票筛选器 - 向后兼容的适配层.
    
    注意：本类仅为兼容旧代码，实际功能委托给 src.screening.executor.ScreeningExecutor。
    新代码应直接使用 ScreeningExecutor。
    """

    def __init__(
        self,
        data: pl.DataFrame,
        screening_date: Optional[str] = None,
        stock_codes: Optional[list[str]] = None,
        index_data: Optional[pl.DataFrame] = None,
    ):
        """初始化股票筛选器（兼容旧接口）.
        
        Args:
            data: 市场数据 DataFrame (MultiIndex: trade_date, ts_code)
            screening_date: 筛选日期（YYYYMMDD 格式），默认使用最新交易日
            stock_codes: 预筛选后的股票代码列表（可选，将被忽略）
            index_data: 指数数据 DataFrame (columns: trade_date, index_close)，可选
        """
        
        self.data = data
        self.index_data = index_data
        
        # 如果已提供有效的指数数据，直接使用
        if index_data is not None:
            if not index_data.is_empty():
                logger.info(f"✅ StockScreener 使用传入的指数数据: {len(index_data)} 条记录")
                logger.debug(f"   指数数据列: {list(index_data.columns)}")
            else:
                logger.warning("⚠️ 传入的指数数据为空")
                index_data = None
        else:
            # 仅在未提供指数数据时尝试自动加载
            logger.info("📊 未提供指数数据，尝试自动加载...")
            try:
                loader = IndexDataLoader()
                loaded_index_data = loader.load_and_merge(data, stock_codes)
                
                if loaded_index_data is not None and not loaded_index_data.is_empty():
                    self.index_data = loaded_index_data
                    logger.info(f"✅ 成功加载指数数据: {len(self.index_data)} 条记录")
                else:
                    logger.warning("⚠️ 自动加载指数数据返回空结果或None")
            except Exception as e:
                logger.warning(f"⚠️ 自动加载指数数据失败: {e}")
        
        # 创建实际的筛选执行器，传递独立的指数数据
        
        # 验证数据格式（Polars DataFrame）
        required_cols = ['ts_code', 'trade_date']
        missing_cols = [col for col in required_cols if col not in data.columns]
        if missing_cols:
            raise ValueError(f"Polars DataFrame 缺少必需列: {missing_cols}")
        
        self._executor = ScreeningExecutor(
            data=self.data,
            screening_date=screening_date,
            index_data=self.index_data
        )
        
        # 保存参数用于日志
        self.screening_date_str = screening_date or self._executor.screening_date_str
        self.latest_date = self._executor.latest_date

    def execute_screening(
        self, screening_logic: dict, top_n: int = 20, query: str = "", iteration: int = 1
    ) -> list[dict[str, Any]]:
        """执行股票筛选（兼容旧接口）.
        
        Args:
            screening_logic: 筛选逻辑配置
            top_n: 返回前 N 只股票
            query: 原始查询文本
            iteration: 重试次数（仅用于日志，不影响实际逻辑）
            
        Returns:
            候选股票列表
        """
        if iteration > 1:
            logger.info(f"🔄 第 {iteration} 次筛选迭代...")
        
        # 委托给实际的执行器
        return self._executor.run_screening(
            screening_logic=screening_logic,
            top_n=top_n,
            query=query,
        )


def create_stock_screener(
    data: pl.DataFrame,
    screening_date: Optional[str] = None,
    stock_codes: Optional[list[str]] = None,
    index_data: Optional[pl.DataFrame] = None,
) -> StockScreener:
    """创建 StockScreener 实例的便捷函数（兼容旧接口）。"""
    return StockScreener(
        data=data,
        screening_date=screening_date,
        stock_codes=stock_codes,
        index_data=index_data,
    )
