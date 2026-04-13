"""Skills 加载器 - 三层渐进加载机制.

- Layer 1: YAML frontmatter（metadata）- 始终加载到 system prompt
- Layer 2: Markdown 正文（instructions）- 匹配查询时加载
- Layer 3: 资源文件（REFERENCE.md, scripts/）- 执行时按需加载
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class SkillMetadata:
    """Skill 元数据（Layer 1）."""

    name: str
    description: str
    allowed_tools: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class Skill:
    """完整的 Skill（包含三层内容）."""

    metadata: SkillMetadata
    content: str  # Layer 2: Markdown 指令
    resources_dir: Path | None = None  # Layer 3: 资源目录

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def description(self) -> str:
        return self.metadata.description


class SkillLoader:
    """Skills 加载器.

    使用示例：
        from pathlib import Path
        project_root = Path(__file__).resolve().parent.parent.parent
        loader = SkillLoader(skills_dir=project_root / ".stock_asking" / "skills")
        # 加载所有 skills 的 metadata（Layer 1）
        metadata_list = loader.load_all_metadata()
        
        # 根据查询匹配并加载完整 skill
        matched_skills = loader.match_and_load("找出放量上涨的股票")
    """

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._skills_cache: dict[str, Skill] = {}

    def load_all_metadata(self) -> dict[str, SkillMetadata]:
        """加载所有 skills 的 metadata（Layer 1，轻量级）.
        
        Returns:
            {skill_name: SkillMetadata}
        """
        if not self.skills_dir.exists():
            logger.warning(f"Skills directory not found: {self.skills_dir}")
            return {}

        metadata_dict = {}
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                metadata = self._parse_frontmatter(skill_md)
                metadata_dict[metadata.name] = metadata
            except Exception as e:
                logger.error(f"Failed to load skill metadata from {skill_md}: {e}")

        logger.info(f"Loaded {len(metadata_dict)} skills metadata")
        return metadata_dict

    def load_skill(self, skill_name: str) -> Skill | None:
        """加载完整的 skill（Layer 1 + 2 + 3）.
        
        Args:
            skill_name: Skill 名称
            
        Returns:
            Skill 对象，如果不存在则返回 None
        """
        if skill_name in self._skills_cache:
            return self._skills_cache[skill_name]

        skill_dir = self.skills_dir / skill_name
        skill_md = skill_dir / "SKILL.md"

        if not skill_md.exists():
            logger.warning(f"Skill not found: {skill_name}")
            return None

        try:
            # Layer 1: Metadata
            metadata = self._parse_frontmatter(skill_md)

            # Layer 2: Markdown content（去除 frontmatter）
            content = self._parse_content(skill_md)

            # Layer 3: Resources directory
            resources_dir = skill_dir if (skill_dir / "REFERENCE.md").exists() or (skill_dir / "scripts").exists() else None

            skill = Skill(metadata=metadata, content=content, resources_dir=resources_dir)
            self._skills_cache[skill_name] = skill

            logger.debug(f"Loaded skill: {skill_name}")
            return skill

        except Exception as e:
            logger.error(f"Failed to load skill {skill_name}: {e}")
            return None

    def match_skills(self, query: str, metadata_dict: dict[str, SkillMetadata]) -> list[str]:
        """根据查询匹配相关的 skills.
        
        简单的关键词匹配策略，可扩展为更智能的语义匹配。
        
        Args:
            query: 用户查询
            metadata_dict: 所有 skills 的 metadata
            
        Returns:
            匹配的 skill 名称列表
        """
        matched = []
        query_lower = query.lower()

        for name, metadata in metadata_dict.items():
            # 匹配描述中的关键词
            if any(keyword.lower() in query_lower for keyword in metadata.tags):
                matched.append(name)
            elif any(keyword.lower() in query_lower for keyword in metadata.description.lower().split()):
                matched.append(name)

        logger.debug(f"Matched {len(matched)} skills for query: {query[:50]}...")
        return matched

    def load_matched_skills(self, query: str) -> list[Skill]:
        """根据查询匹配并加载完整的 skills.
        
        Args:
            query: 用户查询
            
        Returns:
            匹配的 Skill 对象列表
        """
        metadata_dict = self.load_all_metadata()
        matched_names = self.match_skills(query, metadata_dict)
        
        skills = []
        for name in matched_names:
            skill = self.load_skill(name)
            if skill:
                skills.append(skill)

        return skills

    def _parse_frontmatter(self, skill_md: Path) -> SkillMetadata:
        """解析 YAML frontmatter（Layer 1）."""
        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read()

        # 提取 YAML frontmatter
        if not content.startswith("---"):
            raise ValueError(f"No YAML frontmatter found in {skill_md}")

        end_marker = content.find("---", 3)
        if end_marker == -1:
            raise ValueError(f"Invalid YAML frontmatter in {skill_md}")

        yaml_content = content[3:end_marker].strip()
        data = yaml.safe_load(yaml_content)

        return SkillMetadata(
            name=data.get("name", skill_md.parent.name),
            description=data.get("description", ""),
            allowed_tools=data.get("allowed-tools", []),
            tags=data.get("tags", []),
        )

    def _parse_content(self, skill_md: Path) -> str:
        """解析 Markdown 正文（Layer 2），去除 frontmatter."""
        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read()

        # 跳过 frontmatter
        if content.startswith("---"):
            end_marker = content.find("---", 3)
            if end_marker != -1:
                content = content[end_marker + 3:].strip()

        return content

    def get_skill_resources(self, skill_name: str) -> dict[str, str]:
        """获取 skill 的资源文件内容（Layer 3）.
        
        Args:
            skill_name: Skill 名称
            
        Returns:
            {relative_path: content}
        """
        skill = self._skills_cache.get(skill_name)
        if not skill or not skill.resources_dir:
            return {}

        resources = {}
        for file_path in skill.resources_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix in [".md", ".py", ".txt"]:
                try:
                    rel_path = file_path.relative_to(skill.resources_dir)
                    resources[str(rel_path)] = file_path.read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning(f"Failed to read resource {file_path}: {e}")

        return resources
