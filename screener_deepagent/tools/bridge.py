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
import os
from collections.abc import Callable

# 筛选执行用 utils.stock_screener; 脚本生成用本包 generators (输出脚本仅依赖 utils)
from utils.exceptions import DataLoadError, ScreeningError, ToolExecutionError
from utils.stock_screener import StockScreener
from config.screener_deepagent_config import data_accessor
from datahub import get_available_industries as get_available_industries_from_data
from screener_deepagent.generators.screening_script_generator import ScreeningScriptGenerator


def create_run_screening(
    data_fn: data_accessor, scripts_dir: str
) -> Callable[[str, int], str]:
    """创建 run_screening 桥接工具

    Args:
        data_fn: 返回当前数据 DataFrame 的函数
        scripts_dir: 脚本输出目录

    Returns:
        run_screening 函数
    """

    def run_screening(screening_logic_json: str, top_n: int = 20) -> str:
        """执行股票筛选 (内部可抛 core 异常, 边界转为 JSON 以兼容 Agent)."""
        try:
            try:
                screening_logic = json.loads(screening_logic_json)
            except json.JSONDecodeError as e:
                raise ToolExecutionError(f"Invalid JSON: {e}") from e

            data = data_fn()
            if data is None or data.empty:
                raise DataLoadError("No data available")

            screener = StockScreener(data)
            try:
                candidates = screener.execute_screening(
                    screening_logic=screening_logic,
                    top_n=top_n,
                    query=screening_logic.get("name", ""),
                )
            except Exception as e:
                raise ScreeningError(f"Screening failed: {e}") from e

            result = {
                "status": "success",
                "screening_logic": screening_logic,
                "candidates": candidates,
                "count": len(candidates),
            }

            return json.dumps(result, ensure_ascii=False, default=str)
        except (DataLoadError, ScreeningError, ToolExecutionError) as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        except Exception as e:
            return json.dumps(
                {"error": f"Screening failed: {e}"}, ensure_ascii=False
            )

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

            # 从 screening_logic 中提取策略名称（必须存在）
            # 如果不存在，尝试从配置的策略模板中匹配或使用默认值
            original_name = screening_logic.get("name", "")
            
            # 如果没有 name 字段，尝试从配置的策略模板中匹配
            if not original_name.strip():
                # 从配置中读取策略模板，查找与 query 匹配的 demo_query
                from config.strategy_des import StrategyDescriptions
                
                matched_strategy = None
                for strategy_name, template in StrategyDescriptions.STRATEGY_TEMPLATES.items():
                    demo_query = template.get("demo_query", "")
                    # 检查 query 是否包含 demo_query 中的关键词
                    # 提取 demo_query 的第一行作为匹配依据（去除序号和格式符号）
                    demo_first_line = demo_query.strip().split('\n')[0].strip()
                    
                    # 如果 query 包含 demo_query 的关键词，或者 demo_query 包含在 query 中
                    if demo_first_line in query or query in demo_query:
                        matched_strategy = strategy_name
                        break
                    
                    # 或者检查是否有共同的关键词（至少 2 个中文字符）
                    import re
                    demo_keywords = re.findall(r'[\u4e00-\u9fa5]{2,}', demo_first_line)
                    for keyword in demo_keywords:
                        if keyword in query:
                            matched_strategy = strategy_name
                            break
                    
                    if matched_strategy:
                        break
                
                original_name = matched_strategy if matched_strategy else "未命名筛选"
            
            # 从配置中读取 strategy_num（如果存在）
            strategy_num = screening_logic.get("strategy_num", 1)
            
            # 提取纯净的策略名称（移除 Agent 可能添加的后缀）
            # 规则：如果 name 包含下划线 + 版本号，只取第一部分
            if "_" in original_name:
                # 尝试分割并判断是否有版本标识
                parts = original_name.split("_")
                # 如果最后一部分看起来像版本标识（包含版、version 等），则丢弃
                last_part = parts[-1]
                if any(keyword in last_part for keyword in ["版", "version", "v"]):
                    strategy_name = "_".join(parts[:-1])
                else:
                    strategy_name = original_name
            else:
                strategy_name = original_name
            
            os.makedirs(scripts_dir, exist_ok=True)
            generator = ScreeningScriptGenerator(output_dir=scripts_dir)
            try:
                script_paths = generator.generate_script(
                    screening_logic=screening_logic, 
                    query=query,
                    strategy_num=strategy_num,
                    strategy_name=strategy_name  # 使用纯净的策略名称
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
) -> dict[str, Callable[..., str]]:
    """创建所有桥接工具

    Args:
        data_fn: 返回当前数据 DataFrame 的函数
        scripts_dir: 脚本输出目录，如果为 None 则不创建 save_screening_script 工具

    Returns:
        桥接工具函数字典
    """
    tools = {
        "run_screening": create_run_screening(data_fn, scripts_dir or ""),
        "get_available_industries": create_get_available_industries(data_fn),
    }
    
    # 只在提供了 scripts_dir 时保存脚本工具
    if scripts_dir is not None:
        tools["save_screening_script"] = create_save_screening_script(scripts_dir)
    
    return tools
