"""错误重试管理器 - 智能错误分类和参数调整.

- 6种错误类型分类（增强版）
- 自动参数调整策略（支持筛选条件自适应）
- 最大重试次数控制
- 重试历史持久化到长期记忆
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.agent.memory.long_term import LongTermMemory

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """错误类型枚举."""

    PARAMETER_VALIDATION = "parameter_validation"  # 参数验证失败
    TIMEOUT_ERROR = "timeout_error"                # 超时错误
    NO_RESULTS = "no_results"                      # 无结果
    CONFIG_ERROR = "config_error"                  # 配置错误
    PERMISSION_DENIED = "permission_denied"        # 权限不足
    TOOL_EXECUTION_ERROR = "tool_execution_error"  # 工具执行错误
    DATA_LOADING_ERROR = "data_loading_error"      # 数据加载错误
    LLM_API_ERROR = "llm_api_error"                # LLM API 错误
    VALIDATION_ERROR = "validation_error"          # 验证错误
    UNKNOWN_ERROR = "unknown_error"                # 未知错误


# 最大重试次数硬限制
MAX_RETRY_COUNT = 3

# 可重试的错误类型
RETRYABLE_ERRORS = {
    ErrorType.PARAMETER_VALIDATION,
    ErrorType.TIMEOUT_ERROR,
    ErrorType.NO_RESULTS,
    ErrorType.TOOL_EXECUTION_ERROR,
    ErrorType.LLM_API_ERROR,
}

# 不可重试的错误类型
NON_RETRYABLE_ERRORS = {
    ErrorType.CONFIG_ERROR,
    ErrorType.PERMISSION_DENIED,
}

# 错误模式匹配规则
ERROR_PATTERNS = {
    ErrorType.PARAMETER_VALIDATION: [
        r"invalid\s+parameter",
        r"parameter\s+validation\s+failed",
        r"value\s+out\s+of\s+range",
        r"invalid\s+value",
        r"参数.*无效",
        r"参数.*验证.*失败",
        r"值.*超出.*范围",
    ],
    ErrorType.TIMEOUT_ERROR: [
        r"timeout",
        r"timed?\s*out",
        r"超时",
        r"execution\s+time\s+exceeded",
    ],
    ErrorType.NO_RESULTS: [
        r"no\s+results?",
        r"empty\s+result",
        r"无结果",
        r"结果为空",
        r"未找到.*股票",
    ],
    ErrorType.CONFIG_ERROR: [
        r"config(uration)?\s+error",
        r"invalid\s+config",
        r"missing\s+config",
        r"配置.*错误",
        r"配置.*无效",
    ],
    ErrorType.PERMISSION_DENIED: [
        r"permission\s+denied",
        r"unauthorized",
        r"forbidden",
        r"access\s+denied",
        r"权限.*不足",
        r"无权.*访问",
    ],
}


@dataclass
class RetryRecord:
    """重试记录 - 用于持久化到长期记忆."""

    tool_name: str
    error_type: str
    original_params: dict[str, Any]
    adjusted_params: dict[str, Any]
    attempt_count: int
    success: bool
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


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
    last_error_type: ErrorType = ErrorType.UNKNOWN_ERROR
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

    def __init__(self, config: RetryConfig | None = None, memory: LongTermMemory | None = None):
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
        """分类错误类型 - 增强版（支持正则模式匹配）.
        
        Args:
            error: 异常对象或错误消息字符串
            
        Returns:
            ErrorType 枚举值
        """
        error_str = str(error).lower()

        # 先尝试正则模式匹配（更精确）
        for error_type, patterns in ERROR_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, error_str, re.IGNORECASE):
                    return error_type

        # 回退到关键词匹配
        # 工具执行错误
        if any(keyword in error_str for keyword in ["tool", "execution", "invoke"]):
            return ErrorType.TOOL_EXECUTION_ERROR

        # 数据加载错误
        if any(keyword in error_str for keyword in ["data", "load", "fetch", "download"]):
            return ErrorType.DATA_LOADING_ERROR

        # LLM API 错误
        if any(keyword in error_str for keyword in ["api", "rate limit", "quota", "openai", "deepseek"]):
            return ErrorType.LLM_API_ERROR

        # 验证错误
        if any(keyword in error_str for keyword in ["validation", "invalid", "format"]):
            return ErrorType.VALIDATION_ERROR

        # 超时错误
        if any(keyword in error_str for keyword in ["timeout", "timed out"]):
            return ErrorType.TIMEOUT_ERROR

        return ErrorType.UNKNOWN_ERROR

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
        """根据错误类型调整参数 - 增强版（支持筛选条件自适应）.
        
        Args:
            error_type: 错误类型
            original_params: 原始参数
            
        Returns:
            调整后的参数字典
        """
        adjusted = original_params.copy()

        if error_type == ErrorType.PARAMETER_VALIDATION:
            # 参数验证失败：放宽数值范围
            if "top_n" in adjusted:
                adjusted["top_n"] = self._adjust_numeric_param(adjusted["top_n"], "increase", 2.0)
            if "threshold" in adjusted:
                adjusted["threshold"] = self._adjust_numeric_param(adjusted["threshold"], "decrease", 2.0)
            if "min_value" in adjusted:
                adjusted["min_value"] = self._adjust_numeric_param(adjusted["min_value"], "decrease", 2.0)
            if "max_value" in adjusted:
                adjusted["max_value"] = self._adjust_numeric_param(adjusted["max_value"], "increase", 2.0)

            # 处理 screening_logic_json 中的条件
            if "screening_logic_json" in adjusted:
                try:
                    logic = json.loads(adjusted["screening_logic_json"])
                    conditions = logic.get("conditions", [])
                    for cond in conditions:
                        if "value" in cond:
                            operator = cond.get("operator", "")
                            if operator == ">":
                                # 放宽下限
                                cond["value"] = self._adjust_numeric_param(cond["value"], "decrease", 1.5)
                            elif operator == "<":
                                # 放宽上限
                                cond["value"] = self._adjust_numeric_param(cond["value"], "increase", 1.5)
                    adjusted["screening_logic_json"] = json.dumps(logic, ensure_ascii=False)
                except (json.JSONDecodeError, TypeError):
                    pass

        elif error_type == ErrorType.TIMEOUT_ERROR:
            # 超时：缩小数据范围
            if "days" in adjusted:
                adjusted["days"] = max(30, int(adjusted["days"] * 0.5))
            if "limit" in adjusted:
                adjusted["limit"] = max(10, int(adjusted["limit"] * 0.5))

        elif error_type == ErrorType.NO_RESULTS:
            # 无结果：放宽条件
            if "top_n" in adjusted:
                adjusted["top_n"] = self._adjust_numeric_param(adjusted["top_n"], "increase", 2.0)
            if "min_score" in adjusted:
                adjusted["min_score"] = self._adjust_numeric_param(adjusted["min_score"], "decrease", 2.0)

        elif error_type == ErrorType.LLM_API_ERROR:
            # API 错误：降低 temperature 提高稳定性
            if self.config.adjust_temperature:
                adjusted["temperature"] = 0.3

        elif error_type == ErrorType.TOOL_EXECUTION_ERROR:
            # 工具错误：稍微提高 temperature 增加多样性
            if self.config.adjust_temperature:
                adjusted["temperature"] = 0.9

        return adjusted

    @staticmethod
    def _adjust_numeric_param(value: Any, operator: str, factor: float) -> Any:
        """调整数值参数.
        
        Args:
            value: 原始值
            operator: 调整方向 (increase/decrease)
            factor: 调整因子
            
        Returns:
            调整后的值
        """
        if not isinstance(value, int | float):
            return value

        if operator == "increase":
            return value * factor
        elif operator == "decrease":
            return value / factor
        return value

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


def get_retry_manager(config: RetryConfig | None = None, memory: LongTermMemory | None = None) -> RetryManager:
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
