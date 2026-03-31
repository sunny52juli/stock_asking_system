#!/usr/bin/env python3
"""
自定义异常类 - 量化系统异常层次结构

解决问题：
- 项目中异常处理过于笼统，使用 Exception 捕获所有错误
- 缺乏自定义异常类，难以区分不同类型的错误

使用方法：
    from utils.exceptions import DataLoadError, FactorCalculationError

    try:
        data = load_data()
    except DataLoadError as e:
        logger.error(f"数据加载失败: {e}")
"""


class QuantSystemError(Exception):
    """
    量化系统基础异常类

    所有自定义异常的基类，用于统一捕获系统错误。
    """

    def __init__(self, message: str = "", details: dict = None):
        """
        初始化异常

        Args:
            message: 错误消息
            details: 额外的错误详情（可选）
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | 详情: {self.details}"
        return self.message


# ==================== 数据相关异常 ====================

class DataError(QuantSystemError):
    """数据相关错误的基类"""
    pass


class DataLoadError(DataError):
    """
    数据加载错误

    当数据加载失败时抛出，例如：
    - 本地数据文件不存在
    - 数据格式错误
    - 日期范围内无数据
    """
    pass


class DataValidationError(DataError):
    """
    数据验证错误

    当数据验证失败时抛出，例如：
    - 必要字段缺失
    - 数据类型不正确
    - 数据范围异常
    """
    pass


class StockPoolError(DataError):
    """
    股票池错误

    当股票池获取或筛选失败时抛出
    """
    pass


# ==================== 因子相关异常 ====================

class FactorError(QuantSystemError):
    """因子相关错误的基类"""
    pass


class FactorCalculationError(FactorError):
    """
    因子计算错误

    当因子计算失败时抛出，例如：
    - 因子表达式解析失败
    - 计算过程中出现异常
    - 结果包含无效值
    """
    pass


class FactorBacktestError(FactorError):
    """
    因子回测错误

    当因子回测失败时抛出
    """
    pass


class FactorScriptError(FactorError):
    """
    因子脚本错误

    当因子脚本生成或执行失败时抛出
    """
    pass


# ==================== 配置相关异常 ====================

class ConfigError(QuantSystemError):
    """配置相关错误的基类"""
    pass


class APIConfigError(ConfigError):
    """
    API配置错误

    当API配置缺失或无效时抛出
    """
    pass


class MissingAPIKeyError(APIConfigError):
    """
    API密钥缺失错误

    当必要的API密钥未配置时抛出
    """

    def __init__(self, key_name: str = "DEFAULT_API_KEY"):
        super().__init__(
            f"未检测到API密钥，请在 .env 文件中设置 {key_name}",
            details={"key_name": key_name}
        )


# ==================== 筛选相关异常 ====================

class ScreeningError(QuantSystemError):
    """筛选相关错误的基类"""
    pass


class ScreeningLogicError(ScreeningError):
    """
    筛选逻辑错误

    当筛选逻辑生成或执行失败时抛出
    """
    pass


class ToolExecutionError(ScreeningError):
    """
    工具执行错误

    当MCP工具执行失败时抛出
    """
    pass


# ==================== LLM相关异常 ====================

class LLMError(QuantSystemError):
    """LLM相关错误的基类"""
    pass


class LLMResponseError(LLMError):
    """
    LLM响应错误

    当LLM返回无效响应时抛出
    """
    pass


class LLMParseError(LLMError):
    """
    LLM解析错误

    当无法解析LLM返回的内容时抛出（如JSON解析失败）
    """
    pass
