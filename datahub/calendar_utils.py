"""交易日历工具函数 - 日期计算、交易日查询等."""

from datetime import datetime, timedelta

from datahub import Calendar


from infrastructure.config.settings import get_settings
from infrastructure.logging.logger import get_logger
def count_trade_days(start_date: str, end_date: str) -> list[str]:
    """获取日期范围内的交易日列表
    
    Args:
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)
    
    Returns:
        交易日列表
    """
    calendar = Calendar()
    return calendar.get_trade_dates(start_date, end_date)


def calculate_date_offset(screening_date: str, days: int, forward: bool = True) -> str:
    """根据筛选日期计算偏移后的日期
    
    Args:
        screening_date: 筛选日期 (YYYYMMDD)
        days: 偏移天数 (交易日)
        forward: True=往前推，False=往后推
        
    Returns:
        偏移后的日期 (YYYYMMDD)
    """
    logger = get_logger(__name__)
    
    screening_dt = datetime.strptime(screening_date, "%Y%m%d")
    buffer = int(days * 1.5 + 20)  # 预留节假日
    
    if forward:
        candidate_dt = screening_dt - timedelta(days=buffer)
        trade_dates = count_trade_days(candidate_dt.strftime("%Y%m%d"), screening_date)
        if len(trade_dates) >= days:
            return trade_dates[-days]
        else:
            # 交易日不足，扩大搜索范围
            logger.warning(
                f"⚠️ 交易日历返回 {len(trade_dates)} 天，不足 {days} 天，扩大搜索范围"
            )
            buffer = int(days * 2.0 + 30)
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


def get_data_start_date(screening_date: str | None = None, observation_days: int | None = None) -> str:
    """获取数据开始日期 (筛选日期往前推 observation_days 个交易日)
    
    Args:
        screening_date: 筛选日期 (YYYYMMDD)，默认使用最新交易日
        observation_days: 观察期长度 (交易日)，默认 80 天
    
    Returns:
        数据开始日期 (YYYYMMDD)
    """
    
    if screening_date is None:
        calendar = Calendar()
        today = pd.Timestamp.now().strftime("%Y%m%d")
        screening_date = calendar.get_latest_trade_date(today) or today
    
    if observation_days is None:
        observation_days = get_settings().observation_days
    
    return calculate_date_offset(screening_date, observation_days, forward=True)
