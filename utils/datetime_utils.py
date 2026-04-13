"""日期时间工具 - 日期格式化、解析等."""

from __future__ import annotations

from datetime import datetime


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
