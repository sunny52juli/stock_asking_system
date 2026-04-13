"""配置模块测试."""

import pytest
from pathlib import Path

from infrastructure.config.settings import (
    get_settings,
    Settings,
    LLMConfig,
    DataConfig,
    BacktestConfig,
)


class TestSettings:
    """测试配置类."""

    def test_get_settings_returns_instance(self):
        """测试获取配置实例."""
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_singleton(self):
        """测试配置单例模式."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_llm_config_defaults(self):
        """测试 LLM 配置默认值."""
        settings = get_settings()
        assert hasattr(settings, "llm")
        assert isinstance(settings.llm, LLMConfig)

    def test_data_config_defaults(self):
        """测试数据配置默认值."""
        settings = get_settings()
        assert hasattr(settings, "data")
        assert isinstance(settings.data, DataConfig)

    def test_backtest_config_defaults(self):
        """测试回测配置默认值."""
        settings = get_settings()
        assert hasattr(settings, "backtest")
        assert isinstance(settings.backtest, BacktestConfig)

    def test_observation_days_default(self):
        """测试观察期默认值."""
        settings = get_settings()
        assert hasattr(settings, "observation_days")
        assert isinstance(settings.observation_days, int)
        assert settings.observation_days > 0


class TestLLMConfig:
    """测试 LLM 配置."""

    def test_llm_config_creation(self):
        """测试创建 LLM 配置."""
        config = LLMConfig()
        assert hasattr(config, "api_key")
        assert hasattr(config, "api_url")
        assert hasattr(config, "model")

    def test_llm_config_with_values(self):
        """测试带值的 LLM 配置."""
        config = LLMConfig(
            api_key="test_key",
            api_url="http://test.com/v1",
            model="gpt-4"
        )
        assert config.api_key == "test_key"
        assert config.api_url == "http://test.com/v1"
        assert config.model == "gpt-4"

    def test_llm_config_to_dict(self):
        """测试转换为字典（base_url 映射）."""
        config = LLMConfig(api_url="http://test.com/v1")
        d = config.to_dict()
        assert "base_url" in d
        assert d["base_url"] == "http://test.com/v1"


class TestDataConfig:
    """测试数据配置."""

    def test_data_config_creation(self):
        """测试创建数据配置."""
        config = DataConfig()
        assert hasattr(config, "cache_root")

    def test_data_config_cache_root(self):
        """测试缓存目录配置."""
        config = DataConfig(cache_root=Path("/tmp/test_cache"))
        assert config.cache_root == Path("/tmp/test_cache")


class TestBacktestConfig:
    """测试回测配置."""

    def test_backtest_config_creation(self):
        """测试创建回测配置."""
        config = BacktestConfig()
        assert hasattr(config, "holding_periods")

    def test_backtest_config_holding_periods(self):
        """测试持仓周期配置."""
        config = BacktestConfig(holding_periods=[5, 10, 20])
        assert config.holding_periods == [5, 10, 20]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
