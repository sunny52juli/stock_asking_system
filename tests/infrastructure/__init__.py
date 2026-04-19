"""Infrastructure 模块测试套件."""

import pytest


from infrastructure.config.settings import get_settings
from infrastructure.errors.exceptions import QuantSystemError, DataError
from infrastructure.logging.logger import get_logger, configure_logging, LoggerMixin
def test_infrastructure_imports():
    """测试 infrastructure 模块导入."""
    
    assert callable(get_logger)
    assert callable(configure_logging)
    assert LoggerMixin is not None
    assert issubclass(QuantSystemError, Exception)
    assert issubclass(DataError, QuantSystemError)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
