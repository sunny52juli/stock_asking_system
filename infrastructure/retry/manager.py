"""智能重试管理器 - 自动分析错误类型并决定重试策略."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class ErrorType(Enum):
    """错误类型枚举."""
    PARAMETER_VALIDATION = "parameter_validation"  # 参数验证失败
    TIMEOUT = "timeout"  # 超时
    NO_RESULTS = "no_results"  # 无结果
    CONFIG_ERROR = "config_error"  # 配置错误
    PERMISSION_DENIED = "permission_denied"  # 权限不足
    UNKNOWN = "unknown"  # 未知错误


@dataclass
class RetryRecord:
    """重试记录."""
    tool_name: str
    error_type: str
    original_params: dict[str, Any]
    adjusted_params: dict[str, Any]
    attempt_count: int
    success: bool
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# 最大重试次数
MAX_RETRY_COUNT = 3

# 可重试的错误类型
RETRYABLE_ERRORS = {
    ErrorType.PARAMETER_VALIDATION,
    ErrorType.TIMEOUT,
    ErrorType.NO_RESULTS,
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
        r"参数.*无效",
        r"参数.*验证.*失败",
    ],
    ErrorType.TIMEOUT: [
        r"timeout",
        r"timed?\s*out",
        r"超时",
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
        r"配置.*错误",
    ],
    ErrorType.PERMISSION_DENIED: [
        r"permission\s+denied",
        r"unauthorized",
        r"forbidden",
        r"权限.*不足",
    ],
}


def classify_error(error: Exception | str) -> ErrorType:
    """分类错误类型."""
    error_str = str(error).lower()

    for error_type, patterns in ERROR_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, error_str, re.IGNORECASE):
                return error_type

    return ErrorType.UNKNOWN


def adjust_numeric_param(value: Any, operator: str, factor: float) -> Any:
    """调整数值参数."""
    if not isinstance(value, (int, float)):
        return value

    if operator == "increase":
        return value * factor
    elif operator == "decrease":
        return value / factor
    return value


def generate_adjusted_params(
    error_type: ErrorType,
    tool_name: str,
    original_params: dict[str, Any],
) -> dict[str, Any]:
    """生成调整后的参数."""
    adjusted = original_params.copy()

    if error_type == ErrorType.PARAMETER_VALIDATION:
        # 参数验证失败：放宽数值范围
        if "top_n" in adjusted:
            adjusted["top_n"] = adjust_numeric_param(adjusted["top_n"], "increase", 2.0)
        if "threshold" in adjusted:
            adjusted["threshold"] = adjust_numeric_param(adjusted["threshold"], "decrease", 2.0)

    elif error_type == ErrorType.TIMEOUT:
        # 超时：缩小数据范围
        if "days" in adjusted:
            adjusted["days"] = max(30, int(adjusted["days"] * 0.5))
        if "limit" in adjusted:
            adjusted["limit"] = max(10, int(adjusted["limit"] * 0.5))

    elif error_type == ErrorType.NO_RESULTS:
        # 无结果：放宽条件
        if "top_n" in adjusted:
            adjusted["top_n"] = adjust_numeric_param(adjusted["top_n"], "increase", 2.0)
        if "min_score" in adjusted:
            adjusted["min_score"] = adjust_numeric_param(adjusted["min_score"], "decrease", 2.0)

    return adjusted


def should_retry(
    error: Exception | str,
    tool_name: str,
    attempt_count: int,
) -> bool:
    """判断是否应该重试."""
    # 硬限制：最大重试次数
    if attempt_count >= MAX_RETRY_COUNT:
        return False

    # 分类错误类型
    error_type = classify_error(error)

    # 不可重试的错误类型
    if error_type in NON_RETRYABLE_ERRORS:
        return False

    # 可重试的错误类型
    if error_type in RETRYABLE_ERRORS:
        return True

    # 未知错误：保守起见不重试
    return False


class RetryManager:
    """重试管理器."""

    def __init__(self):
        self._retry_counts: dict[str, int] = {}
        self._retry_history: list[RetryRecord] = []

    def check_and_prepare_retry(
        self,
        error: Exception,
        tool_name: str,
        params: dict[str, Any],
    ) -> tuple[bool, dict[str, Any]]:
        """检查并准备重试.

        Returns:
            (should_retry, adjusted_params)
        """
        attempt_count = self._retry_counts.get(tool_name, 0)

        if not should_retry(error, tool_name, attempt_count):
            return False, params

        # 分类错误
        error_type = classify_error(error)
        logger.info(f"🔄 检测到错误类型：{error_type.value}，准备第 {attempt_count + 1} 次重试")

        # 生成调整后的参数
        adjusted_params = generate_adjusted_params(error_type, tool_name, params)

        # 记录重试
        self._retry_counts[tool_name] = attempt_count + 1

        record = RetryRecord(
            tool_name=tool_name,
            error_type=error_type.value,
            original_params=params,
            adjusted_params=adjusted_params,
            attempt_count=attempt_count + 1,
            success=False,  # 将在后续更新
        )
        self._retry_history.append(record)

        return True, adjusted_params

    def record_success(self, tool_name: str):
        """记录成功."""
        self._retry_counts[tool_name] = 0

    def get_retry_stats(self) -> dict[str, Any]:
        """获取重试统计."""
        total = len(self._retry_history)
        by_tool = {}
        by_error_type = {}
        
        for record in self._retry_history:
            by_tool[record.tool_name] = by_tool.get(record.tool_name, 0) + 1
            by_error_type[record.error_type] = by_error_type.get(record.error_type, 0) + 1
        
        return {
            "total_retries": total,
            "by_tool": by_tool,
            "by_error_type": by_error_type,
        }

    def reset(self):
        """重置重试计数器."""
        self._retry_counts.clear()
        self._retry_history.clear()


# 全局单例
_retry_manager_instance: RetryManager | None = None


def get_retry_manager() -> RetryManager:
    """获取全局重试管理器实例."""
    global _retry_manager_instance
    if _retry_manager_instance is None:
        _retry_manager_instance = RetryManager()
    return _retry_manager_instance
