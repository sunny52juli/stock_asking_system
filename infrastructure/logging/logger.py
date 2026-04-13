"""日志模块 - 提供统一的日志配置和管理."""

import logging
import sys
from pathlib import Path
from typing import Any

# 日志格式
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
SIMPLE_FORMAT = "%(levelname)s - %(message)s"
DETAILED_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"

# 全局日志配置
_configured = False
_log_level = logging.INFO
_log_file: Path | None = None


def configure_logging(
    level: str = "INFO",
    log_file: str | None = None,
    format_style: str = "default"
) -> None:
    """配置全局日志系统.

    Args:
        level: 日志级别 ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        log_file: 日志文件路径（可选）
        format_style: 格式风格 ('default', 'simple', 'detailed')
    """
    global _configured, _log_level, _log_file

    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    
    _log_level = level_map.get(level.upper(), logging.INFO)
    _log_file = Path(log_file) if log_file else None

    # 选择格式
    if format_style == "simple":
        log_format = SIMPLE_FORMAT
    elif format_style == "detailed":
        log_format = DETAILED_FORMAT
    else:
        log_format = DEFAULT_FORMAT

    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(_log_level)

    # 清除现有处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 添加控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(_log_level)
    console_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(console_handler)

    # 如果指定了日志文件，添加文件处理器
    if _log_file:
        _log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(_log_file, encoding="utf-8")
        file_handler.setLevel(_log_level)
        file_handler.setFormatter(logging.Formatter(DETAILED_FORMAT))
        root_logger.addHandler(file_handler)

    _configured = True


def get_logger(name: str = None) -> logging.Logger:
    """获取日志记录器.
    
    Args:
        name: 日志记录器名称（通常是 __name__）
        
    Returns:
        配置好的 Logger 实例
    """
    global _configured

    if not _configured:
        configure_logging()

    logger = logging.getLogger(name)

    # 确保日志器有正确的级别
    if logger.level == logging.NOTSET:
        logger.setLevel(_log_level)

    return logger


class LoggerMixin:
    """日志混入类 - 可以混入到任何类中，提供 self.logger 属性."""

    @property
    def logger(self) -> logging.Logger:
        """获取类专属的日志器"""
        if not hasattr(self, "_logger"):
            self._logger = get_logger(self.__class__.__name__)
        return self._logger
