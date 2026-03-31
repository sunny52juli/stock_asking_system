"""
股票配置模块 - 管理股票池筛选规则和回测配置
"""

from datetime import datetime, timedelta
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)


class StockConfig:
    """股票配置类 - 包含股票池筛选和回测相关配置"""

    # ==================== 股票池筛选规则 ====================
    STOCK_POOL_MIN_LIST_DAYS = 180
    STOCK_POOL_EXCLUDE_ST = True
    EXCLUDE_SUSPENDED_STOCKS = True

    # ==================== 回测配置 ====================
    BACKTEST_DEFAULT_INDEX_CODE: str | None = None  # 默认全市场
    BACKTEST_LOOKBACK_DAYS: list[int] = [4, 10, 20]
    BACKTEST_SCREENING_DATE: str = "20260201"  # 格式：YYYYMMDD（已调整：确保前有至少 80 个交易日）
    OBSERVATION_PERIOD_DAYS: int = 80  # 观察期长度 (交易日)

    @classmethod
    def _get_trade_calendar(cls):
        """获取交易日历对象"""
        from datahub import Calendar
        return Calendar()
    
    @classmethod
    def _count_trade_days(cls, start_date: str, end_date: str) -> list[str]:
        """获取日期范围内的交易日列表"""
        calendar = cls._get_trade_calendar()
        return calendar.get_trade_dates(start_date, end_date)
    
    @classmethod
    def _calculate_date_offset(cls, screening_date: str, days: int, forward: bool = True) -> str:
        """
        根据筛选日期计算偏移后的日期
        
        Args:
            screening_date: 筛选日期 (YYYYMMDD)
            days: 偏移天数 (交易日)
            forward: True=往前推，False=往后推
            
        Returns:
            偏移后的日期 (YYYYMMDD)
        """
        screening_dt = datetime.strptime(screening_date, "%Y%m%d")
        buffer = int(days * 1.5 + 20)  # 预留节假日
        
        if forward:
            candidate_dt = screening_dt - timedelta(days=buffer)
            trade_dates = cls._count_trade_days(candidate_dt.strftime("%Y%m%d"), screening_date)
            if len(trade_dates) >= days:
                return trade_dates[-days]
        else:
            candidate_dt = screening_dt + timedelta(days=buffer)
            trade_dates = cls._count_trade_days(screening_date, candidate_dt.strftime("%Y%m%d"))
            if len(trade_dates) > days:
                return trade_dates[days]
        
        # 降级方案：使用自然日
        offset_dt = screening_dt + timedelta(days=days * (-1 if forward else 1))
        return offset_dt.strftime("%Y%m%d")

    @classmethod
    def get_observation_period(cls) -> int:
        """获取观察期长度 (交易日)"""
        return cls.OBSERVATION_PERIOD_DAYS
    
    @classmethod
    def get_data_start_date(cls, screening_date: str | None = None, observation_days: int | None = None) -> str:
        """获取数据开始日期 (筛选日期往前推 observation_days 个交易日)"""
        if screening_date is None:
            screening_date = cls.BACKTEST_SCREENING_DATE
        if observation_days is None:
            observation_days = cls.OBSERVATION_PERIOD_DAYS
        return cls._calculate_date_offset(screening_date, observation_days, forward=True)
    
    @classmethod
    def get_data_end_date(cls, screening_date: str | None = None, holding_periods: list[int] | None = None) -> str:
        """获取数据结束日期 (筛选日期往后推 max_holding_period 个交易日)"""
        if screening_date is None:
            screening_date = cls.BACKTEST_SCREENING_DATE
        if holding_periods is None:
            holding_periods = cls.BACKTEST_LOOKBACK_DAYS
        max_holding = max(holding_periods)
        return cls._calculate_date_offset(screening_date, max_holding, forward=False)
    
    @classmethod
    def validate_screening_date(cls, screening_date: str | None = None) -> bool:
        """验证筛选日期格式"""
        if screening_date is None:
            screening_date = cls.BACKTEST_SCREENING_DATE
        try:
            datetime.strptime(screening_date, "%Y%m%d")
            return True
        except ValueError:
            raise ValueError(f"日期格式错误，请使用 YYYYMMDD 格式：{screening_date}")
    
    @classmethod
    def set_screening_date(cls, screening_date: str) -> None:
        """设置自定义筛选日期"""
        cls.validate_screening_date(screening_date)
        cls.BACKTEST_SCREENING_DATE = screening_date
