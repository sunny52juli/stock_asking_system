"""批量计算引擎 - 向量化执行技术指标计算和表达式评估."""

from __future__ import annotations

import re
import time as _time
from datetime import datetime
from typing import Any
import polars as pl
import math

from infrastructure.logging.logger import get_logger
from src.screening.expression_evaluator import ExpressionEvaluator
from src.screening.mcp_tool_runner import ToolExecutor
from src.screening.namespace_builder import NamespaceBuilder
logger = get_logger(__name__)


class NamespaceBuilder:
    """命名空间构建器 - 管理工具计算的中间变量."""

    @staticmethod
    def build_namespace(data: pl.DataFrame) -> dict:
        """从数据构建初始命名空间."""
        namespace = {}
        # 添加基础数据列（polars Series）
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

    def __init__(self, data: pl.DataFrame, latest_date: str, index_data: pl.DataFrame | None = None):
        """初始化批量计算器.
        
        Args:
            data: 市场数据 DataFrame (columns: ts_code, trade_date, ...)
            latest_date: 最新交易日 (YYYYMMDD 字符串)
            index_data: 指数数据 DataFrame (columns: trade_date, index_close)，可选
        """
        self.data = data
        self.latest_date = latest_date
        self.index_data = index_data
        self.namespace_builder = NamespaceBuilder()
        self.tool_executor = ToolExecutor(index_data=index_data)

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
        
        main_tools = tools
        pre_filter_vars = {}
        
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
        namespace, tool_error_count = self.tool_executor.execute_tools(
            valid_data, main_tools, pre_filter_vars
        )
        
        # 提取最新截面数据
        latest_namespace = self._extract_latest_cross_section(namespace, valid_data)
        
        # 向量化表达式评估
        matched_stocks, eval_stats = ExpressionEvaluator.evaluate_expression(
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
    ) -> tuple[list[str], pl.DataFrame, dict[str, int]]:
        """过滤出有效股票（有足够数据且包含最新日期）."""
        # Polars: 使用 filter 和 is_in
        subset_data = self.data.filter(pl.col("ts_code").is_in(stock_codes))
        
        if subset_data.is_empty():
            logger.warning("   ⚠️ 子集数据为空")
            return [], subset_data, {"data_insufficient": 0, "no_latest": 0}
        
        # 检查数据充足性：每只股票的交易天数 >= 20
        stock_day_counts = subset_data.group_by("ts_code").agg(
            pl.count().alias("day_count")
        )
        sufficient_stocks_df = stock_day_counts.filter(pl.col("day_count") >= 20)
        sufficient_stocks = sufficient_stocks_df["ts_code"].to_list()
        data_insufficient_count = len(stock_day_counts) - len(sufficient_stocks)
        
        # 检查是否包含最新日期
        # Polars: trade_date 可能是 date/datetime 类型，需要转换后比较
        latest_date_str = str(self.latest_date)
        
        # 统一日期格式：提取 YYYYMMDD 部分
        # 可能的格式："2026-04-17 00:00:00", "20260417", "2026-04-17"
        date_match = re.search(r'(\d{4})[-/]?(\d{2})[-/]?(\d{2})', latest_date_str)
        if date_match:
            normalized_date = f"{date_match.group(1)}{date_match.group(2)}{date_match.group(3)}"
        else:
            normalized_date = latest_date_str
        
        if subset_data.schema["trade_date"] in [pl.Date, pl.Datetime]:
            # 将字符串转换为日期后比较
            try:
                latest_date_val = datetime.strptime(normalized_date, "%Y%m%d").date()
                latest_date_data = subset_data.filter(pl.col("trade_date") == latest_date_val)
            except Exception as e:
                logger.warning(f"   ⚠️ 日期转换失败：{e}，尝试直接比较")
                latest_date_data = subset_data.filter(pl.col("trade_date") == normalized_date)
        else:
            # trade_date 已经是字符串或整数
            latest_date_data = subset_data.filter(pl.col("trade_date") == normalized_date)
        if latest_date_data.is_empty():
            logger.error(f"   ⚠️ 数据中不存在分析日期 {self.latest_date}")
            return [], subset_data, {
                "data_insufficient": data_insufficient_count,
                "no_latest": 0
            }
        
        stocks_with_latest = set(latest_date_data["ts_code"].to_list())
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
        
        # 过滤出有效股票的数据
        valid_data = subset_data.filter(pl.col("ts_code").is_in(valid_stocks))
        
        return (
            valid_stocks,
            valid_data,
            {
                "data_insufficient": data_insufficient_count,
                "no_latest": no_latest_count
            },
        )

    def _build_candidates(
        self,
        matched_stocks: list[str],
        confidence_formula: str,
        latest_namespace: dict,
        expression_vars: set[str],
        valid_data: pl.DataFrame,
        valid_stocks: list[str],
        rationale: str,
    ) -> list[dict[str, Any]]:
        """构建候选股票列表."""
        if not matched_stocks:
            return []
        
        # 计算置信度
        confidence_values = ExpressionEvaluator.calculate_confidence(
            confidence_formula, latest_namespace, valid_stocks
        )
        
        # 批量获取股票名称和行业
        name_map = self._get_stock_names_batch(valid_data, matched_stocks)
        industry_map = self._get_stock_industries_batch(valid_data, matched_stocks)
        
        # 提取指标数据
        metrics_dict: dict[str, list[float]] = {}
        for var in expression_vars:
            val = latest_namespace.get(var)
            if isinstance(val, pl.Series):
                # 只取 matched_stocks 对应的值
                metrics_dict[var] = val.to_list()
            elif isinstance(val, (int, float)):
                metrics_dict[var] = [float(val)] * len(matched_stocks)
        
        # 构建候选列表
        candidates = []
        for idx, ts_code in enumerate(matched_stocks):
            conf = confidence_values[idx] if idx < len(confidence_values) else 0.5
            
            # 使用 math.isnan 检查 NaN
            if isinstance(conf, float) and math.isnan(conf):
                conf = 0.5
            
            # 提取该股票的指标
            metrics = {}
            for var, values in metrics_dict.items():
                if idx < len(values):
                    val = values[idx]
                    # 只添加非 NaN 值
                    if isinstance(val, float) and not math.isnan(val):
                        metrics[var] = float(val)
                    elif not isinstance(val, float):
                        metrics[var] = float(val)
            
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
        self, namespace: dict, valid_data: pl.DataFrame
    ) -> dict:
        """提取最新日期的截面数据."""
        latest_namespace = {}
        
        # 过滤最新日期的数据
        latest_date_str = str(self.latest_date)
        
        # 统一日期格式：提取 YYYYMMDD 部分
        date_match = re.search(r'(\d{4})[-/]?(\d{2})[-/]?(\d{2})', latest_date_str)
        if date_match:
            normalized_date = f"{date_match.group(1)}{date_match.group(2)}{date_match.group(3)}"
        else:
            normalized_date = latest_date_str
        
        if valid_data.schema["trade_date"] in [pl.Date, pl.Datetime]:
            # 将字符串转换为日期后比较
            try:
                latest_date_val = datetime.strptime(normalized_date, "%Y%m%d").date()
                latest_slice = valid_data.filter(pl.col("trade_date") == latest_date_val)
            except Exception:
                latest_slice = valid_data.filter(pl.col("trade_date") == normalized_date)
        else:
            latest_slice = valid_data.filter(pl.col("trade_date") == normalized_date)
        
        if latest_slice.is_empty():
            logger.warning(f"   ⚠️ 无法找到最新日期 {normalized_date} 的数据")
            return latest_namespace
        
        stock_index = latest_slice["ts_code"].to_list()
        latest_namespace["_stock_index"] = stock_index
        
        for key, value in namespace.items():
            # 跳过函数对象
            if callable(value):
                continue
            
            if isinstance(value, pl.DataFrame):
                # Polars DataFrame: 提取最新日期的列
                if "trade_date" in value.columns and "ts_code" in value.columns:
                    # 有时间序列数据：过滤最新日期（使用标准化后的日期）
                    if value.schema["trade_date"] in [pl.Date, pl.Datetime]:
                        try:
                            latest_date_val = datetime.strptime(normalized_date, "%Y%m%d").date()
                            latest_mask = value["trade_date"] == latest_date_val
                        except Exception:
                            latest_mask = value["trade_date"] == normalized_date
                    else:
                        latest_mask = value["trade_date"] == normalized_date
                    
                    latest_df = value.filter(latest_mask)
                    
                    # 提取所有非索引列作为 Series（使用原始列名）
                    for col in latest_df.columns:
                        if col not in ["trade_date", "ts_code"]:
                            latest_namespace[col] = latest_df[col]
                elif "ts_code" in value.columns and "trade_date" not in value.columns:
                    # 已经是截面数据（如 beta, alpha 等聚合指标），直接使用
                    # 这类 DataFrame 只有 ts_code 和计算结果列
                    for col in value.columns:
                        if col != "ts_code":
                            latest_namespace[col] = value[col]
                else:
                    # 既没有 trade_date 也没有 ts_code，跳过
                    logger.warning(f"   ⚠️ DataFrame {key} 缺少必要列 (ts_code)，跳过")
            
            elif isinstance(value, pl.Series):
                # Polars Series: 需要与 valid_data 对齐
                if len(value) == len(valid_data):
                    # 假设 value 的顺序与 valid_data 一致
                    mask = valid_data["trade_date"] == normalized_date
                    sliced = value.filter(mask)
                    latest_namespace[key] = sliced
                else:
                    # 直接使用该 Series
                    logger.warning(f"   ⚠️ Series {key} 长度不匹配: {len(value)} vs {len(valid_data)}")
                    latest_namespace[key] = value
            else:
                latest_namespace[key] = value
        
        return latest_namespace

    @staticmethod
    def _get_stock_names_batch(
        data: pl.DataFrame, stock_codes: list[str]
    ) -> dict[str, str]:
        """批量获取股票名称."""
        if "name" not in data.columns:
            return {code: code for code in stock_codes}
        
        try:
            # Polars: group_by 并取第一个 name
            names_df = data.group_by("ts_code").agg(pl.col("name").first())
            names_dict = dict(zip(names_df["ts_code"], names_df["name"]))
            return {
                code: str(names_dict[code]) if code in names_dict else code
                for code in stock_codes
            }
        except Exception:
            return {code: code for code in stock_codes}
    
    @staticmethod
    def _get_stock_industries_batch(
        data: pl.DataFrame, stock_codes: list[str]
    ) -> dict[str, str]:
        """批量获取股票行业信息."""
        if "industry" not in data.columns:
            return {code: "N/A" for code in stock_codes}
        
        try:
            # Polars: group_by 并取第一个 industry
            industries_df = data.group_by("ts_code").agg(pl.col("industry").first())
            industries_dict = dict(zip(industries_df["ts_code"], industries_df["industry"]))
            return {
                code: (
                    str(industries_dict[code])
                    if code in industries_dict and industries_dict[code] is not None
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
