"""DeepAgent factory for creating the screener agent.

This module integrates deepagents framework with our custom components:
- Skills System (SkillRegistry) → deepagents skills
- Memory System (LongTermMemory) → deepagents memory (AGENTS.md)
- Context Engineering (ContextInjector) → system_prompt
- Tool Provider (MCP + Bridge tools) → deepagents tools

Architecture:
- Use deepagents as a single powerful agent with planning capabilities
- Inject our domain-specific skills, tools, and memory
- Let deepagents handle task decomposition via built-in write_todos tool
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from deepagents.backends.utils import create_file_data
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver

if TYPE_CHECKING:
    from screener_deepagent.context.skill_registry import SkillRegistry
    from screener_deepagent.memory.protocols import LongTermMemory
    from screener_deepagent.tools.provider import ScreenerToolProvider

logger = logging.getLogger(__name__)


def create_screener_agent(
    llm: BaseChatModel,
    tool_provider: ScreenerToolProvider,
    skill_registry: SkillRegistry,
    long_term_memory: LongTermMemory,
    skills_dir: Path | None = None,
) -> Any:
    """Create the screener deep agent.

    Args:
        llm: Language model
        tool_provider: Tool provider for MCP and Bridge tools
        skill_registry: Registry for loading skills
        long_term_memory: Long-term memory for cross-session persistence
        skills_dir: Directory containing SKILL.md files

    Returns:
        Compiled DeepAgent (CompiledStateGraph)
    """
    logger.info("Creating screener deep agent")

    # Get all tools (MCP + Bridge)
    all_tools = tool_provider.get_tools_for_agent("all")

    # Build system prompt with domain knowledge
    system_prompt = _build_system_prompt(tool_provider, skill_registry)

    # Prepare skills files for deepagents
    skills_files = _prepare_skills_files(skill_registry, skills_dir)

    # Prepare memory file (AGENTS.md) from long-term memory
    memory_content = _build_memory_content(long_term_memory)

    # Combine skills and memory into initial files
    initial_files = {**skills_files, "/AGENTS.md": create_file_data(memory_content)}

    # Create checkpointer (required for memory)
    checkpointer = MemorySaver()

    # Create the agent
    agent = create_deep_agent(
        model=llm,
        tools=all_tools,
        system_prompt=system_prompt,
        backend=(lambda rt: StateBackend(rt)),
        skills=["/skills/"],  # Point to skills directory
        memory=["/AGENTS.md"],  # Point to memory file
        checkpointer=checkpointer,
    )

    logger.info("Screener deep agent created successfully")
    return agent, initial_files


def _build_system_prompt(
    tool_provider: ScreenerToolProvider, skill_registry: SkillRegistry
) -> str:
    """Build the system prompt for the screener agent."""
    import json
    from config.screener_deepagent_prompts import SYSTEM_PROMPT_TEMPLATE

    tool_descriptions = tool_provider.get_tool_descriptions()
    tools_json = json.dumps(tool_descriptions, ensure_ascii=False, indent=2)

    # 使用配置文件中的模板
    return SYSTEM_PROMPT_TEMPLATE.format(tools_json=tools_json)


def _prepare_skills_files(
    skill_registry: SkillRegistry, skills_dir: Path | None
) -> dict[str, Any]:
    """Prepare skills files for deepagents StateBackend."""
    skills_files = {}

    # Get all skills from registry
    all_skills = skill_registry.all_skills

    for skill_name, skill in all_skills.items():
        # Create virtual path for skill
        skill_path = f"/skills/{skill_name}/SKILL.md"
        skills_files[skill_path] = create_file_data(skill.content)
        logger.debug("Prepared skill file: %s", skill_path)

    return skills_files


def _build_memory_content(long_term_memory: LongTermMemory) -> str:
    """Build AGENTS.md content from long-term memory."""
    from config.screener_deepagent_prompts import (
        AGENTS_MEMORY_TEMPLATE,
        EMPTY_MEMORY_CONTENT,
        PAST_SCREENING_TEMPLATE,
    )
    
    try:
        # Get user preferences
        try:
            prefs = long_term_memory.get_user_preferences()
        except NotImplementedError:
            # Use default preferences if not implemented
            from screener_deepagent.memory.protocols import UserPreferences
            prefs = UserPreferences(
                preferred_industries=[],
                preferred_indicators=[],
                default_top_n=20,
                risk_tolerance="medium",
                min_confidence=0.5,
            )

        # Get past successful screenings
        try:
            past_screenings = long_term_memory.get_past_screenings(limit=5)
        except NotImplementedError:
            past_screenings = []

        # Build AGENTS.md content using template
        if past_screenings:
            past_screenings_text = "\n".join([
                PAST_SCREENING_TEMPLATE.format(
                    query=record.query,
                    timestamp=record.timestamp.strftime('%Y-%m-%d %H:%M'),
                    candidates_count=record.candidates_count,
                    quality_score=record.quality_score,
                    tools_used=', '.join(record.tools_used),
                    returns_summary=record.returns_summary or '无',
                )
                for record in past_screenings
            ])
        else:
            past_screenings_text = ""

        return AGENTS_MEMORY_TEMPLATE.format(
            preferred_industries=', '.join(prefs.preferred_industries) if prefs.preferred_industries else '无',
            preferred_indicators=', '.join(prefs.preferred_indicators) if prefs.preferred_indicators else '无',
            default_top_n=prefs.default_top_n,
            risk_tolerance=prefs.risk_tolerance,
            min_confidence=prefs.min_confidence,
            past_screenings=past_screenings_text if past_screenings_text else '暂无历史记录。',
        )
    except Exception as e:
        logger.exception("Failed to build memory content: %s", e)
        return EMPTY_MEMORY_CONTENT
