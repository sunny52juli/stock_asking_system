"""统一错误处理 - 量化系统错误码和异常体系."""

from __future__ import annotations

from enum import IntEnum
from typing import Any, Optional


class ErrorCode(IntEnum):
    """错误码定义.
    
    格式: XXXX
    - 1xxx: 数据相关错误
    - 2xxx: 工具执行错误
    - 3xxx: 筛选引擎错误
    - 4xxx: Agent 相关错误
    - 5xxx: 配置错误
    """
    
    # 数据相关 (1xxx)
    DATA_NOT_FOUND = 1001
    DATA_FORMAT_ERROR = 1002
    DATA_LOADING_FAILED = 1003
    INDEX_DATA_MISSING = 1004
    
    # 工具执行 (2xxx)
    TOOL_NOT_FOUND = 2001
    TOOL_PARAM_ERROR = 2002
    TOOL_EXECUTION_FAILED = 2003
    
    # 筛选引擎 (3xxx)
    SCREENING_FAILED = 3001
    EXPRESSION_EVAL_ERROR = 3002
    NO_VALID_STOCKS = 3003
    
    # Agent 相关 (4xxx)
    AGENT_TIMEOUT = 4001
    AGENT_MAX_RETRIES = 4002
    AGENT_INVALID_RESPONSE = 4003
    
    # 配置错误 (5xxx)
    CONFIG_MISSING = 5001
    CONFIG_INVALID = 5002


class QuantError(Exception):
    """量化系统基础异常类.
    
    Attributes:
        code: 错误码
        message: 错误消息
        details: 详细错误信息（可选）
    """
    
    def __init__(
        self,
        code: ErrorCode | int,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ):
        self.code = code if isinstance(code, int) else code.value
        self.message = message
        self.details = details or {}
        
        super().__init__(f"[{self.code}] {message}")
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式（用于 JSON 序列化）."""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


# ==================== 具体异常类 ====================

class DataError(QuantError):
    """数据相关错误."""
    pass


class ToolError(QuantError):
    """工具执行错误."""
    pass


class ScreeningError(QuantError):
    """筛选引擎错误."""
    pass


class AgentError(QuantError):
    """Agent 相关错误."""
    pass


class ConfigError(QuantError):
    """配置错误."""
    pass


# ==================== 便捷函数 ====================

def handle_error(error: Exception, context: str = "") -> QuantError:
    """将普通异常转换为 QuantError.
    
    Args:
        error: 原始异常
        context: 错误上下文
        
    Returns:
        QuantError 实例
    """
    if isinstance(error, QuantError):
        return error
    
    # 根据异常类型映射到对应的错误码
    error_map = {
        FileNotFoundError: (ErrorCode.DATA_NOT_FOUND, "数据文件不存在"),
        KeyError: (ErrorCode.DATA_FORMAT_ERROR, "数据格式错误"),
        ValueError: (ErrorCode.TOOL_PARAM_ERROR, "参数错误"),
        ImportError: (ErrorCode.TOOL_NOT_FOUND, "模块导入失败"),
    }
    
    error_type = type(error)
    if error_type in error_map:
        code, default_msg = error_map[error_type]
        message = f"{context}: {default_msg} - {str(error)}" if context else f"{default_msg} - {str(error)}"
        return QuantError(code, message, {"original_error": str(error)})
    
    # 默认错误
    message = f"{context}: {str(error)}" if context else str(error)
    return QuantError(ErrorCode.TOOL_EXECUTION_FAILED, message, {"original_error": str(error)})


def format_error_response(error: QuantError | Exception) -> dict[str, Any]:
    """格式化错误响应.
    
    Args:
        error: 异常对象
        
    Returns:
        标准化的错误响应字典
    """
    if isinstance(error, QuantError):
        return {
            "status": "error",
            "error": error.to_dict(),
        }
    
    # 普通异常
    quant_error = handle_error(error)
    return {
        "status": "error",
        "error": quant_error.to_dict(),
    }
