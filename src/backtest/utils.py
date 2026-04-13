"""回测辅助工具函数."""

from datetime import datetime, timedelta
from typing import Optional


def get_holding_period_end_date(screening_date: str, holding_days: int) -> str:
    """获取持有期结束日期
    
    Args:
        screening_date: 筛选日期 (YYYYMMDD)
        holding_days: 持有天数 (交易日)
        
    Returns:
        持有期结束日期 (YYYYMMDD)
    """
    from src.screening.utils import calculate_date_offset
    return calculate_date_offset(screening_date, holding_days, forward=False)


def format_return_percentage(return_value: float) -> str:
    """格式化收益率为百分比字符串
    
    Args:
        return_value: 收益率值（小数）
        
    Returns:
        格式化后的字符串，如 "+15.23%" 或 "-8.45%"
    """
    percentage = return_value * 100
    sign = "+" if percentage >= 0 else ""
    return f"{sign}{percentage:.2f}%"


def calculate_win_rate(results: list[dict]) -> float:
    """计算胜率
    
    Args:
        results: 回测结果列表，每个元素包含 'return' 字段
        
    Returns:
        胜率（0-1之间的小数）
    """
    if not results:
        return 0.0
    
    winning_count = sum(1 for r in results if r.get("return", 0) > 0)
    return winning_count / len(results)


def calculate_avg_return(results: list[dict]) -> float:
    """计算平均收益率
    
    Args:
        results: 回测结果列表，每个元素包含 'return' 字段
        
    Returns:
        平均收益率（小数）
    """
    if not results:
        return 0.0
    
    total_return = sum(r.get("return", 0) for r in results)
    return total_return / len(results)


def calculate_sharpe_ratio(returns: list[float], risk_free_rate: float = 0.03) -> float:
    """计算夏普比率
    
    Args:
        returns: 收益率列表（小数）
        risk_free_rate: 无风险利率（年化，默认3%）
        
    Returns:
        夏普比率
    """
    import numpy as np
    
    if not returns or len(returns) < 2:
        return 0.0
    
    returns_array = np.array(returns)
    excess_returns = returns_array - risk_free_rate / 252  # 日化无风险利率
    
    if np.std(excess_returns) == 0:
        return 0.0
    
    sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)  # 年化
    return float(sharpe)
