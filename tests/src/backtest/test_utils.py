"""回测模块测试 - utils.py"""

import pytest
from src.backtest.utils import (
    get_holding_period_end_date,
    format_return_percentage,
    calculate_win_rate,
    calculate_avg_return,
    calculate_sharpe_ratio,
)


class TestFormatReturnPercentage:
    """收益率格式化测试."""

    def test_positive_return(self):
        """测试正收益率."""
        result = format_return_percentage(0.1523)
        assert result == "+15.23%"

    def test_negative_return(self):
        """测试负收益率."""
        result = format_return_percentage(-0.0845)
        assert result == "-8.45%"

    def test_zero_return(self):
        """测试零收益率."""
        result = format_return_percentage(0.0)
        assert result == "+0.00%"

    def test_small_return(self):
        """测试小收益率."""
        result = format_return_percentage(0.0001)
        assert result == "+0.01%"

    def test_large_return(self):
        """测试大收益率."""
        result = format_return_percentage(1.5)
        assert result == "+150.00%"


class TestCalculateWinRate:
    """胜率计算测试."""

    def test_all_winning(self):
        """测试全部盈利."""
        results = [
            {'return': 0.05},
            {'return': 0.08},
            {'return': 0.03},
        ]
        assert calculate_win_rate(results) == 1.0

    def test_all_losing(self):
        """测试全部亏损."""
        results = [
            {'return': -0.05},
            {'return': -0.08},
            {'return': -0.03},
        ]
        assert calculate_win_rate(results) == 0.0

    def test_mixed_results(self):
        """测试混合结果."""
        results = [
            {'return': 0.05},
            {'return': -0.02},
            {'return': 0.03},
            {'return': -0.01},
        ]
        assert calculate_win_rate(results) == 0.5

    def test_empty_results(self):
        """测试空结果列表."""
        assert calculate_win_rate([]) == 0.0

    def test_zero_return_not_counted(self):
        """测试零收益不计入盈利."""
        results = [
            {'return': 0.05},
            {'return': 0.0},
            {'return': -0.02},
        ]
        assert calculate_win_rate(results) == 1/3


class TestCalculateAvgReturn:
    """平均收益率计算测试."""

    def test_simple_average(self):
        """测试简单平均."""
        results = [
            {'return': 0.05},
            {'return': 0.10},
            {'return': 0.15},
        ]
        assert pytest.approx(calculate_avg_return(results)) == 0.10

    def test_negative_average(self):
        """测试负平均."""
        results = [
            {'return': -0.05},
            {'return': -0.10},
        ]
        assert pytest.approx(calculate_avg_return(results)) == -0.075

    def test_empty_results(self):
        """测试空结果列表."""
        assert calculate_avg_return([]) == 0.0

    def test_missing_return_field(self):
        """测试缺失return字段."""
        results = [
            {'return': 0.05},
            {'other_field': 0.10},
        ]
        # 缺失字段默认为0
        assert calculate_avg_return(results) == 0.025


class TestCalculateSharpeRatio:
    """夏普比率计算测试."""

    def test_normal_sharpe(self):
        """测试正常夏普比率."""
        returns = [0.01, 0.02, -0.01, 0.015, 0.005]
        sharpe = calculate_sharpe_ratio(returns)
        assert isinstance(sharpe, float)

    def test_empty_returns(self):
        """测试空收益率列表."""
        assert calculate_sharpe_ratio([]) == 0.0

    def test_single_return(self):
        """测试单个收益率."""
        assert calculate_sharpe_ratio([0.01]) == 0.0

    def test_zero_std(self):
        """测试零标准差."""
        returns = [0.01, 0.01, 0.01, 0.01]
        # 标准差为0时返回0
        assert calculate_sharpe_ratio(returns) == 0.0

    def test_custom_risk_free_rate(self):
        """测试自定义无风险利率."""
        returns = [0.01, 0.02, -0.01, 0.015]
        sharpe_low_rf = calculate_sharpe_ratio(returns, risk_free_rate=0.01)
        sharpe_high_rf = calculate_sharpe_ratio(returns, risk_free_rate=0.05)
        
        # 无风险利率越低，夏普比率越高
        assert sharpe_low_rf > sharpe_high_rf


class TestGetHoldingPeriodEndDate:
    """持有期结束日期计算测试."""

    def test_basic_calculation(self):
        """测试基本日期计算."""
        # 注意：这个函数依赖于 calculate_date_offset，需要确保该函数可用
        try:
            end_date = get_holding_period_end_date('20240101', 5)
            assert isinstance(end_date, str)
            assert len(end_date) == 8
        except ImportError:
            pytest.skip("calculate_date_offset not available")
