"""
Screener DeepAgent - 基于 DeepAgents 框架的股票筛选模块

本模块使用 DeepAgents 架构实现智能股票筛选:
- 使用 deepagents.create_deep_agent() 创建强大的筛选智能体
- 集成 Skills System (SKILL.md) 提供领域知识
- 集成 Long-term Memory (SQLite) 记录历史和偏好
- 集成 MCP 工具和 Bridge 工具执行筛选逻辑

核心组件:
- agent_factory: DeepAgent 创建和配置
- tools: MCP 工具和 Bridge 工具管理
- context: Skills 管理
- memory: 跨会话持久化
"""

from screener_deepagent.agent_factory import create_screener_agent
from config.screener_deepagent_config import ScreenerDeepAgentConfig, data_accessor
from screener_deepagent.context import SkillRegistry
from datahub import get_available_industries, load_market_data
from screener_deepagent.memory import ScreeningRecord, UserPreferences
from screener_deepagent.memory.long_term import SQLiteLongTermMemory
from screener_deepagent.tools.provider import ScreenerToolProvider

__all__ = [
    "create_screener_agent",
    "ScreenerDeepAgentConfig",
    "SkillRegistry",
    "SQLiteLongTermMemory",
    "ScreenerToolProvider",
    "ScreeningRecord",
    "UserPreferences",
    "load_market_data",
    "get_available_industries",
]
