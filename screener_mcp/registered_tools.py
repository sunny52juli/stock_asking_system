"""
MCP 工具注册层 - 使用装饰器自动化工具注册

现在只需在一个地方定义函数，自动完成所有注册工作。
"""

from __future__ import annotations

import json
from typing import Any

from screener_mcp.auto_register import tool_registry

TOOL_ANNOTATIONS: dict[str, bool] = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


def _run_tool(name: str, arguments: dict[str, Any]) -> str:
    """执行指定工具，返回 JSON 字符串
    
    直接从 tool_implementations.py 导入执行器并执行
    """
    from screener_mcp.tool_implementations import SimpleToolExecutor
    
    try:
        result = SimpleToolExecutor.execute(name, arguments)
        if isinstance(result, dict) and "error" in result:
            return json.dumps({"error": result["error"]}, ensure_ascii=False)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"执行失败：{e}"}, ensure_ascii=False)


# ==================== 工具定义区域 ====================
# 新增工具示例：只需添加一个函数，自动完成所有注册工作！
#
# @tool_registry.register(
#     name="your_tool_name",
#     description="工具描述",
#     category="math/time_series/technical/statistical/feature_engineering/risk_metrics/screening"
# )
# def your_tool_name(param1: str, param2: int = 5) -> str:
#     return _run_tool("your_tool_name", {"param1": param1, "param2": param2})
#
# 就这么简单！参数类型（str/int/float）会自动提取，默认值也会自动识别
# ===========================================================
# 现在所有工具都在这里定义，使用装饰器自动注册！

# ---------- math ----------
@tool_registry.register(description="计算绝对值", category="math")
def abs_value(column: str) -> str:
    return _run_tool("abs_value", {"column": column})


@tool_registry.register(description="对数变换，log(1+x)", category="math")
def log_transform(column: str) -> str:
    return _run_tool("log_transform", {"column": column})


@tool_registry.register(description="平方根变换，保留符号", category="math")
def sqrt_transform(column: str) -> str:
    return _run_tool("sqrt_transform", {"column": column})


@tool_registry.register(description="幂次变换，x^n", category="math")
def power_transform(column: str, power: float = 2) -> str:
    return _run_tool("power_transform", {"column": column, "power": power})


@tool_registry.register(description="横截面排名归一化到 [0,1]", category="math")
def rank_normalize(column: str) -> str:
    return _run_tool("rank_normalize", {"column": column})


@tool_registry.register(description="Z-score 标准化", category="math")
def zscore_normalize(column: str) -> str:
    return _run_tool("zscore_normalize", {"column": column})


# ---------- time_series ----------
@tool_registry.register(description="移动平均", category="time_series")
def rolling_mean(column: str, window: int = 5) -> str:
    return _run_tool("rolling_mean", {"column": column, "window": window})


@tool_registry.register(description="百分比变化", category="time_series")
def pct_change(column: str, periods: int = 1) -> str:
    return _run_tool("pct_change", {"column": column, "periods": periods})


@tool_registry.register(description="移动标准差", category="time_series")
def rolling_std(column: str, window: int = 20) -> str:
    return _run_tool("rolling_std", {"column": column, "window": window})


@tool_registry.register(description="移动最大值", category="time_series")
def rolling_max(column: str, window: int = 20) -> str:
    return _run_tool("rolling_max", {"column": column, "window": window})


@tool_registry.register(description="移动最小值", category="time_series")
def rolling_min(column: str, window: int = 20) -> str:
    return _run_tool("rolling_min", {"column": column, "window": window})


@tool_registry.register(description="指数加权移动平均", category="time_series")
def ewm(column: str, span: int = 12) -> str:
    return _run_tool("ewm", {"column": column, "span": span})


# ---------- technical ----------
@tool_registry.register(description="相对强弱指标 RSI", category="technical")
def rsi(column: str, window: int = 14) -> str:
    return _run_tool("rsi", {"column": column, "window": window})


