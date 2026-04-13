"""筛选执行器 - 负责高效执行股票筛选逻辑.

本模块从 utils/screening/stock_screener.py 重构而来，
职责更加清晰，命名更加语义化。

已拆分为：
- prefilter.py: 预筛选逻辑
- batch_calculator.py: 批量计算引擎
"""

from typing import Any, Optional

import pandas as pd

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class ScreeningExecutor:
    """股票筛选执行器 - 组合预筛选和批量计算."""

    def __init__(self, data: pd.DataFrame, screening_date: Optional[str] = None):
        """初始化股票筛选器.
        
        Args:
            data: 市场数据 DataFrame
            screening_date: 筛选日期（YYYYMMDD 格式），默认使用最新交易日
        """
        from datahub import Calendar
        from src.screening.prefilter import PreFilterEngine
        from src.screening.batch_calculator import BatchCalculator
        
        self.data = data
        
        # 使用传入的日期或自动获取最新交易日
        if screening_date is None:
            calendar = Calendar()
            today = pd.Timestamp.now().strftime("%Y%m%d")
            screening_date = calendar.get_latest_trade_date(today)
            if not screening_date:
                screening_date = today
        
        self.screening_date_str = screening_date
        self.latest_date = pd.to_datetime(self.screening_date_str, format="%Y%m%d")
        
        # 验证数据是否包含筛选日期
        all_dates = sorted(data.index.get_level_values("trade_date").unique())
        
        if len(all_dates) == 0:
            raise ValueError("数据中不包含任何交易日")
        
        if self.latest_date not in all_dates:
            available_dates = [d for d in all_dates if d <= self.latest_date]
            if available_dates:
                self.latest_date = available_dates[-1]
                logger.warning(
                    f"数据中不存在配置的筛选日期 {self.screening_date_str}，"
                    f"使用最近的交易日：{self.latest_date.strftime('%Y-%m-%d')}"
                )
            else:
                raise ValueError(f"数据中没有筛选日期 {self.screening_date_str} 及之前的数据")
        
        # 验证是否有足够的历史数据
        try:
            screen_idx = all_dates.index(self.latest_date)
            from infrastructure.config.settings import get_settings
            observation_days = get_settings().observation_days
            available_days = screen_idx + 1
            if available_days < observation_days:
                logger.warning(
                    f"数据历史不足：筛选日期前共有 {available_days} 个交易日（含当日），"
                    f"建议至少 {observation_days} 个交易日以确保指标计算准确"
                )
        except ValueError:
            pass
        
        self.all_stock_codes = data.index.get_level_values("ts_code").unique().tolist()
        
        # 初始化子模块
        self.prefilter_engine = PreFilterEngine(
            data=data,
            latest_date=self.latest_date,
            all_stock_codes=self.all_stock_codes
        )
        self.batch_calculator = BatchCalculator(
            data=data,
            latest_date=self.latest_date
        )

    def run_screening(
        self, screening_logic: dict, top_n: int = 20, query: str = ""
    ) -> list[dict[str, Any]]:
        """执行股票筛选.
        
        Args:
            screening_logic: 筛选逻辑配置
            top_n: 返回Top N只股票
            query: 原始查询文本（用于智能检测预筛选条件）
            
        Returns:
            筛选结果列表
        """
        # 步骤 1: 预筛选
        filtered_stock_codes = self.prefilter_engine.prefilter(screening_logic, query=query)
        
        if not filtered_stock_codes:
            logger.warning("⚠️ 预筛选后无股票，请检查筛选条件")
            return []
        
        # 步骤 2: 批量计算
        candidates = self.batch_calculator.batch_screen(
            stock_codes=filtered_stock_codes,
            screening_logic=screening_logic
        )
        
        # 按置信度排序并返回 Top N
        results = sorted(candidates, key=lambda x: x["confidence"], reverse=True)[:top_n]
        return results


def create_screening_executor(
    data: pd.DataFrame,
    screening_date: Optional[str] = None,
) -> ScreeningExecutor:
    """创建筛选执行器实例的便捷函数."""
    return ScreeningExecutor(data, screening_date=screening_date)
