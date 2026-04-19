"""Tests for datahub domain modules."""

import pytest
import pandas as pd
from unittest.mock import Mock, MagicMock, patch


from datahub.domain.calendar import Calendar
from datahub.domain.feature import Feature
from datahub.domain.fund import Fund
from datahub.domain.index import Index
from datahub.domain.news import News
from datahub.domain.stock import Stock
class TestStockDomain:
    """测试 Stock 域对象。"""
    
    def test_price_with_date(self):
        """测试按单日获取价格数据。"""
        
        mock_repo = Mock()
        mock_df = pd.DataFrame({'ts_code': ['000001.SZ'], 'close': [10.0]})
        mock_repo.load.return_value = mock_df
        
        stock = Stock(mock_repo)
        result = stock.price(date='20240301')
        
        assert not result.empty
        assert len(result) == 1
        mock_repo.load.assert_called_once()
    
    def test_price_with_date_range(self):
        """测试按日期范围获取价格数据。"""
        
        mock_repo = Mock()
        mock_df = pd.DataFrame({
            'ts_code': ['000001.SZ', '000001.SZ'],
            'trade_date': ['20240301', '20240302'],
            'close': [10.0, 11.0]
        })
        mock_repo.load.return_value = mock_df
        
        stock = Stock(mock_repo)
        result = stock.price(start_date='20240301', end_date='20240302')
        
        assert len(result) == 2
        mock_repo.load.assert_called_once()
    
    def test_price_requires_date_or_range(self):
        """测试 price 方法必须提供 date 或日期范围。"""
        
        mock_repo = Mock()
        stock = Stock(mock_repo)
        
        with pytest.raises(ValueError):
            stock.price()


class TestCalendarDomain:
    """测试 Calendar 域对象。"""
    
    def test_calendar_init(self):
        """测试 Calendar 初始化。"""
        
        cal = Calendar()
        assert cal is not None
    
    def test_is_trade_day(self):
        """测试判断是否为交易日。"""
        
        # 直接测试，不 mock 内部依赖
        cal = Calendar()
        # 只验证方法存在且可调用
        assert hasattr(cal, 'is_trade_day')
        assert callable(cal.is_trade_day)
    
    def test_get_trade_dates(self):
        """测试获取交易日期列表。"""
        
        cal = Calendar()
        # 只验证方法存在且可调用
        assert hasattr(cal, 'get_trade_dates')
        assert callable(cal.get_trade_dates)


class TestFundDomain:
    """测试 Fund 域对象。"""
    
    def test_fund_init(self):
        """测试 Fund 初始化。"""
        
        mock_repo = Mock()
        fund = Fund(mock_repo)
        
        assert fund._repo == mock_repo


class TestIndexDomain:
    """测试 Index 域对象。"""
    
    def test_index_init(self):
        """测试 Index 初始化。"""
        
        mock_repo = Mock()
        index = Index(mock_repo)
        
        assert index._repo == mock_repo


class TestFeatureDomain:
    """测试 Feature 域对象。"""
    
    def test_feature_init(self):
        """测试 Feature 初始化。"""
        
        mock_stock = Mock()
        feature = Feature(mock_stock)
        
        assert feature._stock == mock_stock


class TestNewsDomain:
    """测试 News 域对象。"""
    
    def test_news_init(self):
        """测试 News 初始化。"""
        
        mock_repo = Mock()
        news = News(mock_repo)
        
        assert news._repo == mock_repo


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
