"""错误处理模块."""

from infrastructure.errors.exceptions import (
    QuantSystemError,
    DataError,
    DataLoadError,
    DataValidationError,
    StockPoolError,
    FactorError,
    FactorCalculationError,
    FactorBacktestError,
    FactorScriptError,
    ConfigError,
    APIConfigError,
    MissingAPIKeyError,
    ScreeningError,
    ScreeningLogicError,
    ToolExecutionError,
    AgentError,
    AgentInitializationError,
    AgentExecutionError,
    LLMError,
    LLMResponseError,
    LLMParseError,
)
from infrastructure.errors.error_handler import (
    ErrorCode,
    QuantError,
    handle_error,
    format_error_response,
)

__all__ = [
    # 原有异常类
    "QuantSystemError",
    "DataError",
    "DataLoadError",
    "DataValidationError",
    "StockPoolError",
    "FactorError",
    "FactorCalculationError",
    "FactorBacktestError",
    "FactorScriptError",
    "ConfigError",
    "APIConfigError",
    "MissingAPIKeyError",
    "ScreeningError",
    "ScreeningLogicError",
    "ToolExecutionError",
    "AgentError",
    "AgentInitializationError",
    "AgentExecutionError",
    "LLMError",
    "LLMResponseError",
    "LLMParseError",
    
    # 新增统一错误处理
    "ErrorCode",
    "QuantError",
    "handle_error",
    "format_error_response",
]
