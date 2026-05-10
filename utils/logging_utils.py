"""日志工具 - 通用日志功能."""

from __future__ import annotations

import logging


class LoggerMixin:
    """日志混入类 - 可以混入到任何类中，提供 self.logger 属性."""

    @property
    def logger(self) -> logging.Logger:
        """获取类专属的日志器"""
        if not hasattr(self, "_logger"):
            self._logger = logging.getLogger(self.__class__.__name__)
        return self._logger
