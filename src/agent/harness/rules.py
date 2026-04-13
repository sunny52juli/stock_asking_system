"""Rules 加载器 - 从配置文件加载规则并注入到 system prompt.

- 从 .stock_asking/rules/*.md 加载规则文件
- 合并到 system prompt 中约束 Agent 行为
- 支持动态启用/禁用规则
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class RulesLoader:
    """Rules 加载器.

    使用示例：
        rules = RulesLoader.load(config_dir)
        # rules 是规则名称 -> 规则内容的字典
        # 可合并到 system prompt 中
    """

    @staticmethod
    def load(config_dir: Path) -> dict[str, str]:
        """从配置目录加载所有规则文件.
        
        Args:
            config_dir: 配置目录路径（包含 rules/ 子目录）
            
        Returns:
            {rule_name: rule_content} 字典
        """
        rules_dir = config_dir / "rules"
        if not rules_dir.exists():
            logger.warning(f"Rules directory not found: {rules_dir}")
            return {}

        rules_dict = {}
        for rule_file in rules_dir.glob("*.md"):
            try:
                rule_name = rule_file.stem
                rule_content = rule_file.read_text(encoding="utf-8")
                rules_dict[rule_name] = rule_content
                logger.debug(f"Loaded rule: {rule_name}")
            except Exception as e:
                logger.error(f"Failed to load rule from {rule_file}: {e}")

        logger.info(f"Loaded {len(rules_dict)} rules")
        return rules_dict

    @staticmethod
    def build_rules_section(rules_dict: dict[str, str]) -> str:
        """将规则字典格式化为 system prompt 的一部分.
        
        Args:
            rules_dict: 规则字典
            
        Returns:
            格式化后的规则文本
        """
        if not rules_dict:
            return ""

        sections = ["\n# Active Rules\n"]
        for rule_name, rule_content in rules_dict.items():
            sections.append(f"\n## Rule: {rule_name}\n")
            sections.append(rule_content)
            sections.append("\n---\n")

        return "\n".join(sections)
