"""测试 ToolStep 窗口参数验证."""

import pytest
from src.agent.models.screening_logic import ToolStep


class TestToolStepWindowValidation:
    """测试 ToolStep 的窗口参数验证."""
    
    def setup_method(self):
        """每个测试前重置 observation_days 为默认值."""
        ToolStep.set_observation_days(60)
    
    def test_valid_window_within_limit(self):
        """测试窗口参数在限制范围内应该通过."""
        tool = ToolStep(
            tool="rolling_mean",
            params={"column": "close", "window": 20},
            var="ma20"
        )
        assert tool.params["window"] == 20
    
    def test_window_exactly_at_limit(self):
        """测试窗口参数等于限制值应该通过."""
        ToolStep.set_observation_days(60)
        tool = ToolStep(
            tool="rolling_mean",
            params={"column": "close", "window": 60},
            var="ma60"
        )
        assert tool.params["window"] == 60
    
    def test_window_exceeds_limit_should_fail(self):
        """测试窗口参数超过限制应该抛出 ValueError."""
        ToolStep.set_observation_days(60)
        
        with pytest.raises(ValueError) as exc_info:
            ToolStep(
                tool="rolling_mean",
                params={"column": "volatility_20", "window": 100},
                var="avg_volatility"
            )
        
        assert "window=100" in str(exc_info.value)
        assert "超过最大允许值 60" in str(exc_info.value)
        assert "observation_days" in str(exc_info.value)
    
    def test_negative_window_should_fail(self):
        """测试负数窗口应该抛出 ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ToolStep(
                tool="rolling_mean",
                params={"column": "close", "window": -5},
                var="ma_neg"
            )
        
        assert "必须为正整数" in str(exc_info.value)
    
    def test_zero_window_should_fail(self):
        """测试零窗口应该抛出 ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ToolStep(
                tool="rolling_mean",
                params={"column": "close", "window": 0},
                var="ma_zero"
            )
        
        assert "必须为正整数" in str(exc_info.value)
    
    def test_no_window_param_is_ok(self):
        """测试没有 window 参数的工具应该通过."""
        tool = ToolStep(
            tool="pct_change",
            params={"column": "close", "periods": 20},
            var="return_20d"
        )
        assert tool.params["periods"] == 20
    
    def test_custom_observation_days(self):
        """测试自定义 observation_days 配置."""
        ToolStep.set_observation_days(100)
        
        # window=80 应该通过（小于 100）
        tool = ToolStep(
            tool="rolling_mean",
            params={"column": "close", "window": 80},
            var="ma80"
        )
        assert tool.params["window"] == 80
        
        # window=120 应该失败（大于 100）
        with pytest.raises(ValueError) as exc_info:
            ToolStep(
                tool="rolling_mean",
                params={"column": "close", "window": 120},
                var="ma120"
            )
        
        assert "window=120" in str(exc_info.value)
        assert "超过最大允许值 100" in str(exc_info.value)
    
    def test_float_window_value(self):
        """测试浮点数窗口值也应该被验证."""
        ToolStep.set_observation_days(60)
        
        with pytest.raises(ValueError) as exc_info:
            ToolStep(
                tool="rolling_mean",
                params={"column": "close", "window": 75.5},
                var="ma75"
            )
        
        assert "window=75.5" in str(exc_info.value)
        assert "超过最大允许值 60" in str(exc_info.value)
    
    def test_different_tools_with_window(self):
        """测试不同工具的 window 参数都应该被验证."""
        ToolStep.set_observation_days(60)
        
        # rolling_std
        tool1 = ToolStep(
            tool="rolling_std",
            params={"column": "pct_chg", "window": 20},
            var="volatility_20d"
        )
        assert tool1.params["window"] == 20
        
        # rsi
        tool2 = ToolStep(
            tool="rsi",
            params={"column": "close", "window": 14},
            var="rsi14"
        )
        assert tool2.params["window"] == 14
        
        # macd (fast/slow/signal 不是 window，不应该被验证)
        tool3 = ToolStep(
            tool="macd",
            params={"column": "close", "fast": 12, "slow": 26, "signal": 9},
            var="macd_signal"
        )
        assert tool3.params["fast"] == 12


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
