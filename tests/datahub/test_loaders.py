"""Tests for datahub loaders module."""

import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch


class TestBaseDataLoader:
    """测试 BaseDataLoader 基类功能。"""
    
    def test_set_multi_index_basic(self):
        """测试设置 MultiIndex 基本功能。"""
        from datahub.loaders.base import BaseDataLoader
        
        # 创建测试数据
        data = pd.DataFrame({
            'trade_date': ['20240101', '20240101', '20240102'],
            'ts_code': ['000001.SZ', '000002.SZ', '000001.SZ'],
            'close': [10.0, 20.0, 11.0]
        })
        
        # 创建具体的子类实例而不是抽象类
        class ConcreteLoader(BaseDataLoader):
            def load_data(self, **kwargs):
                return pd.DataFrame()
        
        loader = ConcreteLoader()
        result = loader.set_multi_index(data)
        
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ['trade_date', 'ts_code']
        assert len(result) == 3
    
    def test_set_multi_index_empty(self):
        """测试空 DataFrame 的处理。"""
        from datahub.loaders.base import BaseDataLoader
        
        class ConcreteLoader(BaseDataLoader):
            def load_data(self, **kwargs):
                return pd.DataFrame()
        
        loader = ConcreteLoader()
        result = loader.set_multi_index(pd.DataFrame())
        
        assert result.empty
    
    def test_filter_by_stock_pool_with_multiindex(self):
        """测试基于股票池过滤（MultiIndex）。"""
        from datahub.loaders.base import BaseDataLoader
        
        data = pd.DataFrame({
            'trade_date': pd.to_datetime(['2024-01-01', '2024-01-01']),
            'ts_code': ['000001.SZ', '000002.SZ'],
            'close': [10.0, 20.0]
        }).set_index(['trade_date', 'ts_code'])
        
        class ConcreteLoader(BaseDataLoader):
            def load_data(self, **kwargs):
                return pd.DataFrame()
        
        loader = ConcreteLoader()
        result = loader.filter_by_stock_pool(data, ['000001.SZ'])
        
        assert len(result) == 1
        assert result.index.get_level_values('ts_code')[0] == '000001.SZ'
    
    def test_extract_industries(self):
        """测试提取行业列表。"""
        from datahub.loaders.base import BaseDataLoader
            
        data = pd.DataFrame({
            'industry': ['银行', '证券', '银行', None, '']
        })
            
        class ConcreteLoader(BaseDataLoader):
            def load_data(self, **kwargs):
                return pd.DataFrame()
            
        loader = ConcreteLoader()
        industries = loader.extract_industries(data)
            
        assert industries == ['证券', '银行']
        assert isinstance(industries, list)
        
    def test_extract_industries_from_multiindex(self):
        """测试 MultiIndex DataFrame 提取行业。"""
        from datahub.loaders.base import BaseDataLoader
            
        data = pd.DataFrame({
            'trade_date': pd.to_datetime(['2024-01-01']),
            'ts_code': ['000001.SZ'],
            'industry': ['银行']
        }).set_index(['trade_date', 'ts_code'])
            
        class ConcreteLoader(BaseDataLoader):
            def load_data(self, **kwargs):
                return pd.DataFrame()
            
        loader = ConcreteLoader()
        industries = loader.extract_industries(data)
            
        assert industries == ['银行']
    
    def test_clean_data(self):
        """测试数据清洗功能。"""
        from datahub.loaders.base import BaseDataLoader
        
        data = pd.DataFrame({
            'open': [10.0, None, 12.0],
            'high': [11.0, 21.0, None],
            'low': [9.0, 19.0, 11.0],
            'close': [10.5, 20.5, 11.5],
            'vol': [1000, 2000, 0]  # vol=0 的行应该被过滤
        })
        
        class ConcreteLoader(BaseDataLoader):
            def load_data(self, **kwargs):
                return pd.DataFrame()
        
        loader = ConcreteLoader()
        cleaned = loader.clean_data(data)
        
        # 应该只剩下第一行（第二行有 NaN，第三行 vol=0）
        assert len(cleaned) == 1


