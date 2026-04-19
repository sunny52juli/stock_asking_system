"""筛选执行器 - 执行股票筛选并返回结果."""

from __future__ import annotations

import json
import logging

from infrastructure.errors.exceptions import DataLoadError
from utils.screening.stock_screener import StockScreener
from .logic_validator import validate_screening_logic
from .tool_executor import execute_tool_impl

from src.agent.services.index_loader import load_and_merge_index_data
logger = logging.getLogger(__name__)

# 全局调用计数器（用于跟踪 Agent 重试）
_run_screening_call_count = 0

# 全局最后一次筛选结果（用于可靠地获取 candidates）
_last_screening_result: dict | None = None


def create_run_screening(
    data_fn,
    scripts_dir: str,
    stock_codes: list[str] | None = None,
):
    """创建 run_screening 桥接工具.

    Args:
        data_fn: 返回当前数据 DataFrame 的函数
        scripts_dir: 脚本输出目录
        stock_codes: 预筛选后的股票代码列表（可选）

    Returns:
        run_screening 函数
    """

    def run_screening(screening_logic_json: str, top_n: int = 20) -> str:
        """执行股票筛选."""
        global _run_screening_call_count, _last_screening_result
        _run_screening_call_count += 1
        call_iteration = _run_screening_call_count
        
        # 解析 JSON
        screening_logic = json.loads(screening_logic_json)
        
        # 校验 screening_logic 结构
        validation_error = validate_screening_logic(screening_logic)
        if validation_error:
            # 返回结构化错误信息，帮助 Agent 理解并修正
            error_result = {
                "status": "validation_failed",
                "error_type": "screening_logic_validation_error",
                "error_message": str(validation_error),  # 确保是字符串
                "guidance": {
                    "problem": "筛选逻辑验证失败，请根据以下建议修正",
                    "common_issues": [
                        "1. 表达式中使用了未定义的变量 → 在 tools 中添加对应的变量定义",
                        "2. 表达式中直接调用了工具函数（如 rolling_mean(close, 20)） → 先在 tools 中定义变量，然后在 expression 中使用变量名",
                        "3. 使用了硬编码的绝对阈值（如 volatility < 0.03） → 使用相对指标（如 volatility < volatility_ma60 或 volatility_rank < 0.3）",
                    ],
                    "note": "指数相关指标（beta、outperform_rate、alpha、tracking_error、information_ratio、correlation_with_index）可以使用具体数值，因为它们有明确的金融含义。"
                },
                "current_logic": {
                    "expression": screening_logic.get("expression", ""),
                    "defined_variables": [tool.get("var") for tool in screening_logic.get("tools", [])],
                },
            }
            return json.dumps(error_result, ensure_ascii=False, default=str)

        data = data_fn()
        
        # 支持两种返回格式：DataFrame 或 (DataFrame, index_data)
        index_data = None
        if isinstance(data, tuple) and len(data) == 2:
            data, index_data = data
            # Polars: is_empty() 代替 .empty
            index_is_empty = (hasattr(index_data, 'is_empty') and index_data.is_empty()) or (hasattr(index_data, 'empty') and index_data.empty)
            if index_data is not None and not index_is_empty:
                logger.info(f"📊 接收到独立的指数数据: {len(index_data)} 条记录")
            else:
                index_data = None
        
        # Polars: is_empty() 代替 .empty
        data_is_empty = (hasattr(data, 'is_empty') and data.is_empty()) or (hasattr(data, 'empty') and data.empty)
        if data is None or data_is_empty:
            raise ValueError("No data available")
        
        # 检查是否需要指数数据（如果 tools_definition 或 tools 中包含指数相关工具）
        tools_def = screening_logic.get("tools_definition", []) or screening_logic.get("tools", [])
        index_tools = {'beta', 'alpha', 'outperform_rate', 'correlation_with_index', 'tracking_error', 'information_ratio'}
        
        # 兼容两种格式：{"name": "beta"} 和 {"tool": "beta"}
        needs_index_data = False
        for tool in tools_def:
            tool_name = tool.get('name') or tool.get('tool')
            if tool_name in index_tools:
                needs_index_data = True
                break
        
        # 仅在需要指数数据且尚未提供时才加载
        if needs_index_data and index_data is None:
            logger.info("📊 检测到指数相关性工具，自动加载指数数据...")
            data = load_and_merge_index_data(data, stock_codes)
        elif needs_index_data and index_data is not None:
            logger.info(f"📊 使用已提供的指数数据，跳过重复加载")

        screener = StockScreener(data, stock_codes=stock_codes, index_data=index_data)
        
        # 限制最大迭代次数，避免 Agent 无限重试
        max_internal_iterations = 3
        if call_iteration > max_internal_iterations:
            logger.warning(f"⚠️ 已达到最大内部迭代次数 ({max_internal_iterations})，停止重试")
            logger.warning(f"   原因：连续 {call_iteration} 次筛选未能找到合适股票")
            logger.warning(f"   建议：大幅放宽筛选条件或更换策略方向")
            return json.dumps({
                "status": "failed",
                "message": f"已达到最大迭代次数限制 ({max_internal_iterations})，无法找到符合条件的股票。请大幅放宽条件或更换策略。",
                "candidates": [],
                "count": 0,
                "iteration_limit_reached": True,
            }, ensure_ascii=False, default=str)
        
        candidates = screener.execute_screening(
            screening_logic=screening_logic,
            top_n=top_n,
            query=screening_logic.get("name", ""),
            iteration=call_iteration,
        )

        result = {
            "status": "success",
            "screening_logic": screening_logic,
            "candidates": candidates,
            "count": len(candidates),
        }
        
        # 保存到最后一次筛选结果（供外部可靠获取）
        _last_screening_result = result

        return json.dumps(result, ensure_ascii=False, default=str)

    return run_screening


def get_last_screening_result() -> dict | None:
    """获取最后一次筛选结果（包括完整的 candidates）.
    
    Returns:
        最后一次筛选结果字典，包含 candidates、screening_logic 等字段
    """
    return _last_screening_result
