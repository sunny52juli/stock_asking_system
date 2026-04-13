"""回测模块测试 - returns.py"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.backtest.returns import ReturnsCalculator


class TestReturnsCalculator:
    """收益计算器测试类."""

    @pytest.fixture
    def sample_data(self):
        """创建样本市场数据."""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        stocks = ['000001.SZ', '000002.SZ', '600000.SH']
        
        data_list = []
        for date in dates:
            for stock in stocks:
                data_list.append({
                    'trade_date': date,
                    'ts_code': stock,
                    'close': 100 + np.random.randn() * 5,
                    'open': 100 + np.random.randn() * 5,
                    'high': 105 + np.random.randn() * 5,
                    'low': 95 + np.random.randn() * 5,
                    'name': f'股票{stock[:6]}',
                    'industry': '银行业',
                })
        
        df = pd.DataFrame(data_list)
        df = df.set_index(['trade_date', 'ts_code'])
        return df

    @pytest.fixture
    def calculator(self, sample_data):
        """创建收益计算器实例."""
        return ReturnsCalculator(sample_data, [5, 10, 20])

    def test_calculate_returns_empty_candidates(self, calculator):
        """测试空候选列表."""
        result = calculator.calculate_returns([], '20240105')
        assert result == {"per_stock": [], "summary": {}}

    def test_calculate_single_stock_returns(self, calculator):
        """测试单只股票收益计算."""
        result = calculator._calculate_single_stock_returns(
            '000001.SZ', 
            pd.Timestamp('2024-01-05')
        )
        
        if result is not None:
            assert 'ret_5d' in result
            assert 'ret_10d' in result
            assert 'ret_20d' in result
            
            # 检查收益率是否为有效数值或None
            for key in ['ret_5d', 'ret_10d', 'ret_20d']:
                if result[key] is not None:
                    assert isinstance(result[key], (int, float))

    def test_calculate_portfolio_stats(self, calculator):
        """测试投资组合统计计算."""
        per_stock_results = [
            {'ts_code': '000001.SZ', 'ret_5d': 0.05, 'ret_10d': 0.08},
            {'ts_code': '000002.SZ', 'ret_5d': -0.02, 'ret_10d': 0.03},
            {'ts_code': '600000.SH', 'ret_5d': 0.03, 'ret_10d': None},
        ]
        
        summary = calculator._calculate_portfolio_stats(per_stock_results)
        
        assert 5 in summary
        assert 10 in summary
        
        # 检查5日统计
        stats_5d = summary[5]
        assert 'mean' in stats_5d
        assert 'std' in stats_5d
        assert 'win_rate' in stats_5d
        assert 'valid_stocks' in stats_5d
        assert stats_5d['valid_stocks'] == 3
        
        # 检查10日统计（有一个None值）
        stats_10d = summary[10]
        assert stats_10d['valid_stocks'] == 2

    def test_calculate_portfolio_stats_empty(self, calculator):
        """测试空的投资组合统计."""
        summary = calculator._calculate_portfolio_stats([])
        
        for period in [5, 10, 20]:
            assert period in summary
            assert summary[period]['mean'] == 0.0
            assert summary[period]['win_rate'] == 0.0

    def test_get_stock_info(self, calculator):
        """测试获取股票信息."""
        info = calculator.get_stock_info('000001.SZ')
        
        assert 'ts_code' in info
        assert info['ts_code'] == '000001.SZ'
        assert 'name' in info
        assert 'industry' in info

    def test_get_stock_info_not_found(self, calculator):
        """测试获取不存在的股票信息."""
        info = calculator.get_stock_info('999999.SZ')
        
        assert info['ts_code'] == '999999.SZ'
        assert info['name'] == '999999.SZ'
        assert info['industry'] == 'N/A'

    def test_invalid_holding_period(self, calculator):
        """测试超出数据范围的持有期."""
        # 使用很早的日期，使得部分持有期超出数据范围
        result = calculator._calculate_single_stock_returns(
            '000001.SZ',
            pd.Timestamp('2024-01-25')
        )
        
        # 应该返回字典，但超出范围的持有期收益率为None
        assert result is not None
        assert isinstance(result, dict)
        # 至少有一个持有期为None（超出数据范围）
        assert any(v is None for v in result.values())


class TestReturnsCalculatorEdgeCases:
    """收益计算器边界情况测试."""

    def test_zero_price(self):
        """测试零价格情况."""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        data_list = []
        for i, date in enumerate(dates):
            # 筛选日期是 2024-01-04 (i=3)，让买入价格为0
            data_list.append({
                'trade_date': date,
                'ts_code': '000001.SZ',
                'close': 0 if i == 3 else 100,
                'name': '测试股票',
                'industry': '测试行业',
            })
        
        df = pd.DataFrame(data_list).set_index(['trade_date', 'ts_code'])
        calculator = ReturnsCalculator(df, [5])
        
        result = calculator._calculate_single_stock_returns(
            '000001.SZ',
            pd.Timestamp('2024-01-04')
        )
        
        # 如果买入价格为0，应该返回None
        assert result is None

    def test_nan_price(self):
        """测试NaN价格情况."""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        data_list = []
        for i, date in enumerate(dates):
            # 筛选日期是 2024-01-05 (i=4)，持有5天后是 i=9，让卖出价格为NaN
            data_list.append({
                'trade_date': date,
                'ts_code': '000001.SZ',
                'close': np.nan if i == 9 else 100,
                'name': '测试股票',
                'industry': '测试行业',
            })
        
        df = pd.DataFrame(data_list).set_index(['trade_date', 'ts_code'])
        calculator = ReturnsCalculator(df, [5])
        
        result = calculator._calculate_single_stock_returns(
            '000001.SZ',
            pd.Timestamp('2024-01-05')
        )
        
        # 卖出价格为NaN时，对应收益率应为None
        assert result is not None
        assert result.get('ret_5d') is None

    def test_negative_price(self):
        """测试负价格情况."""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        data_list = []
        for i, date in enumerate(dates):
            # 筛选日期是 2024-01-05 (i=4)，持有5天后是 i=9，让卖出价格为负数
            data_list.append({
                'trade_date': date,
                'ts_code': '000001.SZ',
                'close': -10 if i == 9 else 100,
                'name': '测试股票',
                'industry': '测试行业',
            })
        
        df = pd.DataFrame(data_list).set_index(['trade_date', 'ts_code'])
        calculator = ReturnsCalculator(df, [5])
        
        result = calculator._calculate_single_stock_returns(
            '000001.SZ',
            pd.Timestamp('2024-01-05')
        )
        
        # 卖出价格为负数时，对应收益率应为None
        assert result is not None
        assert result.get('ret_5d') is None
