"""Agent工厂 - 负责Agent的创建和复用."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from infrastructure.logging.logger import get_logger
from utils.agent.llm_helper import build_llm_from_api_config

logger = get_logger(__name__)


class AgentFactory:
    """Agent工厂 - 管理Agent的生命周期."""
    
    def __init__(self, settings: Any):
        """初始化.
        
        Args:
            settings: 全局配置
        """
        self.settings = settings
        self.agent = None
        self.initial_files = None
    
    def create_or_reuse(
        self,
        component_initializer,
        query: str | None = None,
        bridge_tools: dict | None = None
    ) -> tuple[Any, dict]:
        """创建或复用Agent.
        
        Args:
            component_initializer: 组件初始化器
            query: 用户查询（可选）
            bridge_tools: 桥接工具（交互式模式）
            
        Returns:
            (Agent实例, initial_files)
        """
        # Deep Mode: Agent已预创建，直接返回
        if self.settings.harness.deep_thinking and self.agent:
            logger.debug("Reusing pre-created deep thinking agent")
            return self.agent, self.initial_files
        
        # Quick Mode: 检查是否可以复用
        if not self.settings.harness.deep_thinking and self.agent:
            logger.debug("Reusing quick mode agent")
            return self.agent, self.initial_files
        
        # 创建新Agent
        logger.info(f"Creating new agent (deep_thinking={self.settings.harness.deep_thinking})...")
        
        # 交互式模式：动态创建所需组件
        if bridge_tools:
            components = self._create_interactive_components(component_initializer, bridge_tools)
        else:
            # 批量模式：使用component_initializer的组件
            components = {
                "tool_provider": component_initializer.tool_provider,
                "skill_registry": component_initializer.skill_registry,
                "long_term_memory": component_initializer.long_term_memory,
            }
        
        # 创建Agent
        self.agent, self.initial_files = component_initializer.create_agent(
            llm=component_initializer.llm,
            **components,
            query=query,
        )
        
        return self.agent, self.initial_files
    
    def _create_interactive_components(
        self,
        component_initializer,
        bridge_tools: dict
    ) -> dict:
        """为交互式模式动态创建组件.
        
        Args:
            component_initializer: 组件初始化器
            bridge_tools: 桥接工具
            
        Returns:
            组件字典
        """
        from src.agent.tools.provider import ScreenerToolProvider
        from src.agent.context.skill_registry import SkillRegistry
        from src.agent.memory.long_term import LongTermMemory
        
        # 动态创建LLM（如果尚未创建）
        if not component_initializer.llm:
            logger.info("[CONFIG] 创建LLM（交互式模式）...")
            api_config = self.settings.llm.to_dict()
            
            # 验证API Key
            if not api_config.get('api_key'):
                logger.error("[ERROR] API Key未配置！请检查.env文件")
                raise ValueError("API Key未配置，无法创建LLM")
            
            component_initializer.llm = build_llm_from_api_config(api_config)
            logger.info(f"[OK] LLM创建完成: {api_config.get('model')}")
        
        tool_provider = ScreenerToolProvider(mcp_tools=[], bridge_tools=bridge_tools)
        skill_registry = SkillRegistry()
        
        # 使用项目根目录下的memory.db
        db_path = Path(__file__).resolve().parent.parent.parent.parent / ".stock_asking" / "memory.db"
        long_term_memory = LongTermMemory(db_path=db_path)
        
        return {
            "tool_provider": tool_provider,
            "skill_registry": skill_registry,
            "long_term_memory": long_term_memory,
        }
    
    def update_executor(self, query_executor):
        """更新查询执行器的Agent引用.
        
        Args:
            query_executor: 查询执行器实例
        """
        if query_executor:
            query_executor.agent = self.agent
            query_executor.initial_files = self.initial_files


def create_screener_agent(
    llm,
    tool_provider,
    skill_registry,
    long_term_memory,
    skills_dir=None,
    deep_thinking=False,
    query=None,
    rules_dict=None,
) -> tuple[Any, dict]:
    """创建股票筛选Agent（兼容旧接口）.
    
    Args:
        llm: LLM实例
        tool_provider: 工具提供者
        skill_registry: 技能注册表
        long_term_memory: 长期记忆
        skills_dir: Skills目录（可选）
        deep_thinking: 是否深度思考模式
        max_iterations: 最大迭代次数
        query: 用户查询（可选）
        rules_dict: 规则字典（可选）
        
    Returns:
        (Agent实例, initial_files)元组
    """
    # 导入DeepAgents或LangGraph相关模块
    try:
        if deep_thinking:
            from deepagents import create_deep_agent
            from deepagents.backends.state import StateBackend
            from langgraph.checkpoint.memory import MemorySaver
            
            # 准备 Skills 文件
            skills_files = _prepare_skills_files(skill_registry, skills_dir)
            
            # 准备 Memory 文件 (AGENTS.md)
            memory_content = _build_memory_content(long_term_memory, query)
            
            # 合并 Skills 和 Memory 到 initial_files
            initial_files = {
                **skills_files,
                "/AGENTS.md": _create_file_data(memory_content),
            }
            
            # 创建 checkpointer（Memory 必需）
            checkpointer = MemorySaver()
            
            # 创建 Deep Agent
            agent = create_deep_agent(
                model=llm,
                tools=tool_provider.get_tools_for_agent("all"),
                system_prompt=_build_system_prompt(rules_dict),
                backend=(lambda rt: StateBackend(rt)),
                skills=["/skills/"],
                memory=["/AGENTS.md"],
                checkpointer=checkpointer,
            )
            
            logger.info("[OK] Deep thinking agent created successfully")
        else:
            from langgraph.prebuilt import create_react_agent
            agent = create_react_agent(
                model=llm,
                tools=tool_provider.get_tools_for_agent("all"),
                state_modifier=_build_system_prompt(rules_dict),
            )
            
            # 快速模式不需要 initial_files
            initial_files = {
                "skills": {},
                "rules": rules_dict or [],
            }
        
        return agent, initial_files
        
    except ImportError as e:
        logger.error(f"[ERROR] 无法导入Agent框架: {e}")
        raise


def _build_system_prompt(rules_dict=None) -> str:
    """构建系统提示词.
    
    Args:
        rules_dict: 规则字典
        
    Returns:
        系统提示词字符串
    """
    base_prompt = """你是一个专业的量化交易策略助手。

