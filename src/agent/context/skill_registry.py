"""Skill registry for managing local and dynamic skills.

Skills are knowledge units (not tools) that are injected into agent prompts.
Local skills are loaded from SKILL.md files, dynamic skills are registered at runtime.

DeepAgents 会通过 read_file 工具自适应选择合适的 Skills，
所以我们只需加载所有 Skills 并注入到虚拟文件系统即可。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class Skill(Protocol):
    """Protocol for a skill (knowledge unit)."""

    @property
    def name(self) -> str:
        """Skill name."""
        ...

    @property
    def domain(self) -> str:
        """Skill domain (e.g., 'intent-patterns', 'strategy-templates')."""
        ...

    @property
    def content(self) -> str:
        """Skill content (markdown text)."""
        ...

    @property
    def token_cost(self) -> int:
        """Estimated token count for budget management."""
        ...


class LocalSkill:
    """File-based skill loaded from SKILL.md."""

    def __init__(self, skill_path: str) -> None:
        """Initialize local skill from file path.

        Args:
            skill_path: Path to SKILL.md file
        """
        path = Path(skill_path)
        if not path.exists():
            raise FileNotFoundError(f"Skill file not found: {skill_path}")

        self._name = path.parent.name
        self._domain = path.parent.parent.name if path.parent.parent.name != "skills" else "general"
        self._content = path.read_text(encoding="utf-8")
        self._token_cost = len(self._content) // 4  # Rough estimate: 4 chars per token

        logger.debug("Loaded local skill: %s (domain=%s, tokens~%d)", self._name, self._domain, self._token_cost)

    @property
    def name(self) -> str:
        return self._name

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def content(self) -> str:
        return self._content

    @property
    def token_cost(self) -> int:
        return self._token_cost


class DynamicSkill:
    """Runtime-registered skill (e.g., user-defined screening recipe)."""

    def __init__(self, name: str, domain: str, content: str) -> None:
        """Initialize dynamic skill.

        Args:
            name: Skill name
            domain: Skill domain
            content: Skill content (markdown text)
        """
        self._name = name
        self._domain = domain
        self._content = content
        self._token_cost = len(content) // 4

    @property
    def name(self) -> str:
        return self._name

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def content(self) -> str:
        return self._content

    @property
    def token_cost(self) -> int:
        return self._token_cost


class SkillRegistry:
    """Central registry for all skills (local + dynamic).
    
    DeepAgents 会通过 read_file 工具自适应选择合适的 Skills，
    所以我们只需加载所有 Skills 并注入到虚拟文件系统即可。
    """

    def __init__(self) -> None:
        """Initialize empty skill registry."""
        self._skills: dict[str, Skill] = {}

    def load_local_skills(self, skills_dir: str) -> None:
        """Load all local skills from directory.

        Args:
            skills_dir: Path to skills directory containing subdirs with SKILL.md files
        """
        skills_path = Path(skills_dir)
        if not skills_path.exists():
            logger.warning("Skills directory not found: %s", skills_dir)
            return

        skill_files = list(skills_path.rglob("SKILL.md"))
        logger.info("Loading %d local skills from %s", len(skill_files), skills_dir)

        for skill_file in skill_files:
            try:
                skill = LocalSkill(str(skill_file))
                self._skills[skill.name] = skill
                logger.debug("Registered skill: %s", skill.name)
            except Exception as e:
                logger.exception("Failed to load skill from %s: %s", skill_file, e)

        logger.info("Loaded %d skills total", len(self._skills))

    def register(self, skill: Skill) -> None:
        """Register a dynamic skill.

        Args:
            skill: Skill to register
        """
        self._skills[skill.name] = skill
        logger.info("Registered dynamic skill: %s", skill.name)

    def unregister(self, name: str) -> None:
        """Unregister a skill by name.

        Args:
            name: Skill name to remove
        """
        if name in self._skills:
            del self._skills[name]
            logger.info("Unregistered skill: %s", name)

    def get(self, name: str) -> Skill | None:
        """Get a skill by name.

        Args:
            name: Skill name

        Returns:
            Skill if found, None otherwise
        """
        return self._skills.get(name)

    @property
    def all_skills(self) -> dict[str, Skill]:
        """Return all registered skills.

        Returns:
            Dict mapping skill name to Skill object
        """
        return dict(self._skills)
