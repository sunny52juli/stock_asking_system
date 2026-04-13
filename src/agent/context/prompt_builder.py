"""System Prompt构建器 - 整合工具描述和技能知识."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agent.tools.provider import ScreenerToolProvider
    from src.agent.context.skill_registry import SkillRegistry


def build_base_prompt(
    tool_provider: ScreenerToolProvider,
    skill_registry: SkillRegistry,
) -> str:
    """构建基础system prompt.
    
    Args:
        tool_provider: 工具提供者
        skill_registry: 技能注册表
        
    Returns:
        基础system prompt
    """
    from src.agent.context.prompts import SYSTEM_PROMPT_TEMPLATE
    
    tool_descriptions = tool_provider.get_tool_descriptions()
    tools_json = json.dumps(tool_descriptions, ensure_ascii=False, indent=2)
    
    return SYSTEM_PROMPT_TEMPLATE.format(tools_json=tools_json)
