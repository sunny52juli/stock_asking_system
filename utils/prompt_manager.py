#!/usr/bin/env python3
"""
Prompt 模板管理器 - 统一管理所有 Prompt 模板

解决问题：
- Prompt 字符串直接硬编码在代码中，维护困难
- 修改 Prompt 需要修改代码
- Prompt 难以复用

使用方法：
    from utils.prompt_manager import PromptManager

    pm = PromptManager()
    pm = PromptManager(template_dir='path/to/templates')
    prompt = pm.render('screening_system',
                       tools_desc='...',
                       industries_desc='...')
"""

from pathlib import Path
from string import Template
from typing import Any


class PromptManager:
    """
    Prompt 模板管理器

    支持两种模板格式：
    1. 简单的 Python string.Template（默认）
    2. Jinja2 模板（如果安装了 jinja2）

    模板文件存放在各子系统的 prompt/ 目录下，以 .txt 或 .j2 为扩展名。
    初始化时需要传入 template_dir 参数指定模板目录。
    """

    def __init__(self, template_dir: str | None = None):
        """
        初始化 Prompt 管理器

        Args:
            template_dir: 模板目录路径，默认为项目根目录下的 prompts/
        """
        if template_dir:
            self.template_dir = Path(template_dir)
        else:
            # 默认使用项目根目录下的 prompts/ 目录
            project_root = Path(__file__).parent.parent
            self.template_dir = project_root / "prompts"

        # 确保目录存在
        self.template_dir.mkdir(parents=True, exist_ok=True)

        # 尝试导入 Jinja2（可选）
        self._jinja_env = None
        try:
            from jinja2 import Environment, FileSystemLoader
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(self.template_dir)),
                trim_blocks=True,
                lstrip_blocks=True
            )
        except ImportError:
            pass

        # 模板缓存
        self._template_cache: dict[str, str] = {}

    def _load_template(self, template_name: str) -> str:
        """
        加载模板文件内容

        Args:
            template_name: 模板名称（不含扩展名）

        Returns:
            模板内容字符串
        """
        if template_name in self._template_cache:
            return self._template_cache[template_name]

        # 尝试不同的扩展名
        for ext in ['.txt', '.j2', '.jinja2', '']:
            template_path = self.template_dir / f"{template_name}{ext}"
            if template_path.exists():
                content = template_path.read_text(encoding='utf-8')
                self._template_cache[template_name] = content
                return content

        raise FileNotFoundError(f"模板文件不存在: {template_name}")

    def render(self, template_name: str, **kwargs: Any) -> str:
        """
        渲染模板

        Args:
            template_name: 模板名称
            **kwargs: 模板变量

        Returns:
            渲染后的字符串
        """
        # 如果有 Jinja2 环境，优先使用
        if self._jinja_env:
            try:
                template = self._jinja_env.get_template(f"{template_name}.j2")
                return template.render(**kwargs)
            except Exception:
                pass

            try:
                template = self._jinja_env.get_template(f"{template_name}.txt")
                return template.render(**kwargs)
            except Exception:
                pass

        # 回退到 Python string.Template
        template_content = self._load_template(template_name)
        template = Template(template_content)
        return template.safe_substitute(**kwargs)

    def render_string(self, template_str: str, **kwargs: Any) -> str:
        """
        渲染字符串模板（不从文件加载）

        Args:
            template_str: 模板字符串
            **kwargs: 模板变量

        Returns:
            渲染后的字符串
        """
        if self._jinja_env:
            from jinja2 import Template as JinjaTemplate
            template = JinjaTemplate(template_str)
            return template.render(**kwargs)

        template = Template(template_str)
        return template.safe_substitute(**kwargs)

    def list_templates(self) -> list:
        """列出所有可用的模板"""
        templates = []
        for ext in ['.txt', '.j2', '.jinja2']:
            templates.extend([
                p.stem for p in self.template_dir.glob(f"*{ext}")
            ])
        return sorted(set(templates))


# 全局单例
_prompt_manager: PromptManager | None = None


def get_prompt_manager(template_dir: str | None = None) -> PromptManager:
    """
    获取 Prompt 管理器单例

    Args:
        template_dir: 模板目录（首次调用时设置）

    Returns:
        PromptManager 实例
    """
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager(template_dir)
    return _prompt_manager


def render_prompt(template_name: str, **kwargs: Any) -> str:
    """
    渲染 Prompt 模板的便捷函数

    Args:
        template_name: 模板名称
        **kwargs: 模板变量

    Returns:
        渲染后的 Prompt
    """
    return get_prompt_manager().render(template_name, **kwargs)
