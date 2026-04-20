"""DeepAgent factory for creating the screener agent.

This module integrates deepagents framework with our custom components:
- Skills System (三层渐进加载) → deepagents skills
- Memory System (LongTermMemory) → deepagents memory (AGENTS.md)
- Context Engineering (ContextInjector) → system_prompt
- Tool Provider (MCP + Bridge tools) → deepagents tools
- Harness Framework (Hooks/Rules/Permissions) → 约束框架
- Session Management → 会话持久化
- Retry Manager → 错误重试管理

Architecture:
- Deep thinking mode: Use deepagents as a single powerful agent with planning capabilities
- Quick mode: Use simple LangGraph ReAct Agent without write_todos
- Inject our domain-specific skills, tools, and memory
- Apply harness constraints (hooks, rules, permissions)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from deepagents.backends.utils import create_file_data
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver

from src.agent.context.prompts import SYSTEM_PROMPT_TEMPLATE
from src.agent.context.skill_registry import SkillRegistry
from src.agent.harness.rules import RulesLoader
from src.agent.memory.protocols import LongTermMemory
from src.agent.tools.provider import ScreenerToolProvider


logger = logging.getLogger(__name__)


def create_screener_agent(
    llm: BaseChatModel,
    tool_provider: ScreenerToolProvider,
    skill_registry: SkillRegistry,
    long_term_memory: LongTermMemory,
    skills_dir: Path | None = None,
    deep_thinking: bool = False,
    max_iterations: int = 2,
    query: str | None = None,
    rules_dict: dict[str, str] | None = None,
) -> Any:
    """Create the screener agent.

    Args:
        llm: Language model
        tool_provider: Tool provider for MCP and Bridge tools
        skill_registry: Registry for loading skills
        long_term_memory: Long-term memory for cross-session persistence
        skills_dir: Directory containing SKILL.md files
        deep_thinking: If True, use deepagents with write_todos; if False, use simple ReAct agent
        max_iterations: Maximum iterations for agent execution (controls recursion limit)
        query: User query for intelligent memory/skill loading
        rules_dict: Rules dictionary from RulesLoader (will be injected into system prompt)

    Returns:
        Compiled Agent (CompiledStateGraph)
    """
    logger.info("Creating screener agent (deep_thinking=%s, max_iterations=%d)", deep_thinking, max_iterations)

    # Get all tools (MCP + Bridge)
    all_tools = tool_provider.get_tools_for_agent("all")

    # Build system prompt with domain knowledge and rules
    system_prompt = _build_system_prompt(tool_provider, skill_registry, rules_dict)

    if deep_thinking:
        # 深度思考模式：使用 deepagents（包含 write_todos）
        return _create_deep_agent_mode(
            llm=llm,
            tools=all_tools,
            system_prompt=system_prompt,
            skill_registry=skill_registry,
            long_term_memory=long_term_memory,
            skills_dir=skills_dir,
            max_iterations=max_iterations,
            query=query,
        )
    else:
        # 快速模式：使用简单 ReAct Agent（不包含 write_todos）
        return _create_react_agent_mode(
            llm=llm,
            tools=all_tools,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
        )


def _build_system_prompt(
    tool_provider: ScreenerToolProvider, 
    skill_registry: SkillRegistry,
    rules_dict: dict[str, str] | None = None
) -> str:
    """Build the system prompt for the screener agent.
    
    Args:
        tool_provider: Tool provider
        skill_registry: Skill registry
        rules_dict: Rules dictionary from RulesLoader
        
    Returns:
        Complete system prompt with tools, skills, and rules
    """


    tool_descriptions = tool_provider.get_tool_descriptions()
    tools_json = json.dumps(tool_descriptions, ensure_ascii=False, indent=2)
    
    logger.info(f"🔧 Injecting {len(tool_descriptions)} tool descriptions into System Prompt")
    if tool_descriptions:
        logger.info(f"   Tools: {[t['name'] for t in tool_descriptions]}")

    # 基础 prompt
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(tools_json=tools_json)
    
    # 添加强制停止规则，避免无限循环
    system_prompt += """

## ⚠️ 重要：停止条件（必须遵守）

**为避免无限循环，你必须严格遵守以下规则：**

### 1. 最多尝试 3 次不同的筛选策略
- **第 1 次**：使用最直接、最符合用户需求的策略
- **第 2 次**：如果第1次返回空结果，调整参数或更换指标
- **第 3 次**：如果第2次仍为空，使用简化条件或替代方案
- **第 3 次后无论结果如何，必须停止并返回最终报告**

### 2. 连续 2 次空结果立即停止
- 如果 `run_screening` 连续 2 次返回 `candidates: []`
- **不要继续尝试新策略**
- 直接向用户说明："当前市场条件下未找到符合条件的股票"
- 提供可能的原因分析和建议

### 3. 禁止无限重试
- ❌ **错误做法**：不断修改参数直到找到结果（会导致 recursion limit 错误）
- ✅ **正确做法**：尝试 2-3 次后，承认无解并给出专业建议

### 4. 每次调用后检查 candidates 数量
```python
result = run_screening(...)
if result['count'] == 0:
    # 记录这次失败
    failed_attempts += 1
    if failed_attempts >= 2:
        # 立即停止，返回最终报告
        return {
            "status": "completed",
            "message": "经过多次尝试，当前市场条件下未找到符合条件的股票",
            "attempts": failed_attempts,
            "suggestions": [...]
        }
```

