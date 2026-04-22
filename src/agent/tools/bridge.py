"""
Bridge 工具 - 连接 Deep Agent 与本地数据和执行逻辑

模块化设计：
- tool_executor: 统一调用本地工具和 MCP 工具
- logic_validator: 验证 screening_logic 结构
- strategy_resolver: 从配置文件查找策略名称
- screening_executor: 执行股票筛选
- script_saver: 生成并保存筛选脚本

注意:
- 这些工具在宿主进程中运行，可以访问已加载的 DataFrame
- MCP 工具在独立进程中运行，不持有数据
- 筛选逻辑的执行必须在宿主进程中完成
"""

from __future__ import annotations

from collections.abc import Callable

from .screening_executor import create_run_screening
from .script_saver import create_save_screening_script


def create_bridge_tools(
    data_fn,
    scripts_dir: str | None = None,
    stock_codes: list[str] | None = None,
) -> dict[str, Callable[..., str]]:
    """创建所有桥接工具.

    Args:
        data_fn: 返回当前数据 DataFrame 的函数
        scripts_dir: 脚本输出目录，如果为 None 则不创建 save_screening_script 工具
        stock_codes: 预筛选后的股票代码列表（可选）

    Returns:
        桥接工具函数字典
    """
    tools = {
        "run_screening": create_run_screening(data_fn, stock_codes),
    }
    
    # 只在提供了 scripts_dir 时保存脚本工具
    if scripts_dir is not None:
        tools["save_screening_script"] = create_save_screening_script(scripts_dir)
    
    return tools
