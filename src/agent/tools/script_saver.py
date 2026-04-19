"""脚本保存工具 - 生成并保存筛选脚本."""

from __future__ import annotations

import json
import os

from infrastructure.errors.exceptions import ScreeningError, ToolExecutionError
from src.agent.generators.screening_script_generator import ScreeningScriptGenerator
from .strategy_resolver import find_strategy_name_from_config


def create_save_screening_script(scripts_dir: str):
    """创建 save_screening_script 桥接工具.

    Args:
        scripts_dir: 脚本输出目录

    Returns:
        save_screening_script 函数
    """

    def save_screening_script(screening_logic_json: str, query: str = "") -> str:
        """保存筛选脚本.
        
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
            strategy_name = find_strategy_name_from_config(query, screening_logic)
            
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
