"""批量计算引擎 - 向量化执行技术指标计算和表达式评估."""

from __future__ import annotations

import time as _time
from typing import Any

import numpy as np
import pandas as pd

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class NamespaceBuilder:
    """命名空间构建器 - 管理工具计算的中间变量."""

    @staticmethod
    def build_namespace(data: pd.DataFrame) -> dict:
        """从数据构建初始命名空间."""
        namespace = {}
        # 添加基础数据列
        for col in data.columns:
            namespace[col] = data[col]
        return namespace

    @staticmethod
    def extract_variables(expression: str) -> set[str]:
        """从表达式中提取变量名.
        
        Args:
            expression: Python 表达式字符串
            
        Returns:
            变量名集合
        """
        import ast
        import re
        
        # 简单提取：匹配标识符
        identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', expression)
        
        # 过滤掉 Python 关键字和内置函数
        keywords = {
            'True', 'False', 'None', 'and', 'or', 'not', 'if', 'else',
            'for', 'while', 'in', 'is', 'lambda', 'def', 'class', 'return'
        }
        builtins = {'abs', 'max', 'min', 'sum', 'len', 'int', 'float', 'str'}
        
        return set(identifiers) - keywords - builtins


class BatchCalculator:
    """批量计算器 - 负责向量化执行筛选逻辑.
    
    核心功能:
    1. 过滤有效股票（数据充足性检查）
    2. 执行主工具列表（技术指标计算）
    3. 向量化表达式评估
    4. 置信度计算和结果构建
    """

    def __init__(self, data: pd.DataFrame, latest_date: pd.Timestamp):
        """初始化批量计算器.
        
        Args:
            data: 市场数据 DataFrame
            latest_date: 最新交易日
        """
        self.data = data
        self.latest_date = latest_date
        self.namespace_builder = NamespaceBuilder()

    def batch_screen(
        self,
        stock_codes: list[str],
        screening_logic: dict,
    ) -> list[dict[str, Any]]:
        """执行批量筛选.
        
        Args:
            stock_codes: 股票代码列表
            screening_logic: 筛选逻辑配置
            
        Returns:
            候选股票列表
        """
        t_start = _time.time()
        
        tools = screening_logic.get("tools", [])
        expression = screening_logic.get("expression", "")
        confidence_formula = screening_logic.get("confidence_formula", "1.0")
        rationale = screening_logic.get("rationale", "")
        
        from src.screening.prefilter import PRE_FILTER_TOOLS
        main_tools = [t for t in tools if t.get("tool") not in PRE_FILTER_TOOLS]
        pre_filter_vars = {
            t.get("var"): True
            for t in tools
            if t.get("tool") in PRE_FILTER_TOOLS and t.get("var")
        }
        
        expression_vars = NamespaceBuilder.extract_variables(expression) if expression else set()
        
        self._print_logic_summary(expression, confidence_formula, main_tools)
        logger.info(f"\n   ⚡ 向量化批量筛选模式 ({len(stock_codes)} 只股票)")
        
        # 过滤有效股票
        valid_stocks, valid_data, stats = self._filter_valid_stocks(stock_codes)
        if not valid_stocks:
            self._print_screening_stats(
                len(stock_codes),
                stats["data_insufficient"],
                stats["no_latest"],
                0, 0, 0, 0, 0, 0
            )
            return []
        
        # 执行主工具
        namespace, tool_error_count = self._execute_main_tools(
            valid_data, main_tools, pre_filter_vars
        )
        
        # 提取最新截面数据
        latest_namespace = self._extract_latest_cross_section(namespace, valid_data)
        
        # 向量化表达式评估
        matched_stocks, eval_stats = self._vectorized_expression_eval(
            expression, expression_vars, latest_namespace, valid_stocks
        )
        
        # 构建候选结果
        candidates = self._build_candidates(
            matched_stocks, confidence_formula, latest_namespace,
            expression_vars, valid_data, valid_stocks, rationale,
        )
        
        t_elapsed = _time.time() - t_start
        self._print_screening_stats(
            len(stock_codes),
            stats["data_insufficient"],
            stats["no_latest"],
            tool_error_count,
            eval_stats["false_count"],
            eval_stats["nan_count"],
            eval_stats["eval_error_count"],
            0,
            len(candidates),
            elapsed=t_elapsed,
        )
        
        return candidates

    def _filter_valid_stocks(
        self, stock_codes: list[str]
    ) -> tuple[list[str], pd.DataFrame, dict[str, int]]:
        """过滤出有效股票（有足够数据且包含最新日期）."""
        all_ts_codes = self.data.index.get_level_values("ts_code")
        subset_data = self.data[all_ts_codes.isin(stock_codes)]
        
        if len(subset_data) == 0:
            logger.warning("   ⚠️ 子集数据为空")
            return [], subset_data, {"data_insufficient": 0, "no_latest": 0}
        
        # 检查数据充足性
        stock_day_counts = subset_data.groupby(level="ts_code").size()
        sufficient_stocks = stock_day_counts[stock_day_counts >= 20].index
        data_insufficient_count = len(stock_day_counts) - len(sufficient_stocks)
        
        # 检查是否包含最新日期
        try:
            latest_date_data = subset_data.xs(self.latest_date, level="trade_date")
            stocks_with_latest = set(latest_date_data.index)
        except KeyError:
            logger.error(f"   ⚠️ 数据中不存在分析日期 {self.latest_date}")
            return [], subset_data, {
                "data_insufficient": data_insufficient_count,
                "no_latest": 0
            }
        
        valid_stocks = [s for s in sufficient_stocks if s in stocks_with_latest]
        no_latest_count = len(sufficient_stocks) - len(valid_stocks)
        
        logger.info(f"   数据过滤：{len(stock_codes)} → {len(valid_stocks)} 只有效股票")
        if data_insufficient_count > 0:
            logger.info(f"      数据不足 (<20 天): {data_insufficient_count} 只")
        if no_latest_count > 0:
            logger.info(f"      无最新数据：{no_latest_count} 只")
        
        if not valid_stocks:
            logger.warning("   ⚠️ 无有效股票")
            return (
                [],
                subset_data,
                {
                    "data_insufficient": data_insufficient_count,
                    "no_latest": no_latest_count
                },
            )
        
        valid_ts_codes = subset_data.index.get_level_values("ts_code")
        valid_data = subset_data[valid_ts_codes.isin(valid_stocks)]
        
        return (
            valid_stocks,
            valid_data,
            {
                "data_insufficient": data_insufficient_count,
                "no_latest": no_latest_count
            },
        )

    def _execute_main_tools(
        self,
        valid_data: pd.DataFrame,
        main_tools: list[dict],
        pre_filter_vars: dict[str, bool]
    ) -> tuple[dict, int]:
        """执行主工具列表."""
        from src.agent.tools.bridge import execute_tool_impl
        
        namespace = self.namespace_builder.build_namespace(valid_data)
        namespace.update(pre_filter_vars)
        tool_error_count = 0
        
        logger.info(f"   📦 执行 {len(main_tools)} 个主工具...")
        for i, tool_step in enumerate(main_tools, 1):
            tool_name = tool_step.get("name") or tool_step.get("tool")
            params = tool_step.get("params", {})
            var_name = tool_step.get("var")
            
            if not tool_name or not var_name:
                logger.warning(f"      ⚠️ 工具步骤 {i}: 缺少必要字段")
                continue
            
            try:
                result = execute_tool_impl(
                    tool_name=tool_name,
                    data=valid_data,
                    params=params,
                    computed_vars=namespace
                )
                namespace[var_name] = result
                logger.info(f"      [{i}/{len(main_tools)}] ✅ {tool_name} → {var_name}")
            except Exception as e:
                tool_error_count += 1
                logger.error(f"      [{i}/{len(main_tools)}] ❌ {tool_name} → {var_name} 失败：{e}")
                namespace[var_name] = pd.Series(np.nan, index=valid_data.index)
        
        logger.info(
            f"   ✅ 工具执行完成，成功：{len(main_tools) - tool_error_count}, "
            f"失败：{tool_error_count}"
        )
        return namespace, tool_error_count

    def _vectorized_expression_eval(
        self,
        expression: str,
        expression_vars: set[str],
        latest_namespace: dict,
        valid_stocks: list[str],
    ) -> tuple[list[str], dict[str, int]]:
        """向量化评估筛选表达式."""
        stats = {
            "false_count": 0,
            "nan_count": 0,
            "eval_error_count": 0
        }
        stock_index = latest_namespace.get("_stock_index", pd.Index(valid_stocks))
        
        if not expression or not expression.strip():
            logger.warning(f"   ⚠️ 表达式为空，返回全部股票")
            return valid_stocks, stats
        
        # 确保所有表达式变量都在 namespace 中
        for var in expression_vars:
            if var not in latest_namespace:
                latest_namespace[var] = pd.Series(np.nan, index=stock_index)
        
        try:
            var_series = [
                latest_namespace[v]
                for v in expression_vars
                if v in latest_namespace and isinstance(latest_namespace[v], pd.Series)
            ]
            
            if var_series:
                nan_mask = (
                    pd.concat(var_series, axis=1)
                    .isna()
                    .any(axis=1)
                    .reindex(stock_index, fill_value=False)
                )
            else:
                nan_mask = pd.Series(False, index=stock_index)
            
            stats["nan_count"] = int(nan_mask.sum())
            
            # 评估表达式
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
            
        except Exception as e:
            stats["eval_error_count"] = 1
            logger.error(f"   ⚠️ 向量化表达式评估失败：{e}")
            matched_stocks = []
        
        return matched_stocks, stats

    def _build_candidates(
        self,
        matched_stocks: list[str],
        confidence_formula: str,
        latest_namespace: dict,
        expression_vars: set[str],
        valid_data: pd.DataFrame,
        valid_stocks: list[str],
        rationale: str,
    ) -> list[dict[str, Any]]:
        """构建候选股票列表."""
        if not matched_stocks:
            return []
        
        # 计算置信度
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
                    1.0 / (1.0 + np.exp(-conf_raw)),
                    index=pd.Index(valid_stocks)
                )
            else:
                confidence_series = pd.Series(0.5, index=pd.Index(valid_stocks))
        except Exception as e:
            logger.warning(f"   ⚠️ 置信度批量计算失败：{e}，使用默认值 0.5")
            confidence_series = pd.Series(0.5, index=pd.Index(valid_stocks))
        
        # 批量获取股票名称和行业
        name_map = self._get_stock_names_batch(valid_data, matched_stocks)
        industry_map = self._get_stock_industries_batch(valid_data, matched_stocks)
        
        # 提取指标数据
        metrics_dict: dict[str, pd.Series] = {}
        for var in expression_vars:
            val = latest_namespace.get(var)
            if isinstance(val, pd.Series):
                metrics_dict[var] = val
            elif isinstance(val, (int, float, np.number)):
                metrics_dict[var] = pd.Series(float(val), index=pd.Index(matched_stocks))
        
        metrics_df = (
            pd.DataFrame(metrics_dict).reindex(matched_stocks)
            if metrics_dict
            else pd.DataFrame(index=matched_stocks)
        )
        
        # 构建候选列表
        candidates = []
        for ts_code in matched_stocks:
            try:
                conf = (
                    float(confidence_series.loc[ts_code])
                    if ts_code in confidence_series.index
                    else 0.5
                )
            except (KeyError, TypeError):
                conf = 0.5
            
            if pd.isna(conf):
                conf = 0.5
            
            # 提取该股票的指标
            metrics = {}
            if ts_code in metrics_df.index:
                row = metrics_df.loc[ts_code]
                metrics = {
                    k: float(v)
                    for k, v in row.items()
                    if pd.notna(v) and isinstance(v, (int, float, np.number))
                }
            
            candidates.append({
                "ts_code": ts_code,
                "name": name_map.get(ts_code, ts_code),
                "industry": industry_map.get(ts_code, "N/A"),
                "confidence": conf,
                "reason": rationale,
                "metrics": metrics,
            })
        
        return candidates

    def _extract_latest_cross_section(
        self, namespace: dict, valid_data: pd.DataFrame
    ) -> dict:
        """提取最新日期的截面数据."""
        latest_namespace = {}
        try:
            latest_slice = valid_data.xs(self.latest_date, level="trade_date")
            stock_index = latest_slice.index
        except KeyError:
            return latest_namespace
        
        latest_namespace["_stock_index"] = stock_index
        
        for key, value in namespace.items():
            # 跳过函数对象
            if callable(value):
                continue
            
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
                    latest_namespace[key] = (
                        value.reindex(stock_index)
                        if hasattr(value, "reindex")
                        else value
                    )
            else:
                latest_namespace[key] = value
        
        return latest_namespace

    @staticmethod
    def _get_stock_names_batch(
        data: pd.DataFrame, stock_codes: list[str]
    ) -> dict[str, str]:
        """批量获取股票名称."""
        if "name" not in data.columns:
            return {code: code for code in stock_codes}
        
        try:
            names = data.groupby(level="ts_code")["name"].first()
            return {
                code: str(names.loc[code]) if code in names.index else code
                for code in stock_codes
            }
        except Exception:
            return {code: code for code in stock_codes}
    
    @staticmethod
    def _get_stock_industries_batch(
        data: pd.DataFrame, stock_codes: list[str]
    ) -> dict[str, str]:
        """批量获取股票行业信息."""
        if "industry" not in data.columns:
            return {code: "N/A" for code in stock_codes}
        
        try:
            industries = data.groupby(level="ts_code")["industry"].first()
            return {
                code: (
                    str(industries.loc[code])
                    if code in industries.index and pd.notna(industries.loc[code])
                    else "N/A"
                )
                for code in stock_codes
            }
        except Exception:
            return {code: "N/A" for code in stock_codes}

    @staticmethod
    def _print_logic_summary(
        expression: str, confidence_formula: str, main_tools: list[dict]
    ):
        """打印筛选逻辑摘要."""
        logger.info("\n   📋 筛选逻辑:")
        logger.info(f"      表达式：{expression}")
        logger.info(f"      置信度：{confidence_formula}")
        if main_tools:
            logger.info("      工具步骤:")
            for t in main_tools:
                logger.info(f"         {t.get('var')} = {t.get('tool')}({t.get('params', {})})")

    @staticmethod
    def _print_screening_stats(
        total: int,
        data_insufficient: int,
        no_latest: int,
        tool_error: int,
        expr_false: int,
        expr_nan: int,
        expr_eval_error: int,
        other_error: int,
        success: int,
        elapsed: float = 0.0,
    ):
        """打印筛选统计信息."""
        logger.info("\n   📊 筛选统计:")
        logger.info(f"      候选股票数：{total}")
        if data_insufficient > 0:
            logger.info(f"      数据不足 (<20 天): {data_insufficient} 只")
        if no_latest > 0:
            logger.info(f"      无最新数据：{no_latest} 只")
        if tool_error > 0:
            logger.info(f"      工具执行失败：{tool_error} 个")
        logger.info(f"      表达式为 False: {expr_false} 只")
        if expr_nan > 0:
            logger.info(f"      表达式为 NaN: {expr_nan} 只")
        if expr_eval_error > 0:
            logger.info(f"      表达式评估错误：{expr_eval_error} 只")
        if other_error > 0:
            logger.info(f"      其他错误：{other_error} 只")
        logger.info(f"      ✅ 成功匹配：{success} 只")
        if elapsed > 0:
            logger.info(f"      ⏱️ 耗时：{elapsed:.2f}s")
