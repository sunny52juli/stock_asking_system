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

            # 不再自动保存脚本，只在用户明确要求时保存
            # if screening_logic.get("auto_save", False):
            #     try:
            #         os.makedirs(scripts_dir, exist_ok=True)
            #         generator = ScreeningScriptGenerator(output_dir=scripts_dir)
            #         script_path = generator.generate_script(
            #             screening_logic=screening_logic,
            #             query=screening_logic.get("name", ""),
            #         )
            #         result["script_path"] = script_path
            #         result["script_filename"] = os.path.basename(script_path)
            #     except Exception:
            #         pass

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
        """
        try:
            try:
                screening_logic = json.loads(screening_logic_json)
            except json.JSONDecodeError as e:
                raise ToolExecutionError(f"Invalid JSON: {e}") from e

            # 从配置中读取 strategy_num（如果存在）
            strategy_num = screening_logic.get("strategy_num", 1)
            
            os.makedirs(scripts_dir, exist_ok=True)
            generator = ScreeningScriptGenerator(output_dir=scripts_dir)
            try:
                script_paths = generator.generate_script(
                    screening_logic=screening_logic, 
                    query=query,
                    strategy_num=strategy_num
                )
            except Exception as e:
                raise ScreeningError(f"Failed to save script: {e}") from e

            result = {
                "status": "success",
                "script_paths": script_paths,
                "script_count": len(script_paths),
                "strategy_num": strategy_num,
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
