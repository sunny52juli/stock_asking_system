"""Tests for datahub integration and entries."""

import pytest
import pandas as pd
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from datahub.core.dataset import Dataset, DatasetMeta, FetchStep
from datahub.core.exceptions import DataNotFoundError
from datahub.core.query import Query
from datahub.domain.calendar import Calendar
from datahub.domain.stock import Stock
from datahub.entries import Calendar, DataHub, Stock
from datahub.factory import Factory
from datahub.loaders.stock_loader import load_latest_market_data
from datahub.sync.sync_repo import SyncRepository
class TestDataHubEntries:
    """测试 DataHub 入口点。"""
    
    def test_datahub_init(self):
        """测试 DataHub 初始化。"""
        
        hub = DataHub(root='/tmp/test', token='test_token')
        
        assert hub._root == '/tmp/test'
        assert hub._token == 'test_token'
    
    def test_datahub_stock(self):
        """测试 DataHub.Stock() 方法。"""
        
        with patch('datahub.entries.Factory') as mock_factory:
            mock_repo = Mock()
            mock_factory.create_repo.return_value = mock_repo
            
            hub = DataHub()
            stock = hub.Stock()
            
            assert stock is not None
            mock_factory.create_repo.assert_called_once()
    
    def test_standalone_stock_function(self):
        """测试独立的 Stock() 函数。"""
        
        with patch('datahub.factory.Factory') as mock_factory:
            mock_repo = Mock()
            mock_factory.create_repo.return_value = mock_repo
            
            stock = Stock(root='/tmp/test', token='test_token')
            
            assert stock is not None
    
    def test_calendar_doesnt_need_repo(self):
        """测试 Calendar 不需要 repository。"""
        
        cal = Calendar()
        
        assert cal is not None


class TestFactory:
    """测试 Factory 工厂类。"""
    
    @patch('datahub.factory.ParquetStore')
    @patch('datahub.factory.TushareSource')
    @patch('datahub.factory.SyncRepository')
    def test_create_repo_auto_mode(self, mock_sync_repo, mock_source, mock_store):
        """测试 auto 模式创建 repository。"""
        
        # 设置环境变量
        os.environ['DATA_CACHE_ROOT'] = '/tmp/cache'
        
        repo = Factory.create_repo(mode='auto', token='test_token')
        
        mock_store.assert_called_once()
        mock_source.assert_called_once_with(token='test_token')
        mock_sync_repo.assert_called_once()
        
        # 清理环境变量
        del os.environ['DATA_CACHE_ROOT']
    
    @patch('datahub.factory.ParquetStore')
    def test_create_repo_local_mode(self, mock_store):
        """测试 local 模式创建 repository。"""
        
        # 设置环境变量
        os.environ['DATA_CACHE_ROOT'] = '/tmp/cache'
        
        repo = Factory.create_repo(mode='local')
        
        mock_store.assert_called_once()
        # 不应该创建 source 或 sync repo
        assert repo == mock_store.return_value
        
        # 清理环境变量
        del os.environ['DATA_CACHE_ROOT']
    
    @patch('datahub.factory.ParquetStore')
    @patch('datahub.factory.TushareSource')
    @patch('datahub.factory.SyncRepository')
    def test_create_repo_remote_mode(self, mock_sync_repo, mock_source, mock_store):
        """测试 remote 模式创建 repository。"""
        
        # 设置环境变量
        os.environ['DATA_CACHE_ROOT'] = '/tmp/cache'
        
        repo = Factory.create_repo(mode='remote', token='test_token')
        
        mock_sync_repo.assert_called_once()
        # auto_save 应该是 False
        call_args = mock_sync_repo.call_args
        assert call_args[1]['auto_save'] is False
        
        # 清理环境变量
        del os.environ['DATA_CACHE_ROOT']


class TestDataLoaderIntegration:
    """测试数据加载器集成。"""
    
    def test_load_market_data_for_backtest_removed(self):
        """测试 load_market_data_for_backtest 已被移除（业务逻辑应在调用方实现）。"""
        # 该函数已删除，因为依赖外部模块
        # datahub 只提供基础数据加载能力
        with pytest.raises(ImportError):
            from datahub.loaders.stock_loader import load_market_data_for_backtest
            load_market_data_for_backtest()
    
    @patch('datahub.loaders.stock_loader.StockDataLoader')
    def test_load_latest_market_data(self, mock_loader_class):
        """测试最新市场数据加载。"""
        
        # Mock loader
        mock_loader = Mock()
        mock_df = pd.DataFrame()
        mock_loader.load_market_data.return_value = mock_df
        mock_loader_class.return_value = mock_loader
        
        result = load_latest_market_data(recent_days=30)
        
        mock_loader.load_market_data.assert_called_once()
        call_kwargs = mock_loader.load_market_data.call_args[1]
        assert 'start_date' in call_kwargs
        assert 'end_date' in call_kwargs


class TestDomainIntegration:
    """测试域对象集成。"""
    
    @pytest.mark.skip(reason="Integration test requiring complex repo mock")
    def test_stock_price_integration(self):
        """测试 Stock.price() 集成调用。"""
        
        with patch('datahub.domain._helpers.load_with_date_or_range') as mock_load_func:
            import polars as pl
            mock_df = pl.DataFrame({'ts_code': ['000001.SZ'], 'trade_date': ['20240301'], 'close': [10.0]})
            mock_load_func.return_value = mock_df
            
            mock_repo = Mock()
            stock = Stock(mock_repo)
            result = stock.price(date='20240301')
            
            assert len(result) == 1
            mock_load_func.assert_called_once()
    
    def test_calendar_integration(self):
        """测试 Calendar 集成。"""
        
        cal = Calendar()
        
        # 只验证方法存在且可调用
        assert hasattr(cal, 'get_trade_dates')
        assert hasattr(cal, 'is_trade_day')
        assert callable(cal.get_trade_dates)
        assert callable(cal.is_trade_day)


class TestErrorHandling:
    """测试错误处理。"""
    
    def test_data_not_found_error(self):
        """测试 DataNotFoundError 异常。"""
        
        error = DataNotFoundError("Test error")
        
        assert str(error) == "Test error"
        assert isinstance(error, Exception)
    
    @patch('datahub.sync.sync_repo.DatasetRegistry')
    def test_sync_repo_handles_empty_data(self, mock_registry):
        """测试 SyncRepository 处理空数据。"""
        
        mock_store = Mock()
        mock_store.load.side_effect = DataNotFoundError("Not found")
        
        mock_source = Mock()
        mock_source.call.return_value = None  # 返回空数据
        
        meta = DatasetMeta(
            dataset=Dataset.STOCK_DAILY,
            domain='stock',
            partition_by='date',
            key_columns=['ts_code'],
            storage_path='stock/daily',
            date_column='trade_date',
            code_column='ts_code',
            partition_key_template='{date}',
            description='Test'
        )
        pipeline = [FetchStep(api_name='daily', param_mapping={'trade_date': 'date'})]
        mock_registry.get.return_value = (meta, pipeline)
        
        repo = SyncRepository(mock_store, mock_source, auto_save=False)
        query = Query(dataset=Dataset.STOCK_DAILY, date='20240301')
        
        with pytest.raises(DataNotFoundError):
            repo.load(query)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
