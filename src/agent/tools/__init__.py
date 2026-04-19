"""Agent 工具模块 - 桥接 Deep Agent 与本地执行逻辑.

模块化设计:
- bridge: 主入口，创建所有桥接工具
- tool_executor: 统一调用本地工具和 MCP 工具
- logic_validator: 验证 screening_logic 结构
- strategy_resolver: 从配置文件查找策略名称
- screening_executor: 执行股票筛选
- script_saver: 生成并保存筛选脚本
"""

from .bridge import create_bridge_tools
from .screening_executor import get_last_screening_result
from .tool_executor import execute_tool_impl

__all__ = [
    "create_bridge_tools",
    "get_last_screening_result",
    "execute_tool_impl",
]
