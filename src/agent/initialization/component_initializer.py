"""组件初始化器 - 负责初始化所有Agent组件."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from infrastructure.logging.logger import get_logger
from src.agent.context.skill_registry import SkillRegistry
from src.agent.memory.long_term import LongTermMemory
from src.agent.tools.bridge import create_bridge_tools
from src.agent.tools.provider import ScreenerToolProvider
from utils.agent.llm_helper import build_llm_from_api_config
from src.agent.harness.rules import RulesLoader

logger = get_logger(__name__)


class ComponentInitializer:
    """组件初始化器 - 封装所有Agent组件的初始化逻辑."""
    
    def __init__(self, settings: Any, project_root: Path):
        """初始化组件初始化器.
        
        Args:
            settings: 全局配置对象
            project_root: 项目根目录
        """
        self.settings = settings
        self.project_root = project_root
        
        # 初始化结果
        self.llm = None
        self.mcp_tools = []
        self.bridge_tools = {}
        self.tool_provider = None
        self.skill_registry = None
        self.long_term_memory = None
        self.system_prompt = ""
        self.rules = []
    
    def initialize_all(self) -> dict[str, Any]:
        """初始化所有组件.
        
        Returns:
            包含所有初始化组件的字典
        """
        logger.info("=" * 60)
        logger.info("Screener DeepAgent - AI 股票推荐系统")
        logger.info("=" * 60)
        
        # 按顺序初始化各个组件
        self._load_rules()
        self._build_system_prompt()
        self._build_llm()
        self._load_mcp_tools()
        self._init_skills_and_memory()
        
        return {
            "llm": self.llm,
            "mcp_tools": self.mcp_tools,
            "bridge_tools": self.bridge_tools,
            "tool_provider": self.tool_provider,
            "skill_registry": self.skill_registry,
            "long_term_memory": self.long_term_memory,
            "system_prompt": self.system_prompt,
            "rules": self.rules,
        }
    
    def _load_rules(self):
        """加载规则文件."""
        self.rules = RulesLoader.load(self.project_root / "setting")
        logger.info(f"📋 已加载 {len(self.rules)} 条规则")
    
    def _build_system_prompt(self):
        """构建系统提示词."""
        from src.agent.context.prompt_builder import build_base_prompt
        
        # 先创建临时的 tool_provider 和 skill_registry
        temp_tool_provider = ScreenerToolProvider(mcp_tools=[], bridge_tools={})
        temp_skill_registry = SkillRegistry()
        
        base_prompt = build_base_prompt(temp_tool_provider, temp_skill_registry)
        
        if self.rules:
            from src.agent.harness.rules import RulesLoader
            rules_section = RulesLoader.build_rules_section(self.rules)
            self.system_prompt = base_prompt + rules_section
            logger.info(f"✅ 已加载 {len(self.rules)} 条规则到 system prompt")
        else:
            self.system_prompt = base_prompt
    
    def _build_llm(self):
        """构建LLM."""
        api_config = self.settings.llm.to_dict()
        self.llm = build_llm_from_api_config(api_config)
        logger.info(f"✅ LLM构建完成: {api_config.get('model')}")
    
    def _load_mcp_tools(self):
        """加载MCP工具."""
        logger.info("正在加载 MCP 工具...")
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
            
            connections = {
                "screener-mcp": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["-m", "mcp_server.server"],
                }
            }
            
            async def _load():
                client = MultiServerMCPClient(connections)
                return await client.get_tools()
            
            self.mcp_tools = asyncio.run(_load())
            tool_names = [getattr(t, 'name', f'tool_{i}') for i, t in enumerate(self.mcp_tools)]
            logger.info(f"✅ 成功加载 {len(self.mcp_tools)} 个 MCP 工具")
            logger.info(f"📦 工具列表：{', '.join(tool_names[:10])}{'...' if len(tool_names) > 10 else ''}")
        except Exception as e:
            logger.warning(f"⚠️ MCP 工具加载失败：{e}")
            self.mcp_tools = []
    
    def create_bridge_tools(self, data_fn, stock_codes: list[str] | None = None):
        """创建Bridge工具.
        
        Args:
            data_fn: 数据访问函数
            stock_codes: 预筛选的股票代码列表
        """
        scripts_dir = str(self.settings.output.strategies_dir)
        
        # 调试：确认 stock_codes 是否已设置
        if stock_codes:
            logger.info(f"🔧 Orchestrator 准备传递 stock_codes：{len(stock_codes)} 只")
        else:
            logger.warning("⚠️ Orchestrator 未设置 stock_codes，将传递 None")
        
        self.bridge_tools = create_bridge_tools(
            data_fn=data_fn,
            scripts_dir=scripts_dir,
            stock_codes=stock_codes,
        )
        logger.info("✅ Bridge工具创建完成")
    
    def create_tool_provider(self):
        """创建工具提供者."""
        self.tool_provider = ScreenerToolProvider(
            mcp_tools=self.mcp_tools,
            bridge_tools=self.bridge_tools,
        )
        logger.info("✅ 工具提供者创建完成")
    
    def _init_skills_and_memory(self):
        """初始化技能和记忆."""
        logger.info("初始化 Skills Registry...")
        self.skill_registry = SkillRegistry()
        skills_dir = Path(self.settings.output.strategies_dir).parent / "src.agent" / "skills"
        if skills_dir.exists():
            self.skill_registry.load_local_skills(str(skills_dir))
        
        logger.info("初始化 Long-term Memory...")
        self.long_term_memory = LongTermMemory(self.project_root / ".stock_asking" / "memory.db")
        logger.info("✅ Skills 和 Memory 初始化完成")
    
    def create_agent(self, llm, tool_provider, skill_registry, long_term_memory, query: str | None = None):
        """创建 Agent.
        
        Args:
            llm: LLM 实例
            tool_provider: 工具提供者
            skill_registry: 技能注册表
            long_term_memory: 长期记忆
            query: 用户查询（可选），用于智能选择工具
            
        Returns:
            (agent, initial_files) 元组
        """
        from src.agent.core.agent_factory import create_screener_agent
        
        logger.info(f"创建 Agent (deep_thinking={self.settings.harness.deep_thinking}, max_iterations={self.settings.harness.max_iterations})...")
        
        agent, initial_files = create_screener_agent(
            llm=llm,
            tool_provider=tool_provider,
            skill_registry=skill_registry,
            long_term_memory=long_term_memory,
            skills_dir=Path(self.settings.output.strategies_dir).parent / "src.agent" / "skills",
            deep_thinking=self.settings.harness.deep_thinking,
            max_iterations=self.settings.harness.max_iterations,
        )
        logger.info("✅ Agent 创建完成")
        
        return agent, initial_files
