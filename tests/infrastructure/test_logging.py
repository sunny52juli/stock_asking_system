"""日志模块测试."""

import logging
import pytest
from pathlib import Path
import tempfile

from infrastructure.logging.logger import (
    get_logger,
    configure_logging,
    LoggerMixin,
    DEFAULT_FORMAT,
    SIMPLE_FORMAT,
    DETAILED_FORMAT,
)


class TestGetLogger:
    """测试 get_logger 函数."""

    def test_get_logger_returns_logger(self):
        """测试返回 Logger 实例."""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_with_name_none(self):
        """测试 name 为 None 的情况."""
        logger = get_logger(None)
        assert isinstance(logger, logging.Logger)

    def test_get_logger_auto_configures(self):
        """测试自动配置日志系统."""
        # 重置全局状态
        import infrastructure.logging.logger as log_module
        log_module._configured = False
        
        logger = get_logger("auto_test")
        assert log_module._configured is True

    def test_get_logger_sets_level(self):
        """测试日志级别设置."""
        import infrastructure.logging.logger as log_module
        log_module._configured = False
        log_module._log_level = logging.DEBUG
        
        configure_logging(level="DEBUG")
        logger = get_logger("level_test")
        assert logger.level == logging.DEBUG


class TestConfigureLogging:
    """测试 configure_logging 函数."""

    def setup_method(self):
        """每个测试前重置状态."""
        import infrastructure.logging.logger as log_module
        log_module._configured = False
        # 清除根日志器的处理器
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

    def test_configure_default(self):
        """测试默认配置."""
        configure_logging()
        
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) >= 1  # 至少有控制台处理器

    def test_configure_debug_level(self):
        """测试 DEBUG 级别配置."""
        configure_logging(level="DEBUG")
        
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_configure_warning_level(self):
        """测试 WARNING 级别配置."""
        configure_logging(level="WARNING")
        
        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING

    def test_configure_simple_format(self):
        """测试简单格式配置."""
        configure_logging(format_style="simple")
        
        root_logger = logging.getLogger()
        handler = root_logger.handlers[0]
        formatter = handler.formatter
        assert formatter._fmt == SIMPLE_FORMAT

    def test_configure_detailed_format(self):
        """测试详细格式配置."""
        configure_logging(format_style="detailed")
        
        root_logger = logging.getLogger()
        handler = root_logger.handlers[0]
        formatter = handler.formatter
        assert formatter._fmt == DETAILED_FORMAT

    def test_configure_with_log_file(self):
        """测试文件日志配置."""
        import time
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            configure_logging(log_file=str(log_file))
            
            # 等待文件创建
            time.sleep(0.1)
            assert log_file.exists()
            
            root_logger = logging.getLogger()
            # 应该有控制台和文件两个处理器
            assert len(root_logger.handlers) >= 2
            
            # 关闭文件处理器以释放文件句柄
            for handler in root_logger.handlers[:]:
                if hasattr(handler, 'baseFilename'):
                    handler.close()
                    root_logger.removeHandler(handler)

    def test_configure_clears_existing_handlers(self):
        """测试清除现有处理器."""
        root_logger = logging.getLogger()
        root_logger.addHandler(logging.StreamHandler())
        initial_count = len(root_logger.handlers)
        
        configure_logging()
        
        # 应该清除了旧处理器并添加了新处理器
        assert len(root_logger.handlers) < initial_count + 2


class TestLoggerMixin:
    """测试 LoggerMixin 类."""

    def test_mixin_provides_logger(self):
        """测试混入类提供 logger 属性."""
        class MyClass(LoggerMixin):
            pass
        
        obj = MyClass()
        assert hasattr(obj, "logger")
        assert isinstance(obj.logger, logging.Logger)
        assert obj.logger.name == "MyClass"

    def test_mixin_logger_cached(self):
        """测试 logger 被缓存."""
        class MyClass(LoggerMixin):
            pass
        
        obj = MyClass()
        logger1 = obj.logger
        logger2 = obj.logger
        assert logger1 is logger2

    def test_mixin_different_classes(self):
        """测试不同类有不同的 logger."""
        class ClassA(LoggerMixin):
            pass
        
        class ClassB(LoggerMixin):
            pass
        
        obj_a = ClassA()
        obj_b = ClassB()
        
        assert obj_a.logger.name == "ClassA"
        assert obj_b.logger.name == "ClassB"
        assert obj_a.logger is not obj_b.logger


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
