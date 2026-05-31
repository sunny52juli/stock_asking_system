"""日志助手 - 提供便捷的日志记录包装函数.

统一日志格式，简化日志调用。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ==================== 日志级别前缀常量 ====================

LOG_PREFIX_SUCCESS = "[OK]"
LOG_PREFIX_WARNING = "[WARN]"
LOG_PREFIX_ERROR = "[ERROR]"
LOG_PREFIX_INFO = "[INFO]"
LOG_PREFIX_DEBUG = "[DEBUG]"


def log_success(message: str, *args: Any, logger_obj: logging.Logger | None = None):
    """记录成功日志.
    
    Args:
        message: 日志消息
        *args: 格式化参数
        logger_obj: 自定义 logger 对象，默认使用当前模块的 logger
    
    Example:
        >>> log_success("数据加载完成")
        [OK] 数据加载完成
    """
    target_logger = logger_obj or logger
    target_logger.info(f"{LOG_PREFIX_SUCCESS} {message}", *args)


def log_warning(message: str, *args: Any, logger_obj: logging.Logger | None = None):
    """记录警告日志.
    
    Args:
        message: 日志消息
        *args: 格式化参数
        logger_obj: 自定义 logger 对象，默认使用当前模块的 logger
    
    Example:
        >>> log_warning("缓存未命中，重新加载")
        [WARN] 缓存未命中，重新加载
    """
    target_logger = logger_obj or logger
    target_logger.warning(f"{LOG_PREFIX_WARNING} {message}", *args)


def log_error(message: str, *args: Any, exc_info: bool = False, 
              logger_obj: logging.Logger | None = None):
    """记录错误日志.
    
    Args:
        message: 日志消息
        *args: 格式化参数
        exc_info: 是否包含异常堆栈信息
        logger_obj: 自定义 logger 对象，默认使用当前模块的 logger
    
    Example:
        >>> log_error("数据处理失败", exc_info=True)
        [ERROR] 数据处理失败
        Traceback (most recent call last):
        ...
    """
    target_logger = logger_obj or logger
    target_logger.error(f"{LOG_PREFIX_ERROR} {message}", *args, exc_info=exc_info)


def log_info(message: str, *args: Any, logger_obj: logging.Logger | None = None):
    """记录信息日志.
    
    Args:
        message: 日志消息
        *args: 格式化参数
        logger_obj: 自定义 logger 对象，默认使用当前模块的 logger
    
    Example:
        >>> log_info("开始处理数据")
        [INFO] 开始处理数据
    """
    target_logger = logger_obj or logger
    target_logger.info(f"{LOG_PREFIX_INFO} {message}", *args)


def log_debug(message: str, *args: Any, logger_obj: logging.Logger | None = None):
    """记录调试日志.
    
    Args:
        message: 日志消息
        *args: 格式化参数
        logger_obj: 自定义 logger 对象，默认使用当前模块的 logger
    
    Example:
        >>> log_debug("变量值: x=%d", x)
        [DEBUG] 变量值: x=42
    """
    target_logger = logger_obj or logger
    target_logger.debug(f"{LOG_PREFIX_DEBUG} {message}", *args)


def log_section(title: str, char: str = "=", width: int = 70, 
                logger_obj: logging.Logger | None = None):
    """记录分段标题（用于日志分隔）.
    
    Args:
        title: 标题文本
        char: 分隔符字符
        width: 总宽度
        logger_obj: 自定义 logger 对象
    
    Example:
        >>> log_section("数据处理开始")
        ======================================================================
        数据处理开始
        ======================================================================
    """
    target_logger = logger_obj or logger
    separator = char * width
    target_logger.info(separator)
    target_logger.info(title)
    target_logger.info(separator)


def log_step(step_num: int, total_steps: int, description: str,
             logger_obj: logging.Logger | None = None):
    """记录步骤进度.
    
    Args:
        step_num: 当前步骤编号（从1开始）
        total_steps: 总步骤数
        description: 步骤描述
        logger_obj: 自定义 logger 对象
    
    Example:
        >>> log_step(1, 3, "加载数据")
        [步骤 1/3] 加载数据
    """
    target_logger = logger_obj or logger
    target_logger.info(f"[步骤 {step_num}/{total_steps}] {description}")
