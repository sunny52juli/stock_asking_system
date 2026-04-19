"""Skills 注册中心 - 动态技能管理.

import re
提供技能的自动发现、注册、版本管理和热重载功能。
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SkillMetadata:
    """技能元数据."""
    
    name: str
    version: str
    description: str
    author: str = ""
    tags: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    enabled: bool = True
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "tags": self.tags,
            "dependencies": self.dependencies,
            "enabled": self.enabled,
        }


@dataclass
class Skill:
    """技能实例."""
    
    metadata: SkillMetadata
    content: str
    file_path: Path
    category: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "content_preview": self.content[:200] + "..." if len(self.content) > 200 else self.content,
            "file_path": str(self.file_path),
            "category": self.category,
        }


class SkillRegistry:
    """技能注册中心.
    
    功能：
    - 自动扫描和加载技能
    - 版本管理和依赖检查
    - 热重载支持
    - 分类检索
    
    使用示例::
    
        registry = SkillRegistry()
        registry.scan_skills("src/agent/skills")
        
        # 获取技能
        skill = registry.get_skill("stock-screening/basic-filtering")
        
        # 按标签搜索
        skills = registry.search_by_tags(["screening", "technical"])
        
        # 热重载
        registry.reload_skill("stock-screening/basic-filtering")
    """
    
    def __init__(self):
        self.skills: dict[str, Skill] = {}
        self.categories: dict[str, list[str]] = {}
        self.skill_index: dict[str, list[str]] = {}  # tag -> skill names
    
    def scan_skills(self, skills_dir: str | Path) -> int:
        """扫描目录加载所有技能.
        
        Args:
            skills_dir: 技能目录路径
            
        Returns:
            加载的技能数量
        """
        skills_path = Path(skills_dir)
        if not skills_path.exists():
            logger.warning(f"⚠️  技能目录不存在: {skills_path}")
            return 0
        
        loaded_count = 0
        
        for category_dir in skills_path.iterdir():
            if not category_dir.is_dir() or category_dir.name.startswith("_"):
                continue
            
            category = category_dir.name
            self.categories[category] = []
            
            for skill_file in category_dir.glob("*.md"):
                try:
                    skill = self._load_skill(skill_file, category)
                    self.skills[skill.metadata.name] = skill
                    self.categories[category].append(skill.metadata.name)
                    
                    # 建立索引
                    for tag in skill.metadata.tags:
                        if tag not in self.skill_index:
                            self.skill_index[tag] = []
                        self.skill_index[tag].append(skill.metadata.name)
                    
                    loaded_count += 1
                    logger.debug(f"  ✓ 加载技能: {skill.metadata.name} v{skill.metadata.version}")
                    
                except Exception as e:
                    logger.error(f"❌ 加载技能失败 {skill_file}: {e}")
        
        logger.info(f"✅ 已加载 {loaded_count} 个技能 ({len(self.categories)} 个分类)")
        return loaded_count
    
    def get_skill(self, skill_name: str) -> Skill | None:
        """获取指定技能.
        
        Args:
            skill_name: 技能名称 (格式: category/skill-name)
            
        Returns:
            技能实例或 None
        """
        skill = self.skills.get(skill_name)
        
        if skill and not skill.metadata.enabled:
            logger.warning(f"⚠️  技能已禁用: {skill_name}")
            return None
        
        return skill
    
    def search_by_tags(self, tags: list[str]) -> list[Skill]:
        """按标签搜索技能.
        
        Args:
            tags: 标签列表
            
        Returns:
            匹配的技能列表
        """
        matching_skills = set()
        
        for tag in tags:
            if tag in self.skill_index:
                matching_skills.update(self.skill_index[tag])
        
        return [
            self.skills[name] 
            for name in matching_skills 
            if name in self.skills and self.skills[name].metadata.enabled
        ]
    
    def list_skills(self, category: str | None = None) -> list[Skill]:
        """列出技能.
        
        Args:
            category: 可选的分类过滤
            
        Returns:
            技能列表
        """
        if category:
            skill_names = self.categories.get(category, [])
            return [
                self.skills[name] 
                for name in skill_names 
                if name in self.skills and self.skills[name].metadata.enabled
            ]
        
        return [
            skill for skill in self.skills.values() 
            if skill.metadata.enabled
        ]
    
    def reload_skill(self, skill_name: str) -> bool:
        """热重载技能.
        
        Args:
            skill_name: 技能名称
            
        Returns:
            True 如果重载成功
        """
        if skill_name not in self.skills:
            logger.error(f"❌ 技能不存在: {skill_name}")
            return False
        
        skill = self.skills[skill_name]
        
        try:
            # 重新读取文件内容
            content = skill.file_path.read_text(encoding='utf-8')
            skill.content = content
            
            logger.info(f"🔄 技能已重载: {skill_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 重载技能失败 {skill_name}: {e}")
            return False
    
    def enable_skill(self, skill_name: str) -> bool:
        """启用技能."""
        if skill_name in self.skills:
            self.skills[skill_name].metadata.enabled = True
            logger.info(f"✅ 技能已启用: {skill_name}")
            return True
        return False
    
    def disable_skill(self, skill_name: str) -> bool:
        """禁用技能."""
        if skill_name in self.skills:
            self.skills[skill_name].metadata.enabled = False
            logger.info(f"⚠️  技能已禁用: {skill_name}")
            return True
        return False
    
    def get_stats(self) -> dict[str, Any]:
        """获取注册中心统计信息."""
        enabled_count = sum(1 for s in self.skills.values() if s.metadata.enabled)
        
        return {
            "total_skills": len(self.skills),
            "enabled_skills": enabled_count,
            "disabled_skills": len(self.skills) - enabled_count,
            "categories": len(self.categories),
            "tags": len(self.skill_index),
            "skills_by_category": {
                cat: len(names) for cat, names in self.categories.items()
            },
        }
    
    def _load_skill(self, file_path: Path, category: str) -> Skill:
        """从文件加载单个技能.
        
        Args:
            file_path: 技能文件路径
            category: 分类名称
            
        Returns:
            技能实例
        """
        content = file_path.read_text(encoding='utf-8')
        
        # 解析 YAML frontmatter
        metadata = self._parse_frontmatter(content, file_path.stem)
        
        skill_name = f"{category}/{metadata.name}"
        
        return Skill(
            metadata=metadata,
            content=content,
            file_path=file_path,
            category=category,
        )
    
    def _parse_frontmatter(self, content: str, default_name: str) -> SkillMetadata:
        """解析 YAML frontmatter.
        
        Args:
            content: 文件内容
            default_name: 默认名称
            
        Returns:
            技能元数据
        """
        
        # 提取 frontmatter
        match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        
        if not match:
            # 没有 frontmatter，使用默认值
            return SkillMetadata(
                name=default_name,
                version="1.0.0",
                description=f"Skill: {default_name}",
            )
        
        yaml_content = match.group(1)
        
        # 简单解析 YAML（避免依赖 pyyaml）
        metadata_dict = {}
        for line in yaml_content.split('\n'):
            if ':' in line and not line.strip().startswith('#'):
                key, _, value = line.partition(':')
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                
                # 处理列表
                if value.startswith('[') and value.endswith(']'):
                    value = [item.strip().strip('"').strip("'") 
                            for item in value[1:-1].split(',') if item.strip()]
                
                metadata_dict[key] = value
        
        return SkillMetadata(
            name=metadata_dict.get('name', default_name),
            version=metadata_dict.get('version', '1.0.0'),
            description=metadata_dict.get('description', ''),
            author=metadata_dict.get('author', ''),
            tags=metadata_dict.get('tags', []),
            dependencies=metadata_dict.get('dependencies', []),
        )


# 全局单例
_registry_instance: SkillRegistry | None = None


def get_skill_registry(skills_dir: str | Path | None = None) -> SkillRegistry:
    """获取全局技能注册中心实例.
    
    Args:
        skills_dir: 可选的技能目录，首次调用时自动扫描
        
    Returns:
        技能注册中心实例
    """
    global _registry_instance
    
    if _registry_instance is None:
        _registry_instance = SkillRegistry()
        
        if skills_dir:
            _registry_instance.scan_skills(skills_dir)
    
    return _registry_instance


def reset_skill_registry():
    """重置注册中心实例（用于测试）."""
    global _registry_instance
    _registry_instance = None
