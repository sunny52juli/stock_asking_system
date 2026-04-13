"""MCP 工具注册层 - 使用装饰器自动化工具注册.

新增工具示例：
    @tool_registry.register(
        description="工具描述",
        category="math/time_series/technical/statistical/feature_engineering/risk_metrics/screening"
    )
    def your_tool_name(param1: str, param2: int = 5) -> str:
        # 实现逻辑
        return result
"""

from __future__ import annotations

from typing import Any

from mcp_server.auto_register import tool_registry


# ==================== 导出接口 ====================

def get_all_tools() -> dict[str, Any]:
    """获取所有已注册的工具定义."""
    return tool_registry.get_tool_definitions()


def register_to_mcp(mcp_instance: Any) -> None:
    """将所有工具注册到 FastMCP 实例."""
    tool_registry.register_to_mcp(mcp_instance)
