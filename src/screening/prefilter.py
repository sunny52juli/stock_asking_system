"""预筛选逻辑 - 行业、市场等过滤条件检测与执行."""

from __future__ import annotations

import pandas as pd

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

# 预筛选工具名称常量
PRE_FILTER_TOOLS = frozenset(["filter_by_industry", "filter_by_market"])


def _execute_tool(tool_name: str, data, params: dict, computed_vars: dict):
    """执行工具的包装函数 - 延迟导入以避免循环依赖."""
    from src.agent.tools.bridge import execute_tool_impl
    return execute_tool_impl(
        tool_name=tool_name,
        data=data,
        params=params,
        computed_vars=computed_vars
    )


class PreFilterEngine:
    """预筛选引擎 - 负责股票池的初步过滤.
    
    核心功能:
    1. 从筛选逻辑中提取预筛选条件
    2. 智能检测查询文本中的行业/市场信息
    3. 执行预筛选工具并合并结果
    """

    def __init__(self, data: pd.DataFrame, latest_date: pd.Timestamp, all_stock_codes: list[str]):
        """初始化预筛选引擎.
        
        Args:
            data: 市场数据 DataFrame
            latest_date: 最新交易日
            all_stock_codes: 全部股票代码列表
        """
        self.data = data
        self.latest_date = latest_date
        self.all_stock_codes = all_stock_codes

    def prefilter(self, screening_logic: dict, query: str = "") -> list[str]:
        """执行预筛选.
        
        Args:
            screening_logic: 筛选逻辑配置
            query: 原始查询文本（用于智能检测）
            
        Returns:
            预筛选后的股票代码列表
        """
        logger.info("\n🔍 步骤 1: 预筛选股票池...")
        
        # 提取预筛选工具
        pre_filter_tools = self._extract_prefilter_tools(screening_logic, query)
        
        if not pre_filter_tools:
            logger.info("   未检测到预筛选条件，使用全部股票池")
            return self.all_stock_codes
        
        logger.info(f"   检测到 {len(pre_filter_tools)} 个预筛选条件:")
        for tool_step in pre_filter_tools:
            logger.info(f"      - {tool_step.get('tool')}({tool_step.get('params', {})})")
        
        # 执行预筛选
        filtered_codes = self._execute_prefilters(pre_filter_tools)
        logger.info(f"   预筛选后：{len(filtered_codes)} 只股票")
        
        return filtered_codes

    def _extract_prefilter_tools(self, screening_logic: dict, query: str) -> list[dict]:
        """提取预筛选工具（去重 + 智能检测）."""
        tools = screening_logic.get("tools", [])
        seen: set[tuple[str, str]] = set()
        pre_filter_tools: list[dict] = []

        def _add_tool(tool_step: dict):
            tool_name = tool_step.get("tool", "")
            params = tool_step.get("params", {})
            if tool_name == "filter_by_industry":
                key = ("industry", params.get("industry", ""))
            elif tool_name == "filter_by_market":
                key = ("market", params.get("market", ""))
            else:
                return
            if key[1] and key not in seen:
                seen.add(key)
                pre_filter_tools.append(tool_step)

        # 从 tools 中提取
        for tool_step in tools:
            if tool_step.get("tool", "") in PRE_FILTER_TOOLS:
                _add_tool(tool_step)
        
        # 智能检测
        for tool_step in self._auto_detect_prefilters(screening_logic, query):
            _add_tool(tool_step)

        return pre_filter_tools

    def _auto_detect_prefilters(self, screening_logic: dict, query: str) -> list[dict]:
        """智能检测预筛选条件（从查询文本中提取行业、市场等信息）."""
        detected_tools = []
        available_industries = self._get_available_industries()
        
        text_sources = [
            query,
            screening_logic.get("name", ""),
            screening_logic.get("rationale", ""),
            screening_logic.get("expression", ""),
        ]
        combined_text = " ".join(str(t) for t in text_sources if t)
        
        if not combined_text.strip():
            return detected_tools
        
        # 检测行业
        if available_industries:
            sorted_industries = sorted(available_industries, key=len, reverse=True)
            matched_industries = []
            remaining_text = combined_text
            
            for industry in sorted_industries:
                if industry in remaining_text:
                    matched_industries.append(industry)
                    remaining_text = remaining_text.replace(industry, "")
            
            for industry in matched_industries:
                detected_tools.append({
                    "tool": "filter_by_industry",
                    "params": {"industry": industry},
                    "var": f"is_{industry}"
                })
        
        # 检测市场板块
        market_keywords = {
            "主板": "主板",
            "创业板": "创业板",
            "科创板": "科创板",
            "北交所": "北交所"
        }
        for keyword, market_name in market_keywords.items():
            if keyword in combined_text:
                detected_tools.append({
                    "tool": "filter_by_market",
                    "params": {"market": market_name},
                    "var": f"is_{market_name}"
                })
        
        if detected_tools:
            logger.info("   🔍 智能检测到预筛选条件:")
            for tool_step in detected_tools:
                logger.info(f"      - {tool_step['tool']}({tool_step['params']})")
        
        return detected_tools

    def _get_available_industries(self) -> list[str]:
        """从数据中提取可用行业列表."""
        try:
            latest_data = self.data.xs(self.latest_date, level="trade_date")
            if "industry" in latest_data.columns:
                industries = latest_data["industry"].dropna().unique().tolist()
                return [str(ind) for ind in industries if str(ind).strip()]
        except Exception:
            pass
        
        try:
            if isinstance(self.data.index, pd.MultiIndex):
                industries = self.data.reset_index()["industry"].dropna().unique().tolist()
            else:
                industries = self.data["industry"].dropna().unique().tolist()
            return [str(ind) for ind in industries if str(ind).strip()]
        except Exception:
            return []

    def _execute_prefilters(self, pre_filter_tools: list[dict]) -> list[str]:
        """执行预筛选工具并合并结果."""
        latest_data = self.data.xs(self.latest_date, level="trade_date")
        tool_results: dict[str, list[pd.Series]] = {}
        
        for tool_step in pre_filter_tools:
            tool_name = tool_step.get("tool")
            params = tool_step.get("params", {})
            try:
                result = _execute_tool(
                    tool_name=tool_name,
                    data=latest_data,
                    params=params,
                    computed_vars={}
                )
                tool_results.setdefault(tool_name, []).append(result)
                logger.info(f"      ↳ {tool_name}({params}): 匹配 {result.sum()} 只股票")
            except Exception as e:
                logger.error(f"      ⚠️ 预筛选工具 {tool_name} 执行失败：{e}")
                import traceback
                traceback.print_exc()
        
        # 合并所有预筛选条件
        filter_mask = pd.Series(True, index=latest_data.index)
        for tool_name, results in tool_results.items():
            tool_mask = pd.concat(results, axis=1).any(axis=1)
            filter_mask &= tool_mask
            logger.info(f"      ↳ {tool_name} 合计匹配：{tool_mask.sum()} 只股票")
        
        return latest_data[filter_mask].index.tolist()
