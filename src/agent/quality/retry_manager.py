"""错误重试管理器 - Agent 层的质量评估重试.

本模块复用 infrastructure.retry.manager 的基础功能，并扩展：
- 与长期记忆系统集成（持久化重试历史）
- 指数退避延迟策略
- Temperature 动态调整
- 更细粒度的重试状态管理
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TYPE_CHECKING

# 复用基础设施层的核心功能
from infrastructure.retry.manager import (
    ErrorType,
    MAX_RETRY_COUNT,
    RETRYABLE_ERRORS,
    NON_RETRYABLE_ERRORS,
    classify_error,
    adjust_numeric_param,
    generate_adjusted_params,
    RetryRecord,
)

if TYPE_CHECKING:
    from src.agent.memory import GraphDatabaseMemory

logger = logging.getLogger(__name__)


# 最大重试次数硬限制（从基础设施层导入，这里只是别名）
# MAX_RETRY_COUNT 已在上面导入

# 可重试/不可重试的错误类型（从基础设施层导入）
# RETRYABLE_ERRORS, NON_RETRYABLE_ERRORS 已在上面导入

# 错误模式匹配规则（从基础设施层导入）
# ERROR_PATTERNS 已在 infrastructure.retry.manager 中定义


@dataclass
class RetryConfig:
    """重试配置."""

    max_retries: int = 3                          # 最大重试次数
    base_delay: float = 1.0                       # 基础延迟（秒）
    exponential_backoff: bool = True              # 是否指数退避
    adjust_temperature: bool = True               # 是否调整 temperature
    adjust_max_tokens: bool = False               # 是否调整 max_tokens


@dataclass
class RetryState:
    """重试状态."""

    attempt: int = 0
    max_retries: int = 3
    last_error: str = ""
    last_error_type: ErrorType = ErrorType.UNKNOWN
    adjusted_params: dict[str, Any] = field(default_factory=dict)

    @property
    def should_retry(self) -> bool:
        """是否应该继续重试."""
        return self.attempt < min(self.max_retries, MAX_RETRY_COUNT)


class RetryManager:
    """错误重试管理器.

    使用示例：
        manager = RetryManager(max_retries=3)
        
        for attempt in range(manager.config.max_retries):
            try:
                result = execute_query(query, **manager.get_adjusted_params())
                break
            except Exception as e:
                if not manager.should_retry(e):
                    raise
                manager.record_error(e)
                wait(manager.get_delay())
    """

    def __init__(self, config: RetryConfig | None = None, memory: GraphDatabaseMemory | None = None):
        """初始化重试管理器.
        
        Args:
            config: 重试配置
            memory: 长期记忆实例（可选，用于持久化重试历史）
        """
        self.config = config or RetryConfig()
        self.state = RetryState(max_retries=self.config.max_retries)
        self.memory = memory
        self._retry_counts: dict[str, int] = {}  # 工具级别的重试计数

    def classify_error(self, error: Exception | str) -> ErrorType:
        """分类错误类型 - 复用基础设施层的 classify_error 函数.
        
        Args:
            error: 异常对象或错误消息字符串
            
        Returns:
            ErrorType 枚举值
        """
        # 直接调用基础设施层的函数
        return classify_error(error)

    def should_retry(self, error: Exception | str, tool_name: str = "") -> bool:
        """判断是否应该重试 - 增强版.
        
        Args:
            error: 异常对象或错误消息
            tool_name: 工具名称（用于计数）
            
        Returns:
            True 如果应该重试
        """
        # 硬限制：最大重试次数
        attempt_count = self._retry_counts.get(tool_name, 0)
        if attempt_count >= MAX_RETRY_COUNT:
            logger.warning(f"Tool '{tool_name}' reached max retry limit ({MAX_RETRY_COUNT})")
            return False

        if not self.state.should_retry:
            return False

        error_type = self.classify_error(error)

        # 检查是否可重试
        if error_type in NON_RETRYABLE_ERRORS:
            logger.warning(f"Error type {error_type.value} is not retryable")
            return False

        return error_type in RETRYABLE_ERRORS

    def record_error(self, error: Exception | str, tool_name: str = "", original_params: dict[str, Any] | None = None) -> dict[str, Any]:
        """记录错误并计算调整后的参数 - 增强版.
        
        Args:
            error: 异常对象或错误消息
            tool_name: 工具名称
            original_params: 原始参数（用于自适应调整）
            
        Returns:
            调整后的参数字典
        """
        self.state.attempt += 1
        self.state.last_error = str(error)
        self.state.last_error_type = self.classify_error(error)

        # 更新工具级别的重试计数
        if tool_name:
            self._retry_counts[tool_name] = self._retry_counts.get(tool_name, 0) + 1

        # 根据错误类型调整参数
        adjusted_params = self._adjust_params_for_error(
            self.state.last_error_type, 
            original_params or {}
        )
        self.state.adjusted_params = adjusted_params

        logger.info(
            f"Retry {self.state.attempt}/{min(self.config.max_retries, MAX_RETRY_COUNT)}, "
            f"error_type={self.state.last_error_type.value}, "
            f"adjusted_params={adjusted_params}"
        )

        # 持久化到长期记忆
        if self.memory and original_params:
            self._record_retry_to_memory(
                tool_name=tool_name,
                error_type=self.state.last_error_type,
                original_params=original_params,
                adjusted_params=adjusted_params,
                attempt_count=self.state.attempt,
                success=False,
            )

        return adjusted_params

    def get_delay(self) -> float:
        """获取重试延迟时间.
        
        Returns:
            延迟秒数
        """
        if self.config.exponential_backoff:
            return self.config.base_delay * (2 ** (self.state.attempt - 1))
        else:
            return self.config.base_delay

    def get_adjusted_params(self) -> dict[str, Any]:
        """获取调整后的参数.
        
        Returns:
            调整后的参数字典
        """
        return self.state.adjusted_params.copy()

    def reset(self) -> None:
        """重置重试状态."""
        self.state = RetryState(max_retries=self.config.max_retries)
        self._retry_counts.clear()
        logger.debug("RetryManager state reset")

    def record_success(self, tool_name: str) -> None:
        """记录成功，重置计数器.
        
        Args:
            tool_name: 工具名称
        """
        self._retry_counts[tool_name] = 0
        # 更新长期记忆中的成功记录
        if self.memory and self.state.last_error:
            try:
                conn = self.memory.conn
                conn.execute(
                    """
                    UPDATE tool_retries 
                    SET success = 1 
                    WHERE tool_name = ? AND timestamp = (
                        SELECT MAX(timestamp) FROM tool_retries WHERE tool_name = ?
                    )
                    """,
                    (tool_name, tool_name),
                )
                conn.commit()
            except Exception as e:
                logger.warning(f"Failed to update retry success in memory: {e}")

    def _adjust_params_for_error(self, error_type: ErrorType, original_params: dict[str, Any]) -> dict[str, Any]:
        """根据错误类型调整参数 - 复用基础设施层的 generate_adjusted_params.
        
        Args:
            error_type: 错误类型
            original_params: 原始参数
            
        Returns:
            调整后的参数字典
        """
        # 直接调用基础设施层的函数，传入空工具名（因为这里不需要工具特定的逻辑）
        return generate_adjusted_params(error_type, "", original_params)


    def _record_retry_to_memory(
        self,
        tool_name: str,
        error_type: ErrorType,
        original_params: dict[str, Any],
        adjusted_params: dict[str, Any],
        attempt_count: int,
        success: bool,
    ) -> None:
        """记录重试尝试到长期记忆.
        
        Args:
            tool_name: 工具名称
            error_type: 错误类型
            original_params: 原始参数
            adjusted_params: 调整后参数
            attempt_count: 尝试次数
            success: 是否成功
        """
        try:
            # 确保 tool_retries 表存在
            conn = self.memory.conn
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_retries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_name TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    original_params TEXT,
                    adjusted_params TEXT,
                    attempt_count INTEGER DEFAULT 1,
                    success INTEGER DEFAULT 0,
                    timestamp TEXT NOT NULL
                )
            """
            )
            conn.commit()

            record = RetryRecord(
                tool_name=tool_name,
                error_type=error_type.value,
                original_params=original_params,
                adjusted_params=adjusted_params,
                attempt_count=attempt_count,
                success=success,
            )

            conn.execute(
                """
                INSERT INTO tool_retries
                (tool_name, error_type, original_params, adjusted_params, attempt_count, success, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.tool_name,
                    record.error_type,
                    json.dumps(record.original_params, ensure_ascii=False, default=str),
                    json.dumps(record.adjusted_params, ensure_ascii=False, default=str),
                    record.attempt_count,
                    1 if record.success else 0,
                    record.timestamp,
                ),
            )
            conn.commit()
            logger.debug(f"Recorded retry to memory: {tool_name}")
        except Exception as e:
            # 记录失败不影响主流程
            logger.warning(f"Failed to record retry to memory: {e}")


# 全局重试管理器实例
_retry_manager_instance: RetryManager | None = None


def get_retry_manager(config: RetryConfig | None = None, memory: GraphDatabaseMemory | None = None) -> RetryManager:
    """获取全局重试管理器实例（单例模式）.
    
    Args:
        config: 重试配置
        memory: 长期记忆实例
        
    Returns:
        RetryManager 实例
    """
    global _retry_manager_instance
    if _retry_manager_instance is None:
        _retry_manager_instance = RetryManager(config=config, memory=memory)
    return _retry_manager_instance
