"""工具执行器 - 统一调用 MCP 工具."""

from __future__ import annotations

import inspect
import pandas as pd


from mcp_server.executors import TOOL_FUNCTIONS
from mcp_server.executors import execute_tool as mcp_execute_tool
def execute_tool_impl(
    tool_name: str,
    data: pd.DataFrame,
    params: dict,
    index_data: pd.DataFrame | None = None,
):
    """执行工具的包装函数 - 通过 MCP 工具执行器调用.
    
    Args:
        tool_name: 工具名称（如 beta, alpha, rsi 等）
        data: 数据 DataFrame
        params: 工具参数
        index_data: 指数数据 DataFrame (可选，仅接受该参数的工具使用)
        
    Returns:
        工具执行结果
    """
    
    # 合并参数
    exec_params = params.copy()
    
    # 如果传入了 index_data，检查目标工具是否接受该参数
    if index_data is not None:
        try:
            # 动态获取工具函数
            if tool_name in TOOL_FUNCTIONS:
                func = TOOL_FUNCTIONS[tool_name]
                sig = inspect.signature(func)
                
                # 只有当工具函数签名包含 index_data 参数时才传入
                if 'index_data' in sig.parameters:
                    # 检查是否为空
                    is_empty = (
                        (hasattr(index_data, 'is_empty') and index_data.is_empty()) or
                        (hasattr(index_data, 'empty') and index_data.empty) or
                        len(index_data) == 0
                    )
                    if not is_empty:
                        exec_params['index_data'] = index_data
        except (ImportError, KeyError):
            # 如果无法获取函数信息，跳过 index_data
            pass
    
    return mcp_execute_tool(tool_name=tool_name, data=data, **exec_params)
