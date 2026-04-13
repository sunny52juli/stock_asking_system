"""
Screener DeepAgent - 股票筛选智能体模块

本模块支持两种 Agent 模式:
- 深度思考模式 (deep_thinking=true): 使用 deepagents 框架，包含 write_todos、Skills、Memory
- 快速模式 (deep_thinking=false): 使用 LangGraph ReAct Agent，不包含 write_todos，响应更快

核心组件:
- agent_factory: Agent 创建和配置（支持双模式）
- tools: MCP 工具和 Bridge 工具管理
- context: Skills 管理
- memory: 跨会话持久化
"""

from src.agent.core.agent_factory import create_screener_agent
from src.agent.context import SkillRegistry
from src.agent.memory import ScreeningRecord, UserPreferences
from src.agent.memory.long_term import LongTermMemory
from src.agent.core.orchestrator import ScreenerOrchestrator
from src.agent.tools.provider import ScreenerToolProvider
from src.agent.core.subagent import BaseSubAgent, AgentOrchestrator
from datahub import get_available_industries
from datahub.loaders import StockDataLoader
from infrastructure.config.settings import get_settings
from utils.agent.result_checker import _check_api_key, _is_screening_successful

__all__ = [
    "create_screener_agent",
    "SkillRegistry",
    "LongTermMemory",
    "ScreenerToolProvider",
    "ScreeningRecord",
    "UserPreferences",
    "StockDataLoader",
    "get_available_industries",
    "ScreenerOrchestrator",
    "BaseSubAgent",
    "AgentOrchestrator",
    "get_settings",
    "_check_api_key",
    "_is_screening_successful",
]