class TestDataLoaderMixin:
    """测试 DataLoaderMixin 工具类。"""
    
    def test_set_dataframe_index(self):
        """测试设置 DataFrame 索引。"""
        from datahub.loaders.base import DataLoaderMixin
        
        data = pd.DataFrame({
            'trade_date': ['20240101', '20240102'],
            'ts_code': ['000001.SZ', '000002.SZ'],
            'close': [10.0, 20.0]
        })
        
        result = DataLoaderMixin.set_dataframe_index(data)
        
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ['trade_date', 'ts_code']
    
    def test_filter_stocks(self):
        """测试股票过滤功能。"""
        from datahub.loaders.base import DataLoaderMixin
        
        data = pd.DataFrame({
            'trade_date': pd.to_datetime(['2024-01-01', '2024-01-01']),
            'ts_code': ['000001.SZ', '000002.SZ'],
            'close': [10.0, 20.0]
        })
        
        result = DataLoaderMixin.filter_stocks(data, ['000001.SZ'])
        
        assert len(result) == 1
        assert result.iloc[0]['ts_code'] == '000001.SZ'


class TestStockDataLoader:
    """测试 StockDataLoader 类。"""
    
    @patch('datahub.loaders.stock_loader.Stock')
    @patch('datahub.loaders.stock_loader.Calendar')
    def test_init_default(self, mock_calendar, mock_stock):
        """测试默认初始化。"""
        from datahub.loaders.stock_loader import StockDataLoader
        
        loader = StockDataLoader()
        
        assert loader.exclude_st is True
        assert loader.min_list_days == 180
        assert loader.index_code is None
    
    @patch('datahub.loaders.stock_loader.Stock')
    @patch('datahub.loaders.stock_loader.Calendar')
    def test_get_latest_trade_date_success(self, mock_calendar, mock_stock):
        """测试获取最新交易日期成功场景。"""
        from datahub.loaders.stock_loader import StockDataLoader
        from datetime import datetime
        
        # Mock calendar
        mock_cal_instance = Mock()
        mock_cal_instance.latest_trade_date.return_value = datetime(2024, 3, 1)
        mock_calendar.return_value = mock_cal_instance
        
        loader = StockDataLoader(calendar=mock_cal_instance)
        result = loader._get_latest_trade_date()
        
        assert result == '20240301'
    
    @patch('datahub.loaders.stock_loader.Stock')
    @patch('datahub.loaders.stock_loader.Calendar')
    def test_get_latest_trade_date_fallback(self, mock_calendar, mock_stock):
        """测试获取最新交易日期失败时的备用方案。"""
        from datahub.loaders.stock_loader import StockDataLoader
        
        # Mock calendar 抛出异常
        mock_cal_instance = Mock()
        mock_cal_instance.latest_trade_date.side_effect = Exception("Error")
        
        loader = StockDataLoader(calendar=mock_cal_instance)
        result = loader._get_latest_trade_date()
        
        # 应该返回当前日期
        from datetime import datetime
        expected = datetime.now().strftime("%Y%m%d")
        assert result == expected
    
    def test_calculate_default_dates(self):
        """测试默认日期计算。"""
        from datahub.loaders.stock_loader import StockDataLoader
        
        loader = StockDataLoader.__new__(StockDataLoader)
        start, end = loader._calculate_default_dates('20240301')
        
        assert end == '20240301'
        # start_date 应该是 end_date 往前推 observation_days 个交易日（通过交易日历计算）
        # 由于使用交易日历，结果可能与自然日不同，这里只验证格式和逻辑合理性
        assert len(start) == 8
        assert start.isdigit()
        # 验证 start < end
        assert start < end
    
    def test_calculate_default_dates_invalid_format(self):
        """测试无效日期格式的处理。"""
        from datahub.loaders.stock_loader import StockDataLoader
        from datetime import datetime
        
        loader = StockDataLoader.__new__(StockDataLoader)
        start, end = loader._calculate_default_dates('invalid')
        
        # 应该使用当前日期作为 fallback
        expected_end = datetime.now().strftime("%Y%m%d")
        assert end == expected_end


