"""
Bridge 工具模块

提供供 Deep Agent 调用的本地工具工厂函数，连接 Agent 与本地数据和执行逻辑:
- create_run_screening: 创建 run_screening 工具
- create_get_available_industries: 创建 get_available_industries 工具
- create_save_screening_script: 创建 save_screening_script 工具
- create_bridge_tools: 创建所有桥接工具

这些工厂函数需要注入数据访问函数来创建实际的工具函数。
"""

from src.agent.tools.bridge import (
    create_bridge_tools,
    create_get_available_industries,
    create_run_screening,
    create_save_screening_script,
)

__all__ = [
    "create_run_screening",
    "create_get_available_industries",
    "create_save_screening_script",
    "create_bridge_tools",
]
