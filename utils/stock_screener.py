#!/usr/bin/env python3
"""
股票筛选执行引擎 (Utils)

依赖 screener_mcp.expression_tools 和 screener_mcp.tool_implementations 提供实际的计算功能。

示例:
    from utils.stock_screener import StockScreener
    screener = StockScreener(data)
    results = screener.execute_screening(screening_logic, top_n=20)
"""

import time as _time
from typing import Any

import numpy as np
import pandas as pd

# 导入 MCP 模块
from screener_mcp.expression_tools import NamespaceBuilder
from screener_mcp.tool_implementations import execute_tool as execute_tool_impl
from utils.logger import get_logger

logger = get_logger(__name__)

# 预筛选工具名称常量
_PRE_FILTER_TOOLS = frozenset(["filter_by_industry", "filter_by_market"])


class StockScreener:
    """
    股票筛选执行器 - 负责高效执行筛选逻辑

    核心功能:
    1. 预筛选：识别并优先执行行业、市场等过滤条件
    2. 批量计算：对筛选后的股票池批量计算技术指标
    3. 结果排序：按置信度排序并返回 Top N
    """

    def __init__(self, data: pd.DataFrame, screening_date: str | None = None):
        """初始化股票筛选器
        
        Args:
            data: 市场数据 DataFrame
            screening_date: 筛选日期（YYYYMMDD 格式），默认使用 strategy_des 的配置
        """
        from config.strategy_des import StrategyDescriptions
        
        self.data = data
        self.namespace_builder = NamespaceBuilder()
        
        # 使用配置的筛选日期或传入的日期
        self.screening_date_str = screening_date or StrategyDescriptions.SCREENING_DATE
        self.latest_date = pd.to_datetime(self.screening_date_str, format="%Y%m%d")
        
        # 验证数据是否包含筛选日期
        all_dates = sorted(data.index.get_level_values("trade_date").unique())
        self._all_dates = all_dates
        
        if len(all_dates) == 0:
            raise ValueError("数据中不包含任何交易日")
        
        # 检查数据范围
        data_min_date = all_dates[0]
        data_max_date = all_dates[-1]
        
        if self.latest_date not in all_dates:
            # 如果筛选日期不在数据中，找到最接近的日期
            available_dates = [d for d in all_dates if d <= self.latest_date]
            if available_dates:
                self.latest_date = available_dates[-1]
                logger.warning(f"数据中不存在配置的筛选日期 {self.screening_date_str}，使用最近的交易日：{self.latest_date.strftime('%Y-%m-%d')}")
            else:
                raise ValueError(f"数据中没有筛选日期 {self.screening_date_str} 及之前的数据")
        
        # 验证是否有足够的历史数据（观察期）
        try:
            screen_idx = all_dates.index(self.latest_date)
            from utils.screening_tools import get_observation_period
            observation_days = get_observation_period()
            if screen_idx + 1 < observation_days:
                logger.warning(
                    f"数据历史不足：筛选日期前有 {screen_idx} 个交易日，"
                    f"建议至少 {observation_days} 个交易日以确保指标计算准确"
                )
        except ValueError:
            pass  # 已在上面处理
        
        self.all_stock_codes = data.index.get_level_values("ts_code").unique().tolist()
        print("   📊 筛选器初始化完成")
        print(f"      筛选日期：{self.latest_date.strftime('%Y-%m-%d')}")
        print(f"      股票总数：{len(self.all_stock_codes)}")

    def execute_screening(
        self, screening_logic: dict, top_n: int = 20, query: str = ""
    ) -> list[dict[str, Any]]:
        print("\n   🔍 步骤 1: 预筛选股票池...")
        filtered_stock_codes = self._pre_filter_stocks(screening_logic, query=query)
        print(f"      预筛选后：{len(filtered_stock_codes)} 只股票")
        if not filtered_stock_codes:
            print("      ⚠️ 预筛选后无股票，请检查筛选条件")
            return []
        print("\n   📊 步骤 2: 计算技术指标并筛选...")
        candidates = self._batch_screen_stocks(
            stock_codes=filtered_stock_codes, screening_logic=screening_logic
        )
        print(f"      成功筛选：{len(candidates)} 只")
        results = sorted(candidates, key=lambda x: x["confidence"], reverse=True)[:top_n]
        return results

    def _pre_filter_stocks(self, screening_logic: dict, query: str = "") -> list[str]:
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

        for tool_step in tools:
            if tool_step.get("tool", "") in _PRE_FILTER_TOOLS:
                _add_tool(tool_step)
        for tool_step in self._auto_detect_pre_filters(screening_logic, query):
            _add_tool(tool_step)

        if not pre_filter_tools:
            print("      未检测到预筛选条件，使用全部股票池")
            return self.all_stock_codes

        print(f"      检测到 {len(pre_filter_tools)} 个预筛选条件:")
        for tool_step in pre_filter_tools:
            print(f"         - {tool_step.get('tool')}({tool_step.get('params', {})})")
        latest_data = self.data.xs(self.latest_date, level="trade_date")
        tool_results: dict[str, list[pd.Series]] = {}
        for tool_step in pre_filter_tools:
            tool_name = tool_step.get("tool")
            params = tool_step.get("params", {})
            try:
                result = execute_tool_impl(
                    tool_name=tool_name, data=latest_data, params=params, computed_vars={}
                )
                tool_results.setdefault(tool_name, []).append(result)
                print(f"         ↳ {tool_name}({params}): 匹配 {result.sum()} 只股票")
            except Exception as e:
                print(f"      ⚠️ 预筛选工具 {tool_name} 执行失败：{e}")
                import traceback
                traceback.print_exc()
        filter_mask = pd.Series(True, index=latest_data.index)
        for tool_name, results in tool_results.items():
            tool_mask = pd.concat(results, axis=1).any(axis=1)
            filter_mask &= tool_mask
            print(f"         ↳ {tool_name} 合计匹配：{tool_mask.sum()} 只股票")
        return latest_data[filter_mask].index.tolist()

    def _auto_detect_pre_filters(self, screening_logic: dict, query: str = "") -> list[dict]:
        detected_tools = []
        available_industries = self._get_available_industries_from_data()
        text_sources = [
            query,
            screening_logic.get("name", ""),
            screening_logic.get("rationale", ""),
            screening_logic.get("expression", ""),
        ]
        combined_text = " ".join(str(t) for t in text_sources if t)
        if not combined_text.strip():
            return detected_tools
        if available_industries:
            sorted_industries = sorted(available_industries, key=len, reverse=True)
            matched_industries = []
            remaining_text = combined_text
            for industry in sorted_industries:
                if industry in remaining_text:
                    matched_industries.append(industry)
                    remaining_text = remaining_text.replace(industry, "")
            for industry in matched_industries:
                detected_tools.append(
                    {"tool": "filter_by_industry", "params": {"industry": industry}, "var": f"is_{industry}"}
                )
        market_keywords = {"主板": "主板", "创业板": "创业板", "科创板": "科创板", "北交所": "北交所"}
        for keyword, market_name in market_keywords.items():
            if keyword in combined_text:
                detected_tools.append(
                    {"tool": "filter_by_market", "params": {"market": market_name}, "var": f"is_{market_name}"}
                )
        if detected_tools:
            print("      🔍 智能检测到预筛选条件:")
            for tool_step in detected_tools:
                print(f"         - {tool_step['tool']}({tool_step['params']})")
        return detected_tools

    def _get_available_industries_from_data(self) -> list[str]:
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

    def _batch_screen_stocks(
        self, stock_codes: list[str], screening_logic: dict
    ) -> list[dict[str, Any]]:
        t_start = _time.time()
        tools = screening_logic.get("tools", [])
        expression = screening_logic.get("expression", "")
        confidence_formula = screening_logic.get("confidence_formula", "1.0")
        rationale = screening_logic.get("rationale", "")
        main_tools = [t for t in tools if t.get("tool") not in _PRE_FILTER_TOOLS]
        pre_filter_vars = {
            t.get("var"): True for t in tools if t.get("tool") in _PRE_FILTER_TOOLS and t.get("var")
        }
        expression_vars = NamespaceBuilder.extract_variables(expression) if expression else set()
        self._print_logic_summary(expression, confidence_formula, main_tools)
        print(f"\n      ⚡ 向量化批量筛选模式 ({len(stock_codes)} 只股票)")
        valid_stocks, valid_data, stats = self._filter_valid_stocks(stock_codes)
        if not valid_stocks:
            self._print_screening_stats(
                len(stock_codes), stats["data_insufficient"], stats["no_latest"], 0, 0, 0, 0, 0, 0
            )
            return []
        namespace, tool_error_count = self._execute_main_tools(
            valid_data, main_tools, pre_filter_vars
        )
        latest_namespace = self._extract_latest_cross_section(namespace, valid_data)
        matched_stocks, eval_stats = self._vectorized_expression_eval(
            expression, expression_vars, latest_namespace, valid_stocks
        )
        candidates = self._build_candidates(
            matched_stocks, confidence_formula, latest_namespace,
            expression_vars, valid_data, valid_stocks, rationale,
        )
        t_elapsed = _time.time() - t_start
        self._print_screening_stats(
            len(stock_codes), stats["data_insufficient"], stats["no_latest"],
            tool_error_count, eval_stats["false_count"], eval_stats["nan_count"],
            eval_stats["eval_error_count"], 0, len(candidates), elapsed=t_elapsed,
        )
        return candidates

    def _filter_valid_stocks(
        self, stock_codes: list[str]
    ) -> tuple[list[str], pd.DataFrame, dict[str, int]]:
        all_ts_codes = self.data.index.get_level_values("ts_code")
        subset_data = self.data[all_ts_codes.isin(stock_codes)]
        if len(subset_data) == 0:
            print("      ⚠️ 子集数据为空")
            return [], subset_data, {"data_insufficient": 0, "no_latest": 0}
        stock_day_counts = subset_data.groupby(level="ts_code").size()
        sufficient_stocks = stock_day_counts[stock_day_counts >= 20].index
        data_insufficient_count = len(stock_day_counts) - len(sufficient_stocks)
        try:
            latest_date_data = subset_data.xs(self.latest_date, level="trade_date")
            stocks_with_latest = set(latest_date_data.index)
        except KeyError:
            print(f"      ⚠️ 数据中不存在分析日期 {self.latest_date}")
            return [], subset_data, {"data_insufficient": data_insufficient_count, "no_latest": 0}
        valid_stocks = [s for s in sufficient_stocks if s in stocks_with_latest]
        no_latest_count = len(sufficient_stocks) - len(valid_stocks)
        print(f"      数据过滤：{len(stock_codes)} → {len(valid_stocks)} 只有效股票")
        if data_insufficient_count > 0:
            print(f"         数据不足 (<20 天): {data_insufficient_count} 只")
        if no_latest_count > 0:
            print(f"         无最新数据：{no_latest_count} 只")
        if not valid_stocks:
            print("      ⚠️ 无有效股票")
            return (
                [], subset_data,
                {"data_insufficient": data_insufficient_count, "no_latest": no_latest_count},
            )
        valid_ts_codes = subset_data.index.get_level_values("ts_code")
        valid_data = subset_data[valid_ts_codes.isin(valid_stocks)]
        return (
            valid_stocks, valid_data,
            {"data_insufficient": data_insufficient_count, "no_latest": no_latest_count},
        )

    def _execute_main_tools(
        self, valid_data: pd.DataFrame, main_tools: list[dict], pre_filter_vars: dict[str, bool]
    ) -> tuple[dict, int]:
        namespace = self.namespace_builder.build_namespace(valid_data)
        namespace.update(pre_filter_vars)
        tool_error_count = 0
        
        print(f"      📦 执行 {len(main_tools)} 个主工具...")
        for i, tool_step in enumerate(main_tools, 1):
            tool_name = tool_step.get("tool")
            params = tool_step.get("params", {})
            var_name = tool_step.get("var")
            if not tool_name or not var_name:
                print(f"         ⚠️ 工具步骤 {i}: 缺少 tool 或 var")
                continue
            
            try:
                result = execute_tool_impl(
                    tool_name=tool_name, data=valid_data, params=params, computed_vars=namespace
                )
                namespace[var_name] = result
                print(f"         [{i}/{len(main_tools)}] ✅ {tool_name} → {var_name}")
            except Exception as e:
                tool_error_count += 1
                print(f"         [{i}/{len(main_tools)}] ❌ {tool_name} → {var_name} 失败：{e}")
                if tool_error_count <= 2:
                    import traceback
                    traceback.print_exc()
                namespace[var_name] = pd.Series(np.nan, index=valid_data.index)
        
        print(f"      ✅ 工具执行完成，成功：{len(main_tools) - tool_error_count}, 失败：{tool_error_count}")
        return namespace, tool_error_count

    def _vectorized_expression_eval(
        self, expression: str, expression_vars: set[str],
        latest_namespace: dict, valid_stocks: list[str],
    ) -> tuple[list[str], dict[str, int]]:
        stats = {"false_count": 0, "nan_count": 0, "eval_error_count": 0}
        stock_index = latest_namespace.get("_stock_index", pd.Index(valid_stocks))
        
        # 确保所有表达式变量都在 namespace 中，缺失的填充 NaN
        for var in expression_vars:
            if var not in latest_namespace:
                latest_namespace[var] = pd.Series(np.nan, index=stock_index)
        
        try:
            var_series = [
                latest_namespace[v] for v in expression_vars
                if v in latest_namespace and isinstance(latest_namespace[v], pd.Series)
            ]
            if var_series:
                nan_mask = (
                    pd.concat(var_series, axis=1).isna().any(axis=1).reindex(stock_index, fill_value=False)
                )
            else:
                nan_mask = pd.Series(False, index=stock_index)
            stats["nan_count"] = int(nan_mask.sum())
            match_result = eval(expression, {"__builtins__": {}}, latest_namespace)
            if isinstance(match_result, pd.Series):
                match_result = match_result.where(~nan_mask, False).fillna(False).astype(bool)
                stats["false_count"] = max(0, int((~match_result).sum()) - stats["nan_count"])
                matched_stocks = match_result[match_result].index.tolist()
            elif isinstance(match_result, (bool, np.bool_)):
                matched_stocks = valid_stocks if match_result else []
                stats["false_count"] = 0 if match_result else len(valid_stocks)
            else:
                matched_stocks = valid_stocks if match_result else []
            if stats["false_count"] > 0 and isinstance(match_result, pd.Series):
                # 只在 debug 模式下输出示例
                if logger.isEnabledFor(10):  # DEBUG level
                    self._debug_print_samples(
                        match_result[match_result].index[:3], expression_vars,
                        latest_namespace, "表达式为 True",
                    )
            if stats["nan_count"] > 0:
                # 只在 debug 模式下输出示例
                if logger.isEnabledFor(10):  # DEBUG level
                    self._debug_print_samples(
                        nan_mask[nan_mask].index[:3], expression_vars,
                        latest_namespace, "变量含 NaN", show_nan_only=True,
                    )
        except Exception as e:
            stats["eval_error_count"] = 1
            print(f"      ⚠️ 向量化表达式评估失败：{e}")
            import traceback
            traceback.print_exc()
            matched_stocks = []
        return matched_stocks, stats

    def _build_candidates(
        self, matched_stocks: list[str], confidence_formula: str, latest_namespace: dict,
        expression_vars: set[str], valid_data: pd.DataFrame, valid_stocks: list[str], rationale: str,
    ) -> list[dict[str, Any]]:
        if not matched_stocks:
            return []
        
        # 提取置信度公式中的变量并确保都存在
        conf_vars = NamespaceBuilder.extract_variables(confidence_formula)
        for var in conf_vars:
            if var not in latest_namespace:
                stock_index = latest_namespace.get("_stock_index", pd.Index(valid_stocks))
                latest_namespace[var] = pd.Series(np.nan, index=stock_index)
        
        try:
            conf_raw = eval(confidence_formula, {"__builtins__": {}}, latest_namespace)
            if isinstance(conf_raw, pd.Series):
                confidence_series = 1.0 / (1.0 + np.exp(-conf_raw))
            elif isinstance(conf_raw, (int, float)):
                confidence_series = pd.Series(
                    1.0 / (1.0 + np.exp(-conf_raw)), index=pd.Index(valid_stocks)
                )
            else:
                confidence_series = pd.Series(0.5, index=pd.Index(valid_stocks))
        except Exception as e:
            print(f"      ⚠️ 置信度批量计算失败：{e}，使用默认值 0.5")
            confidence_series = pd.Series(0.5, index=pd.Index(valid_stocks))
        name_map = self._get_stock_names_batch(valid_data, matched_stocks)
        industry_map = self._get_stock_industries_batch(valid_data, matched_stocks)
        metrics_dict: dict[str, pd.Series] = {}
        for var in expression_vars:
            val = latest_namespace.get(var)
            if isinstance(val, pd.Series):
                metrics_dict[var] = val
            elif isinstance(val, (int, float, np.number)):
                metrics_dict[var] = pd.Series(float(val), index=pd.Index(matched_stocks))
        metrics_df = pd.DataFrame(metrics_dict).reindex(matched_stocks) if metrics_dict else pd.DataFrame(index=matched_stocks)
        candidates = []
        for ts_code in matched_stocks:
            try:
                conf = float(confidence_series.loc[ts_code]) if ts_code in confidence_series.index else 0.5
            except (KeyError, TypeError):
                conf = 0.5
            if pd.isna(conf):
                conf = 0.5
            metrics = {}
            if ts_code in metrics_df.index:
                row = metrics_df.loc[ts_code]
                metrics = {k: float(v) for k, v in row.items() if pd.notna(v) and isinstance(v, (int, float, np.number))}
            candidates.append({
                "ts_code": ts_code, "name": name_map.get(ts_code, ts_code),
                "industry": industry_map.get(ts_code, "N/A"),
                "confidence": conf, "reason": rationale, "metrics": metrics,
            })
        return candidates

    def _extract_latest_cross_section(self, namespace: dict, valid_data: pd.DataFrame) -> dict:
        latest_namespace = {}
        try:
            latest_slice = valid_data.xs(self.latest_date, level="trade_date")
            stock_index = latest_slice.index
        except KeyError:
            return latest_namespace
        latest_namespace["_stock_index"] = stock_index
        for key, value in namespace.items():
            if isinstance(value, pd.Series):
                if isinstance(value.index, pd.MultiIndex):
                    try:
                        cross_section = value.xs(self.latest_date, level="trade_date")
                        latest_namespace[key] = cross_section.reindex(stock_index)
                    except KeyError:
                        latest_namespace[key] = pd.Series(np.nan, index=stock_index)
                elif value.index.equals(valid_data.index):
                    try:
                        mask = valid_data.index.get_level_values("trade_date") == self.latest_date
                        sliced = value[mask]
                        sliced.index = stock_index
                        latest_namespace[key] = sliced
                    except Exception:
                        latest_namespace[key] = pd.Series(np.nan, index=stock_index)
                else:
                    latest_namespace[key] = value.reindex(stock_index) if hasattr(value, "reindex") else value
            elif callable(value):
                latest_namespace[key] = value
            else:
                latest_namespace[key] = value
        return latest_namespace

    @staticmethod
    def _get_stock_names_batch(data: pd.DataFrame, stock_codes: list[str]) -> dict[str, str]:
        if "name" not in data.columns:
            return {code: code for code in stock_codes}
        try:
            names = data.groupby(level="ts_code")["name"].first()
            return {code: str(names.loc[code]) if code in names.index else code for code in stock_codes}
        except Exception:
            return {code: code for code in stock_codes}
    
    @staticmethod
    def _get_stock_industries_batch(data: pd.DataFrame, stock_codes: list[str]) -> dict[str, str]:
        """批量获取股票行业信息"""
        if "industry" not in data.columns:
            return {code: "N/A" for code in stock_codes}
        try:
            industries = data.groupby(level="ts_code")["industry"].first()
            return {code: str(industries.loc[code]) if code in industries.index and pd.notna(industries.loc[code]) else "N/A" for code in stock_codes}
        except Exception:
            return {code: "N/A" for code in stock_codes}

    @staticmethod
    def _debug_print_samples(sample_codes, expression_vars: set[str], latest_namespace: dict, label: str, show_nan_only: bool = False):
        for ts_code in sample_codes:
            print(f"\n      🔍 调试 [{ts_code}] {label}:")
            for var_name in expression_vars:
                val = latest_namespace.get(var_name)
                if isinstance(val, pd.Series) and ts_code in val.index:
                    v = val.loc[ts_code]
                    if show_nan_only:
                        try:
                            if pd.isna(v):
                                print(f"         {var_name} = NaN")
                        except (TypeError, ValueError):
                            pass
                    elif isinstance(v, (int, float, np.number, bool, np.bool_)):
                        print(f"         {var_name} = {v}")

    @staticmethod
    def _print_logic_summary(expression: str, confidence_formula: str, main_tools: list[dict]):
        print("\n      📋 筛选逻辑:")
        print(f"         表达式：{expression}")
        print(f"         置信度：{confidence_formula}")
        if main_tools:
            print("         工具步骤:")
            for t in main_tools:
                print(f"            {t.get('var')} = {t.get('tool')}({t.get('params', {})})")

    @staticmethod
    def _print_screening_stats(
        total: int, data_insufficient: int, no_latest: int, tool_error: int,
        expr_false: int, expr_nan: int, expr_eval_error: int, other_error: int, success: int,
        elapsed: float = 0.0,
    ):
        print("\n      📊 筛选统计:")
        print(f"         候选股票数：{total}")
        if data_insufficient > 0:
            print(f"         数据不足 (<20 天): {data_insufficient} 只")
        if no_latest > 0:
            print(f"         无最新数据：{no_latest} 只")
        if tool_error > 0:
            print(f"         工具执行失败：{tool_error} 个")
        print(f"         表达式为 False: {expr_false} 只")
        if expr_nan > 0:
            print(f"         表达式为 NaN: {expr_nan} 只")
        if expr_eval_error > 0:
            print(f"         表达式评估错误：{expr_eval_error} 只")
        if other_error > 0:
            print(f"         其他错误：{other_error} 只")
        print(f"         ✅ 成功匹配：{success} 只")
        if elapsed > 0:
            print(f"         ⏱️ 耗时：{elapsed:.2f}s")


def create_stock_screener(
    data: pd.DataFrame, holding_periods: list[int] | None = None
) -> StockScreener:
    """创建股票筛选器实例的便捷函数"""
    return StockScreener(data, holding_periods=holding_periods)