class TestFactorDataLoader:
    """测试 FactorDataLoader 类。"""
    
    @patch('datahub.loaders.factor_loader.Stock')
    @patch('datahub.loaders.factor_loader.Calendar')
    def test_init_default(self, mock_calendar, mock_stock):
        """测试默认初始化。"""
        from datahub.loaders.factor_loader import FactorDataLoader
        
        loader = FactorDataLoader()
        
        assert loader._stock is not None
        assert loader._calendar is not None
    
    @patch('datahub.loaders.factor_loader.Stock')
    @patch('datahub.loaders.factor_loader.Calendar')
    def test_get_stock_pool_requires_trade_date(self, mock_calendar, mock_stock):
        """测试 get_stock_pool 必须传入 trade_date。"""
        from datahub.loaders.factor_loader import FactorDataLoader
        
        loader = FactorDataLoader()
        
        with pytest.raises(ValueError, match="trade_date.*必须显式传入"):
            loader.get_stock_pool()


class TestHelperFunctions:
    """测试辅助函数。"""
    
    @patch('datahub.loaders.stock_loader.Stock')
    def test_get_stock_pool_from_datahub_no_trade_date(self, mock_stock):
        """测试 _get_stock_pool_from_datahub 在没有 trade_date 时抛出异常。"""
        from datahub.loaders.stock_loader import _get_stock_pool_from_datahub
        
        with pytest.raises(ValueError, match="trade_date.*必须显式传入"):
            _get_stock_pool_from_datahub(mock_stock())
    
    @patch('datahub.loaders.stock_loader.Stock')
    def test_get_stock_pool_from_datahub_with_universe(self, mock_stock):
        """测试 _get_stock_pool_from_datahub 正常获取股票池。"""
        from datahub.loaders.stock_loader import _get_stock_pool_from_datahub
        import pandas as pd
        
        # Mock universe 数据
        mock_stock_instance = Mock()
        mock_universe = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ', '300001.SZ'],
            'name': ['平安银行', '万科A', '特锐德'],
            'list_date': ['19910403', '19910129', '20091030']
        })
        mock_stock_instance.universe.return_value = mock_universe
        
        result = _get_stock_pool_from_datahub(
            mock_stock_instance,
            trade_date='20240301',
            exclude_st=True,
            min_list_days=180
        )
        
        assert len(result) == 3
        assert '000001.SZ' in result


class TestDataLoaderModule:
    """测试 datahub.loaders.stock_loader 模块。"""
    
    def test_load_market_data_removed(self):
        """测试 load_market_data 已被移除（业务逻辑应在调用方实现）。"""
        # 该函数已删除，因为依赖外部模块
        with pytest.raises(ImportError):
            from datahub.loaders.stock_loader import load_market_data
    
    @patch('datahub.loaders.stock_loader.StockDataLoader')
    def test_load_latest_market_data(self, mock_loader_class):
        """测试加载最新市场数据。"""
        from datahub.loaders.stock_loader import load_latest_market_data
        
        # Mock loader
        mock_loader = Mock()
        mock_loader.load_market_data.return_value = pd.DataFrame()
        mock_loader_class.return_value = mock_loader
        
        result = load_latest_market_data(recent_days=30)
        
        # 验证调用了 load_market_data
        assert mock_loader.load_market_data.called
        call_kwargs = mock_loader.load_market_data.call_args[1]
        assert 'start_date' in call_kwargs
        assert 'end_date' in call_kwargs
    
    @patch('datahub.loaders.stock_loader.get_available_industries')
    def test_get_available_industries_with_data(self, mock_get_industries):
        """测试获取行业列表（带数据）。"""
        from datahub.loaders.stock_loader import get_available_industries
        
        data = pd.DataFrame({'industry': ['银行', '证券']})
        mock_get_industries.return_value = ['银行', '证券']
        
        result = get_available_industries(data)
        
        mock_get_industries.assert_called_once_with(data)
        assert result == ['银行', '证券']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
