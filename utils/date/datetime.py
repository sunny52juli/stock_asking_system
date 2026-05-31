"""日期时间工具 - 日期格式化、解析、交易日处理等."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datahub.core.query import Query

logger = logging.getLogger(__name__)

# ==================== 日期格式常量 ====================

DATE_FMT_YMD = "%Y%m%d"           # YYYYMMDD (如: 20260512)
DATE_FMT_ISO = "%Y-%m-%d"         # ISO 格式 (如: 2026-05-12)
DATE_FMT_FULL = "%Y-%m-%d %H:%M:%S"  # 完整日期时间 (如: 2026-05-12 14:30:00)
DATE_FMT_TIMESTAMP = "%Y%m%d_%H%M%S"  # 时间戳格式 (如: 20260512_143000)


def format_date(date_obj: datetime | None = None, fmt: str = DATE_FMT_YMD) -> str:
    """格式化日期为字符串.
    
    Args:
        date_obj: 日期对象，默认为当前时间
        fmt: 格式字符串，默认 YYYYMMDD
        
    Returns:
        格式化后的日期字符串
    """
    if date_obj is None:
        date_obj = datetime.now()
    return date_obj.strftime(fmt)


def get_today_str(fmt: str = DATE_FMT_YMD) -> str:
    """获取当前日期字符串.
    
    Args:
        fmt: 格式字符串，默认 YYYYMMDD
        
    Returns:
        当前日期的字符串表示
    """
    return datetime.now().strftime(fmt)


def parse_date(date_str: str, fmt: str = DATE_FMT_YMD) -> datetime:
    """解析日期字符串.
    
    Args:
        date_str: 日期字符串
        fmt: 格式字符串，默认 YYYYMMDD
        
    Returns:
        datetime 对象
    """
    return datetime.strptime(date_str, fmt)


def generate_date_range(start_date: str, end_date: str) -> list[str]:
    """生成日期范围字符串列表.
    
    Args:
        start_date: 起始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)
        
    Returns:
        日期字符串列表
    """
    start = datetime.strptime(start_date, DATE_FMT_YMD)
    end = datetime.strptime(end_date, DATE_FMT_YMD)
    
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime(DATE_FMT_YMD))
        current += timedelta(days=1)
    
    return dates


class DateAdjuster:
    """日期调整器 - 处理交易日历和日期范围."""
    
    def __init__(self, calendar):
        """初始化.
        
        Args:
            calendar: 交易日历对象
        """
        self.calendar = calendar
    
    def adjust_query_dates(self, query: Query) -> Query:
        """调整查询日期为交易日.
        
        Args:
            query: 原始查询
            
        Returns:
            调整后的查询
        """
        if not (query.start_date and query.end_date):
            return query
        
        adjusted_start = query.start_date
        adjusted_end = query.end_date
        
        # 只调整 end_date（往前找最近交易日）
        if query.end_date and not self.calendar.is_trade_day(query.end_date):
            latest_trade_date = self.calendar.get_latest_trade_date(
                str(int(query.end_date) + 1)
            )
            if latest_trade_date and latest_trade_date >= (query.start_date or ""):
                adjusted_end = latest_trade_date
                logger.info(
                    "📅 End datetime %s → %s (trade day)",
                    query.end_date,
                    adjusted_end,
                )
            else:
                logger.warning("⚠️ No trade days before %s", query.end_date)
        
        # 如果日期有变化，创建新查询
        if adjusted_start != query.start_date or adjusted_end != query.end_date:
            from datahub.core.query import Query as DatahubQuery
            return DatahubQuery(
                dataset=query.dataset,
                start_date=adjusted_start,
                end_date=adjusted_end,
                codes=query.codes,
                fields=query.fields,
                index_code=query.index_code,
            )
        
        return query
    
    def get_trade_dates(self, start_date: str, end_date: str) -> list[str] | None:
        """获取交易日期列表.
        
        Args:
            start_date: 起始日期
            end_date: 结束日期
            
        Returns:
            交易日期列表，或 None（如果失败）
        """
        try:
            trade_dates = self.calendar.get_trade_dates(start_date, end_date)
            if trade_dates:
                logger.debug(
                    "📅 Trade calendar: %d days (%s ~ %s)",
                    len(trade_dates),
                    trade_dates[0],
                    trade_dates[-1],
                )
                return trade_dates
            else:
                logger.warning("⚠️ Calendar returned empty list")
                return None
        except Exception as e:
            logger.error("❌ Calendar error: %s", e)
            return None


# ==================== 交易日历工具 ====================

def count_trade_days(start_date: str, end_date: str) -> list[str]:
    """获取日期范围内的交易日列表
    
    Args:
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)
    
    Returns:
        交易日列表
    """
    from datahub import Calendar
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
                f"[WARN] 交易日历返回 {len(trade_dates)} 天，不足 {days} 天，扩大搜索范围"
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
    from infrastructure.config.settings import get_settings
    from datahub import Calendar
    import pandas as pd
    
    if screening_date is None:
        calendar = Calendar()
        today = pd.Timestamp.now().strftime("%Y%m%d")
        screening_date = calendar.get_latest_trade_date(today) or today
    
    if observation_days is None:
        observation_days = get_settings().observation_days
    
    return calculate_date_offset(screening_date, observation_days, forward=True)
