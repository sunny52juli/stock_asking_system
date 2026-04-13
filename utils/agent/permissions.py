"""工具权限控制系统 - 防止未授权的工具调用.

使用fnmatch模式匹配,支持通配符:
- "mcp.*" 匹配所有MCP工具
- "run_*" 匹配所有run_开头的工具
"""

from __future__ import annotations

import fnmatch

from infrastructure.config.settings import get_settings


class PermissionChecker:
    """工具权限检查器."""
    
    def __init__(self, allow_patterns: list[str] | None = None, 
                 deny_patterns: list[str] | None = None):
        """初始化权限检查器.
        
        Args:
            allow_patterns: 允许的模式列表
            deny_patterns: 拒绝的模式列表
        """
        self.allow_patterns = allow_patterns or ["*"]
        self.deny_patterns = deny_patterns or []
    
    @classmethod
    def from_config(cls) -> PermissionChecker:
        """从配置加载权限规则."""
        settings = get_settings()
        return cls(
            allow_patterns=settings.permissions.allow,
            deny_patterns=settings.permissions.deny
        )
    
    def is_allowed(self, tool_name: str) -> bool:
        """检查工具是否被允许调用.
        
        Args:
            tool_name: 工具名称
            
        Returns:
            True if allowed, False otherwise
        """
        # 先检查黑名单
        for pattern in self.deny_patterns:
            if fnmatch.fnmatch(tool_name, pattern):
                return False
        
        # 再检查白名单
        for pattern in self.allow_patterns:
            if fnmatch.fnmatch(tool_name, pattern):
                return True
        
        return False
    
    def validate_tools(self, tools: list) -> list:
        """过滤出允许的工具列表.
        
        Args:
            tools: 原始工具列表
            
        Returns:
            过滤后的工具列表
        """
        return [
            tool for tool in tools
            if self.is_allowed(getattr(tool, 'name', ''))
        ]
