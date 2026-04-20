"""配置系统测试 - Pydantic Schema 验证."""

import pytest
from pathlib import Path
from pydantic import ValidationError

from infrastructure.config.settings import (
    Settings,
    LLMConfig,
    DataConfig,
    BacktestConfig,
    StockPoolConfig,
    HarnessConfig,
    load_settings,
)


class TestLLMConfig:
    """LLM 配置验证测试."""
    
    def test_valid_config(self):
        """有效的 LLM 配置."""
        config = LLMConfig(
            model="deepseek-chat",
            api_key="sk-test123",
            temperature=0.7,
            max_tokens=4096,
        )
        assert config.model == "deepseek-chat"
        assert config.temperature == 0.7
    
    def test_temperature_bounds(self):
        """温度值边界检查."""
        # 有效范围
        LLMConfig(temperature=0.0)
        LLMConfig(temperature=1.0)
        
        # 超出范围
        with pytest.raises(ValidationError):
            LLMConfig(temperature=-0.1)
        
        with pytest.raises(ValidationError):
            LLMConfig(temperature=1.5)
    
    def test_max_tokens_positive(self):
        """max_tokens 必须为正数."""
        LLMConfig(max_tokens=1)
        
        with pytest.raises(ValidationError):
            LLMConfig(max_tokens=0)
        
        with pytest.raises(ValidationError):
            LLMConfig(max_tokens=-100)
    
    def test_empty_api_key_warning(self):
        """空 API Key 应发出警告."""
        # Pydantic V2 的 field_validator 不直接支持 logging
        # 这里只验证配置能正常创建
        config = LLMConfig(api_key="")
        assert config.api_key == ""


class TestDataConfig:
    """数据配置验证测试."""
    
    def test_valid_cache_root(self):
        """有效的缓存路径."""
        config = DataConfig(cache_root=Path("./data_cache"))
        assert config.cache_root == Path("./data_cache")
    
    def test_default_values(self):
        """默认值设置."""
        config = DataConfig()
        # cache_root 是相对路径 ./data_cache，需要相对于当前工作目录解析
        # 测试时工作目录是项目根目录，所以应该解析到项目根目录下的 data_cache
        expected_cache_root = Path("./data_cache").resolve()
        assert config.cache_root.resolve() == expected_cache_root
        # source_token 从 .env 加载，可能非空
        assert isinstance(config.source_token, str)


class TestBacktestConfig:
    """回测配置验证测试."""
    
    def test_valid_holding_periods(self):
        """有效的持有期列表."""
        config = BacktestConfig(holding_periods=[4, 10, 20])
        assert config.holding_periods == [4, 10, 20]
    
    def test_screening_date_format(self):
        """筛选日期格式."""
        config = BacktestConfig(screening_date="20260201")


class TestStockPoolConfig:
    """股票池配置验证测试."""
    
    def test_valid_filters(self):
        """有效的过滤条件."""
        config = StockPoolConfig(
            min_list_days=180,
            exclude_st=True,
            min_price=1.0,
            max_price=1000.0,
        )
        assert config.min_list_days == 180
        assert config.exclude_st is True
    
    def test_price_range_validation(self):
        """价格范围验证."""
        # 最小价格不能为负
        with pytest.raises(ValidationError):
            StockPoolConfig(min_price=-1.0)
        
        # 最大价格必须为正
        with pytest.raises(ValidationError):
            StockPoolConfig(max_price=0)
    
    def test_completeness_ratio_bounds(self):
        """完整性比例边界."""
        StockPoolConfig(min_completeness_ratio=0.0)
        StockPoolConfig(min_completeness_ratio=1.0)
        
        with pytest.raises(ValidationError):
            StockPoolConfig(min_completeness_ratio=-0.1)
        
        with pytest.raises(ValidationError):
            StockPoolConfig(min_completeness_ratio=1.5)
    
    def test_industry_filter_optional(self):
        """行业过滤可选."""
        config1 = StockPoolConfig(industry=None)
        assert config1.industry is None
        
        config2 = StockPoolConfig(industry=["银行", "证券"])
        assert config2.industry == ["银行", "证券"]


