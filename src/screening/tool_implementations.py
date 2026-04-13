"""工具实现注册表 - 提供预筛选工具的本地实现."""

import pandas as pd


def filter_by_industry(data: pd.DataFrame, params: dict, computed_vars: dict) -> pd.Series:
    """按行业过滤股票.
    
    Args:
        data: 股票数据 DataFrame
        params: 参数字典，包含 industry 字段
        computed_vars: 已计算变量
        
    Returns:
        Boolean Series，标记匹配的股票
    """
    industry = params.get("industry", "")
    if not industry or "industry" not in data.columns:
        return pd.Series(False, index=data.index)
    
    return data["industry"] == industry


def filter_by_market(data: pd.DataFrame, params: dict, computed_vars: dict) -> pd.Series:
    """按市场板块过滤股票.
    
    Args:
        data: 股票数据 DataFrame
        params: 参数字典，包含 market 字段（主板/创业板/科创板）
        computed_vars: 已计算变量
        
    Returns:
        Boolean Series，标记匹配的股票
    """
    market = params.get("market", "")
    if not market:
        return pd.Series(True, index=data.index)
    
    # 根据股票代码前缀判断市场
    ts_codes = data.index if isinstance(data.index, pd.Index) else data.get("ts_code", pd.Series())
    
    if market == "主板":
        mask = ts_codes.str.startswith(("600", "601", "603", "605", "000", "001", "002", "003"))
    elif market == "创业板":
        mask = ts_codes.str.startswith("300")
    elif market == "科创板":
        mask = ts_codes.str.startswith("688")
    elif market == "北交所":
        mask = ts_codes.str.startswith(("8", "4", "9"))
    else:
        mask = pd.Series(True, index=data.index)
    
    return mask


# 工具注册表
TOOL_REGISTRY = {
    "filter_by_industry": filter_by_industry,
    "filter_by_market": filter_by_market,
}
