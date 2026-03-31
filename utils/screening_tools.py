"""
股票筛选工具函数 - 策略生成专用

提供策略生成时需要的日期计算、数据加载等工具函数。
与配置分离，保持 config 目录的纯净。
"""

from datetime import datetime, timedelta
from typing import Optional


def get_trade_calendar():
    """获取交易日历对象"""
    from datahub import Calendar
    return Calendar()


def count_trade_days(start_date: str, end_date: str) -> list[str]:
    """获取日期范围内的交易日列表
    
    Args:
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)
    
    Returns:
        交易日列表
    """
    calendar = get_trade_calendar()
    return calendar.get_trade_dates(start_date, end_date)


def calculate_date_offset(screening_date: str, days: int, forward: bool = True) -> str:
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
        trade_dates = count_trade_days(candidate_dt.strftime("%Y%m%d"), screening_date)
        if len(trade_dates) >= days:
            return trade_dates[-days]
    else:
        candidate_dt = screening_dt + timedelta(days=buffer)
        trade_dates = count_trade_days(screening_date, candidate_dt.strftime("%Y%m%d"))
        if len(trade_dates) > days:
            return trade_dates[days]
    
    # 降级方案：使用自然日
    offset_dt = screening_dt + timedelta(days=days * (-1 if forward else 1))
    return offset_dt.strftime("%Y%m%d")


def get_data_start_date(
    screening_date: Optional[str] = None, 
    observation_days: Optional[int] = None
) -> str:
    """获取数据开始日期 (筛选日期往前推 observation_days 个交易日)
    
    Args:
        screening_date: 筛选日期 (YYYYMMDD)，默认使用 strategy_des 的配置
        observation_days: 观察期长度 (交易日)，默认使用 strategy_des 的配置
    
    Returns:
        数据开始日期 (YYYYMMDD)
    """
    from config.strategy_des import StrategyDescriptions
    
    if screening_date is None:
        screening_date = StrategyDescriptions.SCREENING_DATE
    if observation_days is None:
        observation_days = StrategyDescriptions.OBSERVATION_PERIOD_DAYS
    
    return calculate_date_offset(screening_date, observation_days, forward=True)


def get_observation_period() -> int:
    """获取观察期长度 (交易日)
    
    Returns:
        观察期长度
    """
    from config.strategy_des import StrategyDescriptions
    return StrategyDescriptions.OBSERVATION_PERIOD_DAYS


def validate_screening_date(screening_date: Optional[str] = None) -> bool:
    """验证筛选日期格式
    
    Args:
        screening_date: 筛选日期 (YYYYMMDD)
        
    Returns:
        True if valid
        
    Raises:
        ValueError: 如果日期格式无效
    """
    from config.strategy_des import StrategyDescriptions
    
    if screening_date is None:
        screening_date = StrategyDescriptions.SCREENING_DATE
    
    try:
        datetime.strptime(screening_date, "%Y%m%d")
        return True
    except ValueError:
        raise ValueError(f"日期格式错误，请使用 YYYYMMDD 格式：{screening_date}")


def set_screening_date(screening_date: str) -> None:
    """设置自定义筛选日期
    
    Args:
        screening_date: 筛选日期 (YYYYMMDD)
    """
    from config.strategy_des import StrategyDescriptions
    
    validate_screening_date(screening_date)
    StrategyDescriptions.SCREENING_DATE = screening_date
