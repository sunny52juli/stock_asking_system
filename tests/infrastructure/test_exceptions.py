"""异常类测试."""

import pytest

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


class TestQuantSystemError:
    """测试基础异常类."""

    def test_basic_exception(self):
        """测试基础异常创建."""
        exc = QuantSystemError("测试错误")
        assert str(exc) == "测试错误"
        assert exc.message == "测试错误"
        assert exc.details == {}

    def test_exception_with_details(self):
        """测试带详情的异常."""
        exc = QuantSystemError("错误", details={"key": "value"})
        assert "详情" in str(exc)
        assert exc.details == {"key": "value"}

    def test_exception_inheritance(self):
        """测试异常继承关系."""
        assert issubclass(QuantSystemError, Exception)


class TestDataErrors:
    """测试数据相关异常."""

    def test_data_error_hierarchy(self):
        """测试数据异常层次结构."""
        assert issubclass(DataError, QuantSystemError)
        assert issubclass(DataLoadError, DataError)
        assert issubclass(DataValidationError, DataError)
        assert issubclass(StockPoolError, DataError)

    def test_data_load_error(self):
        """测试数据加载错误."""
        exc = DataLoadError("文件不存在")
        assert isinstance(exc, DataError)
        assert isinstance(exc, QuantSystemError)

    def test_data_validation_error(self):
        """测试数据验证错误."""
        exc = DataValidationError("字段缺失")
        assert isinstance(exc, DataError)


class TestFactorErrors:
    """测试因子相关异常."""

    def test_factor_error_hierarchy(self):
        """测试因子异常层次结构."""
        assert issubclass(FactorError, QuantSystemError)
        assert issubclass(FactorCalculationError, FactorError)
        assert issubclass(FactorBacktestError, FactorError)
        assert issubclass(FactorScriptError, FactorError)

    def test_factor_calculation_error(self):
        """测试因子计算错误."""
        exc = FactorCalculationError("计算失败")
        assert isinstance(exc, FactorError)


class TestConfigErrors:
    """测试配置相关异常."""

    def test_config_error_hierarchy(self):
        """测试配置异常层次结构."""
        assert issubclass(ConfigError, QuantSystemError)
        assert issubclass(APIConfigError, ConfigError)
        assert issubclass(MissingAPIKeyError, APIConfigError)

    def test_missing_api_key_error(self):
        """测试 API 密钥缺失错误."""
        exc = MissingAPIKeyError()
        assert "DEFAULT_API_KEY" in str(exc)
        
        exc_custom = MissingAPIKeyError("CUSTOM_KEY")
        assert "CUSTOM_KEY" in str(exc_custom)
        assert exc_custom.details == {"key_name": "CUSTOM_KEY"}


class TestScreeningErrors:
    """测试筛选相关异常."""

    def test_screening_error_hierarchy(self):
        """测试筛选异常层次结构."""
        assert issubclass(ScreeningError, QuantSystemError)
        assert issubclass(ScreeningLogicError, ScreeningError)
        assert issubclass(ToolExecutionError, ScreeningError)

    def test_tool_execution_error(self):
        """测试工具执行错误."""
        exc = ToolExecutionError("工具失败")
        assert isinstance(exc, ScreeningError)


class TestAgentErrors:
    """测试 Agent 相关异常."""

    def test_agent_error_hierarchy(self):
        """测试 Agent 异常层次结构."""
        assert issubclass(AgentError, QuantSystemError)
        assert issubclass(AgentInitializationError, AgentError)
        assert issubclass(AgentExecutionError, AgentError)

    def test_agent_initialization_error(self):
        """测试 Agent 初始化错误."""
        exc = AgentInitializationError("初始化失败")
        assert isinstance(exc, AgentError)


class TestLLMErrors:
    """测试 LLM 相关异常."""

    def test_llm_error_hierarchy(self):
        """测试 LLM 异常层次结构."""
        assert issubclass(LLMError, QuantSystemError)
        assert issubclass(LLMResponseError, LLMError)
        assert issubclass(LLMParseError, LLMError)

    def test_llm_response_error(self):
        """测试 LLM 响应错误."""
        exc = LLMResponseError("响应格式错误")
        assert isinstance(exc, LLMError)


class TestExceptionHandling:
    """测试异常捕获."""

    def test_catch_quant_system_error(self):
        """测试捕获基础异常."""
        try:
            raise DataLoadError("测试")
        except QuantSystemError as e:
            assert isinstance(e, DataLoadError)

    def test_catch_specific_error(self):
        """测试捕获特定异常."""
        try:
            raise DataLoadError("测试")
        except DataLoadError as e:
            assert str(e) == "测试"

    def test_exception_chain(self):
        """测试异常链."""
        try:
            original_error = ValueError("原始错误")
            try:
                raise original_error
            except ValueError:
                new_error = DataLoadError("包装错误")
                new_error.__cause__ = original_error
                raise new_error
        except DataLoadError as e:
            assert e.__cause__ is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
