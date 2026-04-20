"""权限检查器 - 工具白名单/黑名单机制.

- 支持通配符匹配（fnmatch）
- deny 优先级高于 allow
- 在工具调用前进行权限验证
"""

from __future__ import annotations

import fnmatch
import logging
from typing import Any

from src.agent.config import PermissionsConfig

logger = logging.getLogger(__name__)


class PermissionChecker:
    """权限检查器.

    使用示例：
        checker = PermissionChecker.from_config(config)
        
        # 检查工具是否允许执行
        if not checker.is_allowed("run_screening"):
            raise PermissionError("Tool 'run_screening' is not allowed")
    """

    def __init__(self, allow_patterns: list[str], deny_patterns: list[str]):
        """初始化权限检查器.
        
        Args:
            allow_patterns: 允许的工具模式列表（支持通配符）
            deny_patterns: 禁止的工具模式列表（支持通配符）
        """
        self.allow_patterns = allow_patterns
        self.deny_patterns = deny_patterns

    @classmethod
    def from_config(cls, config: PermissionsConfig) -> "PermissionChecker":
        """从配置对象创建权限检查器.
        
        Args:
            config: 权限配置
            
        Returns:
            PermissionChecker 实例
        """
        return cls(
            allow_patterns=config.allow,
            deny_patterns=config.deny
        )

    def is_allowed(self, tool_name: str) -> bool:
        """检查工具是否允许执行.
        
        Args:
            tool_name: 工具名称
            
        Returns:
            True 如果允许，False 如果禁止
        """
        # 先检查 deny 列表（deny 优先级更高）
        if self._matches_any(tool_name, self.deny_patterns):
            logger.warning(f"Tool '{tool_name}' is denied by policy")
            return False

        # 如果有 allow 列表，必须匹配其中之一
        if self.allow_patterns:
            if self._matches_any(tool_name, self.allow_patterns):
                return True
            else:
                logger.warning(f"Tool '{tool_name}' is not in allow list")
                return False

        # 如果没有 allow 列表，默认允许（除非在 deny 列表中）
        return True

    def check_and_raise(self, tool_name: str) -> None:
        """检查权限并在不允许时抛出异常.
        
        Args:
            tool_name: 工具名称
            
        Raises:
            PermissionError: 如果工具不被允许
        """
        if not self.is_allowed(tool_name):
            raise PermissionError(
                f"Tool '{tool_name}' is not permitted. "
                f"Allowed patterns: {self.allow_patterns}, "
                f"Denied patterns: {self.deny_patterns}"
            )

    def _matches_any(self, name: str, patterns: list[str]) -> bool:
        """检查名称是否匹配任一模式.
        
        Args:
            name: 待检查的名称
            patterns: 模式列表（支持通配符）
            
        Returns:
            True 如果匹配任一模式
        """
        return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)

    def get_allowed_tools(self, available_tools: list[str]) -> list[str]:
        """从可用工具列表中过滤出允许的工具.
        
        Args:
            available_tools: 所有可用工具名称列表
            
        Returns:
            允许的工具名称列表
        """
        return [tool for tool in available_tools if self.is_allowed(tool)]