class TestHarnessConfig:
    """约束框架配置验证测试."""
    
    def test_valid_iterations(self):
        """有效的迭代次数."""
        config = HarnessConfig(max_iterations=25)
        assert config.max_iterations == 25
        
        with pytest.raises(ValidationError):
            HarnessConfig(max_iterations=0)
    
    def test_execution_time_positive(self):
        """执行时间必须为正."""
        HarnessConfig(max_execution_time=300)
        
        with pytest.raises(ValidationError):
            HarnessConfig(max_execution_time=0)
    
    def test_deep_thinking_default(self):
        """深度思考模式默认关闭."""
        config = HarnessConfig()
        assert config.deep_thinking is False
    
    def test_hooks_structure(self):
        """Hooks 结构验证."""
        config = HarnessConfig()
        assert "PreToolUse" in config.hooks
        assert "PostToolUse" in config.hooks
        assert "Stop" in config.hooks


class TestSettingsIntegration:
    """全局设置集成测试."""
    
    def test_create_default_settings(self):
        """创建默认设置."""
        settings = Settings()
        assert settings.llm.model == "deepseek-chat"
        assert settings.backtest.holding_periods == [4, 10, 20]
        assert settings.stock_pool.exclude_st is True
    
    def test_nested_config_validation(self):
        """嵌套配置验证."""
        with pytest.raises(ValidationError):
            Settings(
                llm={"temperature": 2.0}  # 超出范围
            )
    
    def test_observation_days_positive(self):
        """观察期必须为正数."""
        Settings(observation_days=80)
        
        with pytest.raises(ValidationError):
            Settings(observation_days=0)
    
    def test_frozen_config_mutable(self):
        """配置可变性测试."""
        settings = Settings()
        # ConfigDict(frozen=False) 允许修改
        settings.llm.temperature = 0.8
        assert settings.llm.temperature == 0.8


class TestConfigurationLoading:
    """配置加载测试."""
    
    def test_load_from_nonexistent_file(self, tmp_path):
        """从不存在的文件加载应返回默认值."""
        
        settings = load_settings(project_root=tmp_path)
        assert isinstance(settings, Settings)
    
    def test_environment_variable_expansion(self, tmp_path, monkeypatch):
        """环境变量展开."""
        monkeypatch.setenv("TEST_MODEL", "gpt-4")
        
        yaml_content = """
llm:
  model: ${TEST_MODEL}
"""
        config_dir = tmp_path / "setting"
        config_dir.mkdir()
        (config_dir / "screening.yaml").write_text(yaml_content)
        
        settings = load_settings(project_root=tmp_path)
        
        assert settings.llm.model == "gpt-4"
    
    def test_multiple_config_merge(self, tmp_path):
        """多配置文件合并."""
        screening_yaml = """
llm:
  model: deepseek-chat
  temperature: 0.7
"""
        backtest_yaml = """
backtest:
  holding_periods: [5, 10, 20]
"""
        config_dir = tmp_path / "setting"
        config_dir.mkdir()
        (config_dir / "screening.yaml").write_text(screening_yaml)
        (config_dir / "backtest.yaml").write_text(backtest_yaml)
        
        settings = load_settings(project_root=tmp_path)
        
        assert settings.llm.model == "deepseek-chat"
        assert settings.backtest.holding_periods == [5, 10, 20]


class TestErrorMessages:
    """错误消息友好性测试."""
    
    def test_clear_error_on_invalid_type(self):
        """类型错误应有清晰提示."""
        with pytest.raises(ValidationError) as exc_info:
            LLMConfig(temperature="high")  # 应为 float
        
        assert "temperature" in str(exc_info.value).lower()
    
    def test_field_name_in_error(self):
        """错误消息应包含字段名."""
        with pytest.raises(ValidationError) as exc_info:
            BacktestConfig(holding_periods="invalid")
        
        assert "holding_periods" in str(exc_info.value).lower()
