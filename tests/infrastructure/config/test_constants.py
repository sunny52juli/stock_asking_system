"""测试配置常量."""

import pytest
from infrastructure.config.constants import (
    # 环境变量键名
    ENV_DEFAULT_MODEL, ENV_DEFAULT_API_KEY, ENV_DEFAULT_API_URL,
    # 默认值常量
    DEFAULT_LLM_MODEL, DEFAULT_LLM_API_URL, DEFAULT_LLM_TEMPERATURE,
    # 错误码
    ERR_DATA_NOT_FOUND, ERR_TOOL_NOT_FOUND, ERR_SCREENING_FAILED,
    # HTTP状态码
    HTTP_OK, HTTP_BAD_REQUEST, HTTP_NOT_FOUND,
)


class TestConfigConstants:
    """测试配置常量定义."""
    
    def test_env_var_constants(self):
        """测试环境变量键名常量."""
        assert ENV_DEFAULT_MODEL == "DEFAULT_MODEL"
        assert ENV_DEFAULT_API_KEY == "DEFAULT_API_KEY"
        assert ENV_DEFAULT_API_URL == "DEFAULT_API_URL"
    
    def test_llm_default_constants(self):
        """测试LLM默认值常量."""
        assert DEFAULT_LLM_MODEL == "deepseek-chat"
        assert DEFAULT_LLM_API_URL == "https://api.deepseek.com/v1"
        assert DEFAULT_LLM_TEMPERATURE == 0.7
    
    def test_error_code_constants(self):
        """测试错误码常量."""
        assert ERR_DATA_NOT_FOUND == 1001
        assert ERR_TOOL_NOT_FOUND == 2001
        assert ERR_SCREENING_FAILED == 3001
    
    def test_http_status_constants(self):
        """测试HTTP状态码常量."""
        assert HTTP_OK == 200
        assert HTTP_BAD_REQUEST == 400
        assert HTTP_NOT_FOUND == 404
    
    def test_constants_are_strings_or_ints(self):
        """测试常量类型正确."""
        assert isinstance(ENV_DEFAULT_MODEL, str)
        assert isinstance(ERR_DATA_NOT_FOUND, int)
        assert isinstance(DEFAULT_LLM_TEMPERATURE, float)


class TestSettingsWithConstants:
    """测试设置类使用常量."""
    
    def test_settings_import_constants(self):
        """测试settings模块导入了常量."""
        from infrastructure.config.settings import Settings
        
        settings = Settings()
        
        # 验证默认值来自常量
        assert settings.llm.model == DEFAULT_LLM_MODEL
        assert settings.llm.temperature == DEFAULT_LLM_TEMPERATURE
        assert settings.observation_days == 80  # DEFAULT_OBSERVATION_DAYS
    
    def test_settings_backtest_defaults(self):
        """测试回测配置默认值."""
        from infrastructure.config.settings import Settings
        from infrastructure.config.constants import DEFAULT_HOLDING_PERIODS
        
        settings = Settings()
        assert settings.backtest.holding_periods == DEFAULT_HOLDING_PERIODS
    
    def test_settings_stock_pool_defaults(self):
        """测试股票池配置默认值."""
        from infrastructure.config.settings import Settings
        from infrastructure.config.constants import DEFAULT_MIN_LIST_DAYS, DEFAULT_EXCLUDE_ST
        
        settings = Settings()
        assert settings.stock_pool.min_list_days == DEFAULT_MIN_LIST_DAYS
        assert settings.stock_pool.exclude_st == DEFAULT_EXCLUDE_ST