@tool_registry.register(description="MACD 指标", category="technical")
def macd(column: str, fast: int = 12, slow: int = 26, signal: int = 9) -> str:
    return _run_tool("macd", {"column": column, "fast": fast, "slow": slow, "signal": signal})


@tool_registry.register(description="KDJ 随机指标", category="technical")
def kdj(high: str = "最高价", low: str = "最低价", close: str = "收盘价", window: int = 9) -> str:
    return _run_tool("kdj", {"high": high, "low": low, "close": close, "window": window})


@tool_registry.register(description="平均真实波幅 ATR", category="technical")
def atr(high: str = "最高价", low: str = "最低价", close: str = "收盘价", window: int = 14) -> str:
    return _run_tool("atr", {"high": high, "low": low, "close": close, "window": window})


@tool_registry.register(description="能量潮 OBV", category="technical")
def obv(close: str = "收盘价", vol: str = "成交量") -> str:
    return _run_tool("obv", {"close": close, "vol": vol})


@tool_registry.register(description="股票最大振幅，计算周期内 (最高价 - 最低价)/前收盘价×100%", category="technical")
def amplitude(high: str = "最高价", low: str = "最低价", pre_close: str = "前收盘", window: int = 5) -> str:
    return _run_tool("amplitude", {"high": high, "low": low, "pre_close": pre_close, "window": window})


# ---------- statistical ----------
@tool_registry.register(description="滚动相关系数", category="statistical")
def correlation(x: str, y: str, window: int = 20) -> str:
    return _run_tool("correlation", {"x": x, "y": y, "window": window})


@tool_registry.register(description="偏度", category="statistical")
def skewness(column: str, window: int = 20) -> str:
    return _run_tool("skewness", {"column": column, "window": window})


@tool_registry.register(description="峰度", category="statistical")
def kurtosis(column: str, window: int = 20) -> str:
    return _run_tool("kurtosis", {"column": column, "window": window})


# ---------- feature_engineering ----------
@tool_registry.register(description="时间序列排名", category="feature_engineering")
def ts_rank(column: str, window: int = 10) -> str:
    return _run_tool("ts_rank", {"column": column, "window": window})


@tool_registry.register(description="时间序列最大值位置", category="feature_engineering")
def ts_argmax(column: str, window: int = 10) -> str:
    return _run_tool("ts_argmax", {"column": column, "window": window})


@tool_registry.register(description="时间序列最小值位置", category="feature_engineering")
def ts_argmin(column: str, window: int = 10) -> str:
    return _run_tool("ts_argmin", {"column": column, "window": window})


@tool_registry.register(description="线性衰减加权平均", category="feature_engineering")
def decay_linear(column: str, window: int = 10) -> str:
    return _run_tool("decay_linear", {"column": column, "window": window})


# ---------- risk_metrics ----------
@tool_registry.register(description="波动率（年化标准差）", category="risk_metrics")
def volatility(column: str, window: int = 20) -> str:
    return _run_tool("volatility", {"column": column, "window": window})


@tool_registry.register(description="最大回撤", category="risk_metrics")
def max_drawdown(column: str, window: int = 60) -> str:
    return _run_tool("max_drawdown", {"column": column, "window": window})


# ---------- screening ----------
@tool_registry.register(description="按行业筛选", category="screening")
def filter_by_industry(industry: str) -> str:
    return _run_tool("filter_by_industry", {"industry": industry})


@tool_registry.register(description="按市场筛选", category="screening")
def filter_by_market(market: str) -> str:
    return _run_tool("filter_by_market", {"market": market})


# ==================== 导出接口 ====================
def get_all_tools() -> dict[str, Any]:
    """获取所有已注册的工具"""
    return tool_registry.get_tool_definitions()


def register_to_mcp(mcp_instance: Any) -> None:
    """将所有工具注册到 FastMCP 实例"""
    tool_registry.register_to_mcp(mcp_instance)
