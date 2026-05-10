"""日期时间工具 - 日期格式化、解析、交易日处理等."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datahub.core.query import Query

logger = logging.getLogger(__name__)


def format_date(date_obj: datetime | None = None, fmt: str = "%Y%m%d") -> str:
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


def parse_date(date_str: str, fmt: str = "%Y%m%d") -> datetime:
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
    start = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")
    
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y%m%d"))
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
                    "📅 End date %s → %s (trade day)",
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
