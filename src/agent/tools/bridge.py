"""
Bridge 工具实现

连接 Deep Agent 与本地数据和执行逻辑的桥梁工具:
- run_screening: 在本地数据上执行筛选
- get_available_industries: 获取当前数据中的行业列表
- save_screening_script: 保存筛选脚本

注意:
- 这些工具在宿主进程中运行，可以访问已加载的 DataFrame
- MCP 工具在独立进程中运行，不持有数据
- 筛选逻辑的执行必须在宿主进程中完成
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable

# 筛选执行用 utils.stock_screener; 脚本生成用本包 generators (输出脚本仅依赖 utils)
from infrastructure.errors.exceptions import DataLoadError, ScreeningError, ToolExecutionError
from utils.screening.stock_screener import StockScreener
from infrastructure.config.settings import get_settings
from datahub import get_available_industries as get_available_industries_from_data
from src.agent.generators.screening_script_generator import ScreeningScriptGenerator

logger = logging.getLogger(__name__)


def _validate_screening_logic(screening_logic: dict) -> str | None:
    """校验 screening_logic 结构的完整性（使用 Pydantic 模型）.
    
    Args:
        screening_logic: 待校验的筛选逻辑
        
    Returns:
        错误信息，如果校验通过则返回 None
    """
    try:
        from src.agent.models.screening_logic import ScreeningLogic
        
        # 1. 尝试解析为 Pydantic 模型（自动校验字段类型和必需性）
        logic_model = ScreeningLogic(**screening_logic)
        
        # 2. 校验变量一致性
        validation_errors = logic_model.validate_variable_consistency()
        if validation_errors:
            return "; ".join(validation_errors)
        
        return None
        
    except Exception as e:
        # Pydantic 会提供详细的校验错误信息
        return f"Validation error: {str(e)}"


def execute_tool_impl(tool_name: str, data, params: dict, computed_vars: dict):
    """执行工具的包装函数 - 通过反射调用对应的工具实现.
    
    Args:
        tool_name: 工具名称（如 filter_by_industry）
        data: 数据 DataFrame
        params: 工具参数
        computed_vars: 已计算的变量
        
    Returns:
        工具执行结果
    """
    # 导入工具实现模块
    from src.screening.tool_implementations import TOOL_REGISTRY
    
    if tool_name not in TOOL_REGISTRY:
        raise ValueError(f"未知工具：{tool_name}，可用工具：{list(TOOL_REGISTRY.keys())}")
    
    tool_func = TOOL_REGISTRY[tool_name]
    return tool_func(data=data, params=params, computed_vars=computed_vars)


def _find_strategy_name_from_config(query: str, screening_logic: dict) -> str:
    """从配置文件中查找匹配的策略名称。
    
    通过 query 或 screening_logic 中的 name 字段，在 settings.yaml 中查找对应的策略名。
    确保文件夹命名与配置文件中的策略名完全一致。
    
    Args:
        query: 用户查询字符串
        screening_logic: 筛选逻辑字典
        
    Returns:
        配置文件中的策略名称
        
    Raises:
        ValueError: 如果无法从配置中找到匹配的策略
    """
    settings = get_settings()
    
    # 遍历配置中的所有策略，查找匹配的
    for strategy_name, strategy_config in settings.strategies.items():
        # StrategyTemplateConfig 是 Pydantic 模型，使用属性访问
        config_query = strategy_config.query.strip() if strategy_config.query else ""
        
        # 方法1：精确匹配 query
        if query and query.strip() == config_query:
            return strategy_name
        
        # 方法2：模糊匹配 - query 包含策略名
        if query and strategy_name in query:
            return strategy_name
        
        # 方法3：检查 query 和 config_query 的相似度（关键词匹配）
        if query and config_query:
            import re
            query_keywords = set(re.findall(r'[\u4e00-\u9fa5]{2,4}', query))
            config_keywords = set(re.findall(r'[\u4e00-\u9fa5]{2,4}', config_query))
            
            # 如果有 50% 以上的关键词重叠，认为是同一个策略
            if query_keywords and config_keywords:
                overlap = len(query_keywords & config_keywords)
                total = len(query_keywords | config_keywords)
                if total > 0 and overlap / total >= 0.5:
                    return strategy_name
    
    # 如果没有找到匹配的策略，抛出异常
    raise ValueError(
        f"无法在配置文件中找到匹配的策略。\n"
        f"用户查询: {query}\n"
        f"screening_logic.name: {screening_logic.get('name', '')}\n"
        f"可用策略: {list(settings.strategies.keys())}"
    )


# 全局调用计数器（用于跟踪 Agent 重试）
_run_screening_call_count = 0


def create_run_screening(
    data_fn: data_accessor, scripts_dir: str, stock_codes: list[str] | None = None
) -> Callable[[str, int], str]:
    """创建 run_screening 桥接工具

    Args:
        data_fn: 返回当前数据 DataFrame 的函数
        scripts_dir: 脚本输出目录
        stock_codes: 预筛选后的股票代码列表（可选）

    Returns:
        run_screening 函数
    """

    def run_screening(screening_logic_json: str, top_n: int = 20) -> str:
        """执行股票筛选"""
        global _run_screening_call_count
        _run_screening_call_count += 1
        call_iteration = _run_screening_call_count
        
        # 解析 JSON
        screening_logic = json.loads(screening_logic_json)
        
        # 校验 screening_logic 结构
        validation_error = _validate_screening_logic(screening_logic)
        if validation_error:
            raise ValueError(f"Screening logic validation failed: {validation_error}")

        data = data_fn()
        if data is None or data.empty:
            raise ValueError("No data available")

        screener = StockScreener(data, stock_codes=stock_codes)
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

        return json.dumps(result, ensure_ascii=False, default=str)

    return run_screening


def create_get_available_industries(data_fn: data_accessor) -> Callable[[], str]:
    """创建 get_available_industries 桥接工具

    Args:
        data_fn: 返回当前数据 DataFrame 的函数

    Returns:
        get_available_industries 函数
    """

    def get_available_industries() -> str:
        """获取可用行业列表 (内部可抛 DataLoadError, 边界转为 JSON)."""
        try:
            data = data_fn()
            if data is None or data.empty:
                raise DataLoadError("No data available")
            industry_list = get_available_industries_from_data(data)
            return json.dumps({"industries": industry_list}, ensure_ascii=False)
        except DataLoadError as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        except Exception as e:
            return json.dumps(
                {"error": f"Failed to get industries: {e}"}, ensure_ascii=False
            )

    return get_available_industries




def create_save_screening_script(
    scripts_dir: str,
) -> Callable[[str, str], str]:
    """创建 save_screening_script 桥接工具

    Args:
        scripts_dir: 脚本输出目录

    Returns:
        save_screening_script 函数
    """

    def save_screening_script(screening_logic_json: str, query: str = "") -> str:
        """保存筛选脚本 (内部可抛 ToolExecutionError/ScreeningError, 边界转为 JSON).
        
        自动从配置中读取 strategy_num 参数，生成指定数量的策略版本。
        严格按照配置文件中的策略名称命名文件夹，避免 Agent 添加额外后缀。
        
        注意：此工具应由用户明确请求时调用，不应在 Agent 执行过程中自动调用。
        """
        try:
            try:
                screening_logic = json.loads(screening_logic_json)
            except json.JSONDecodeError as e:
                raise ToolExecutionError(f"Invalid JSON: {e}") from e

            # 从配置文件中查找匹配的策略名称
            # 优先使用配置文件中的策略名，确保文件夹命名一致
            strategy_name = _find_strategy_name_from_config(query, screening_logic)
            
            # 从配置中读取 strategy_num（如果存在）
            strategy_num = screening_logic.get("strategy_num", 1)
            
            os.makedirs(scripts_dir, exist_ok=True)
            generator = ScreeningScriptGenerator(output_dir=scripts_dir)
            try:
                script_paths = generator.generate_script(
                    screening_logic=screening_logic, 
                    query=query,
                    strategy_num=strategy_num,
                    strategy_name=strategy_name  # 使用配置文件中的策略名称
                )
            except Exception as e:
                raise ScreeningError(f"Failed to save script: {e}") from e

            result = {
                "status": "success",
                "script_paths": script_paths,
                "script_count": len(script_paths),
                "strategy_num": strategy_num,
                "strategy_name": strategy_name,
            }
            return json.dumps(result, ensure_ascii=False)
        except (ToolExecutionError, ScreeningError) as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        except Exception as e:
            return json.dumps(
                {"error": f"Failed to save script: {e}", "ensure_ascii": False}
            )

    return save_screening_script


def create_bridge_tools(
    data_fn: data_accessor,
    scripts_dir: str | None = None,
    stock_codes: list[str] | None = None,
) -> dict[str, Callable[..., str]]:
    """创建所有桥接工具

    Args:
        data_fn: 返回当前数据 DataFrame 的函数
        scripts_dir: 脚本输出目录，如果为 None 则不创建 save_screening_script 工具
        stock_codes: 预筛选后的股票代码列表（可选）

    Returns:
        桥接工具函数字典
    """
    tools = {
        "run_screening": create_run_screening(data_fn, scripts_dir or "", stock_codes),
        "get_available_industries": create_get_available_industries(data_fn),
    }
    
    # 只在提供了 scripts_dir 时保存脚本工具
    if scripts_dir is not None:
        tools["save_screening_script"] = create_save_screening_script(scripts_dir)
    
    return tools