你的任务是帮助用户根据自然语言描述生成股票筛选策略。

## 工作流程
1. 理解用户的选股意图
2. 分析需要的技术指标和条件
3. 使用可用工具获取数据并执行筛选
4. 返回符合条件的股票列表

## 注意事项
- 始终验证筛选结果的合理性
- 如果结果为空，尝试调整参数
- 保存成功的筛选脚本供后续使用
"""
    
    if rules_dict:
        rules_section = "\n\n## 必须遵守的规则\n"
        for i, rule in enumerate(rules_dict, 1):
            rules_section += f"{i}. {rule}\n"
        return base_prompt + rules_section
    
    return base_prompt


def _load_skills_to_files(skills_dir) -> dict:
    """加载Skills到文件上下文中.
    
    Args:
        skills_dir: Skills目录路径
        
    Returns:
        文件字典
    """
    from pathlib import Path
    
    skills_path = Path(skills_dir)
    if not skills_path.exists():
        return {}
    
    files = {}
    for skill_file in skills_path.rglob("SKILL.md"):
        try:
            relative_path = str(skill_file.relative_to(skills_path.parent))
            files[relative_path] = skill_file.read_text(encoding='utf-8')
        except Exception as e:
            logger.warning(f"[WARN] 加载Skill失败 {skill_file}: {e}")
    
    return files


def _prepare_skills_files(skill_registry, skills_dir) -> dict:
    """准备 Skills 文件用于 deepagents.
    
    Args:
        skill_registry: Skill 注册表
        skills_dir: Skills 目录路径
        
    Returns:
        Skills 文件字典，键为 /skills/xxx 格式
    """
    from pathlib import Path
    
    skills_files = {}
    registered_skill_names = set()
    
    # 从 skill_registry 加载已注册的 Skills（优先）
    if skill_registry:
        # SkillRegistry 使用 _skills 属性
        for skill_name, skill in skill_registry._skills.items():
            file_path = f"/skills/{skill_name}/SKILL.md"
            skills_files[file_path] = _create_file_data(skill.content)
            registered_skill_names.add(skill_name)
    
    # 从文件系统加载额外的 Skills（去重）
    if skills_dir:
        skills_path = Path(skills_dir)
        if skills_path.exists():
            for skill_file in skills_path.rglob("SKILL.md"):
                try:
                    relative_path = skill_file.relative_to(skills_path)
                    # 提取 skill 名称用于去重判断
                    skill_name = str(relative_path).replace("\\", "/").rstrip("/SKILL.md")
                    
                    # 如果该 skill 已经在 registry 中，跳过
                    if skill_name in registered_skill_names:
                        logger.debug(f"跳过重复的 Skill: {skill_name}")
                        continue
                    
                    file_path = f"/skills/{relative_path}"
                    content = skill_file.read_text(encoding='utf-8')
                    skills_files[file_path] = _create_file_data(content)
                except Exception as e:
                    logger.warning(f"[WARN] 加载Skill文件失败 {skill_file}: {e}")
    
    return skills_files


def _build_memory_content(long_term_memory, query=None) -> str:
    """构建 Memory 内容 (AGENTS.md).
    
    Args:
        long_term_memory: 长期记忆实例
        query: 用户查询（用于检索相关记忆）
        
    Returns:
        Memory 内容字符串
    """
    memory_lines = [
        "# Agent Memory",
        "",
        "This file contains the agent's long-term memory and preferences.",
        "",
    ]
    
    if long_term_memory:
        # 如果有查询，检索相关策略
        if query:
            strategies = long_term_memory.search_strategies(query, limit=10)
        else:
            # 否则获取最近的策略
            strategies = long_term_memory.get_recent_strategies(limit=10)
        
        if strategies:
            memory_lines.append("## Recent Strategies")
            memory_lines.append("")
            for i, strategy in enumerate(strategies, 1):
                memory_lines.append(f"{i}. **{strategy.strategy_name}**")
                memory_lines.append(f"   - Query: {strategy.query}")
                memory_lines.append(f"   - Candidates: {strategy.candidates_count}")
                if strategy.created_at:
                    memory_lines.append(f"   - Time: {strategy.created_at}")
                memory_lines.append("")
        else:
            memory_lines.append("## No strategies yet")
            memory_lines.append("")
            memory_lines.append("The agent is starting fresh. Build knowledge through interactions.")
    else:
        memory_lines.append("## Memory system not initialized")
        memory_lines.append("")
    
    return "\n".join(memory_lines)


def _create_file_data(content: str) -> dict:
    """创建文件数据对象.
    
    Args:
        content: 文件内容
        
    Returns:
        文件数据字典
    """
    from datetime import datetime
    
    return {
        "content": [content],  # deepagents 期望 list[str]
        "type": "text",
        "modified_at": datetime.now().isoformat(),
    }