### 5. 识别"无解"情况
以下情况说明应该停止：
- 市场整体下跌，没有股票满足"跑赢大盘"
- 波动率阈值设置过严，没有股票符合
- 数据不足或工具不可用

**记住：承认无解比无限重试更专业！**
"""
    
    # 注入 Rules（如果提供）
    if rules_dict:
        rules_section = RulesLoader.build_rules_section(rules_dict)
        system_prompt += rules_section
        logger.info(f"Injected {len(rules_dict)} rules into system prompt")

    return system_prompt


def _prepare_skills_files(
    skill_registry: SkillRegistry, skills_dir: Path | None
) -> dict[str, Any]:
    """Prepare skills files for deepagents StateBackend.
    
    DeepAgents 会通过 read_file 工具自适应选择合适的 Skills。
    """
    skills_files = {}
    all_skills = skill_registry.all_skills
    
    logger.info(f"📦 Preparing {len(all_skills)} skills for DeepAgents: {list(all_skills.keys())}")

    for skill_name, skill in all_skills.items():
        skill_path = f"/skills/{skill_name}/SKILL.md"
        skills_files[skill_path] = create_file_data(skill.content)
        logger.debug("Prepared skill file: %s", skill_path)

    return skills_files


def _build_memory_content(
    long_term_memory: LongTermMemory,
    query: str | None = None
) -> str:
    """Build AGENTS.md content from long-term memory.
    
    Args:
        long_term_memory: Long-term memory instance
        query: Current user query for relevant memory retrieval
        
    Returns:
        Formatted memory content as markdown
    """
    try:
        if query:
            # 智能检索：基于关键词搜索相关历史
            keywords = [word for word in query.split() if len(word) > 1]
            relevant_strategies = []
            
            for keyword in keywords[:3]:  # 最多用 3 个关键词
                strategies = long_term_memory.search_strategies(keyword, limit=3)
                relevant_strategies.extend(strategies)
            
            # 去重并按时间排序
            seen = set()
            unique_strategies = []
            for s in relevant_strategies:
                if s.strategy_name not in seen:
                    seen.add(s.strategy_name)
                    unique_strategies.append(s)
            
            recent_strategies = unique_strategies[:5]  # 最多 5 条
        else:
            # 回退：获取最近的策略
            recent_strategies = long_term_memory.get_recent_strategies(limit=5)
        
        if not recent_strategies:
            return "# Agent Memory\n\n暂无历史记录。"
        
        lines = ["# Agent Memory\n", "## Relevant History\n"]
        for strategy in recent_strategies:
            lines.append(f"### {strategy.strategy_name}")
            lines.append(f"- **Query**: {strategy.query}")
            lines.append(f"- **Candidates**: {strategy.candidates_count}")
            lines.append(f"- **Date**: {strategy.created_at}")
            lines.append("")
        
        logger.info(f"Loaded {len(recent_strategies)} relevant memories")
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Failed to build memory content: {e}")
        return "# Agent Memory\n\n暂无历史记录。"


def _create_deep_agent_mode(
    llm: BaseChatModel,
    tools: list[Any],
    system_prompt: str,
    skill_registry: SkillRegistry,
    long_term_memory: LongTermMemory,
    skills_dir: Path | None = None,
    max_iterations: int = 2,
    query: str | None = None,
) -> tuple[Any, dict[str, Any]]:
    """创建深度思考模式的 Agent（使用 deepagents，包含 write_todos）.
    
    Args:
        llm: Language model
        tools: List of tools
        system_prompt: System prompt
        skill_registry: Skill registry
        long_term_memory: Long-term memory
        skills_dir: Skills directory
        max_iterations: Maximum iterations (recursion limit)
        query: User query for intelligent memory/skill loading
        
    Returns:
        (agent, initial_files) tuple
    """
    logger.info("Creating deep thinking agent with deepagents framework (max_iterations=%d)", max_iterations)
    
    # Prepare skills files for deepagents
    skills_files = _prepare_skills_files(skill_registry, skills_dir)

    # Prepare memory file (AGENTS.md) from long-term memory
    memory_content = _build_memory_content(long_term_memory, query)

    # Combine skills and memory into initial files
    initial_files = {**skills_files, "/AGENTS.md": create_file_data(memory_content)}

    # Create checkpointer (required for memory)
    checkpointer = MemorySaver()

    # Create the deep agent
    agent = create_deep_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        backend=(lambda rt: StateBackend(rt)),
        skills=["/skills/"],
        memory=["/AGENTS.md"],
        checkpointer=checkpointer,
    )

    logger.info("Deep thinking agent created successfully")
    return agent, initial_files


def _create_react_agent_mode(
    llm: BaseChatModel,
    tools: list[Any],
    system_prompt: str,
    max_iterations: int = 2,
) -> tuple[Any, dict[str, Any]]:
    """创建快速模式的 Agent（使用 LangGraph ReAct，不包含 write_todos）.
    
    Args:
        llm: Language model
        tools: List of tools (不会包含 write_todos)
        system_prompt: System prompt
        max_iterations: Maximum iterations (stored for later use in invoke config)
        
    Returns:
        (agent, empty_dict) tuple
    """
    
    logger.info("Creating quick mode agent with LangGraph ReAct (no write_todos, max_iterations=%d)", max_iterations)
    
    # 创建简单的 ReAct Agent
    # 注意：这个 Agent 不会有 write_todos、skills、memory 等 deepagents 特性
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_prompt,
    )

    logger.info("Quick mode agent created successfully")
    # ReAct agent 不需要 initial_files
    return agent, {}
