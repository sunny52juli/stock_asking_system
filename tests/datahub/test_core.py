"""Tests for datahub src modules (repository, query, dataset)."""

import pytest
import pandas as pd
from unittest.mock import Mock, patch


class TestQuery:
    """测试 Query 数据类。"""
    
    def test_query_single_date(self):
        """测试单日查询创建。"""
        from datahub.core.query import Query
        from datahub.core.dataset import Dataset
        
        query = Query(
            dataset=Dataset.STOCK_DAILY,
            date='20240301',
            codes=['000001.SZ'],
            fields=['close']
        )
        
        assert query.date == '20240301'
        assert not query.is_range
        assert query.codes == ['000001.SZ']
    
    def test_query_date_range(self):
        """测试日期范围查询创建。"""
        from datahub.core.query import Query
        from datahub.core.dataset import Dataset
        
        query = Query(
            dataset=Dataset.STOCK_DAILY,
            start_date='20240301',
            end_date='20240331',
            codes=['000001.SZ']
        )
        
        assert query.start_date == '20240301'
        assert query.end_date == '20240331'
        assert query.is_range
    
    def test_query_validation(self):
        """测试查询参数验证。"""
        from datahub.core.query import Query
        from datahub.core.dataset import Dataset
        
        # 同时提供 date 和日期范围应该报错
        with pytest.raises(ValueError):
            Query(
                dataset=Dataset.STOCK_DAILY,
                date='20240301',
                start_date='20240301',
                end_date='20240331'
            )


class TestDataset:
    """测试 Dataset 枚举。"""
    
    def test_dataset_values(self):
        """测试数据集枚举值。"""
        from datahub.core.dataset import Dataset
        
        assert Dataset.STOCK_DAILY.value == 'stock_daily'
        assert Dataset.STOCK_BASIC.value == 'stock_basic'


class TestDatasetMeta:
    """测试 DatasetMeta 配置。"""
    
    def test_dataset_meta_creation(self):
        """测试数据集元数据创建。"""
        from datahub.core.dataset import DatasetMeta, Dataset
        
        meta = DatasetMeta(
            dataset=Dataset.STOCK_DAILY,
            domain='stock',
            partition_by='date',
            key_columns=['ts_code', 'trade_date'],
            storage_path='stock/daily',
            date_column='trade_date',
            code_column='ts_code',
            partition_key_template='{date}',
            description='股票日线数据'
        )
        
        assert meta.dataset == Dataset.STOCK_DAILY
        assert meta.partition_by == 'date'
        assert meta.date_column == 'trade_date'


class TestDatasetRegistry:
    """测试 DatasetRegistry 注册表。"""
    
    def test_register_and_get(self):
        """测试注册和获取数据集配置。"""
        from datahub.core.dataset import DatasetRegistry, DatasetMeta, Dataset, FetchStep
        
        # 创建一个测试数据集
        test_dataset = Dataset.STOCK_DAILY
        meta = DatasetMeta(
            dataset=test_dataset,
            domain='test',
            partition_by='date',
            key_columns=['ts_code'],
            storage_path='test',
            date_column='trade_date',
            code_column='ts_code',
            partition_key_template='{date}',
            description='Test dataset'
        )
        pipeline = [FetchStep(api_name='test_api', param_mapping={})]
        
        # 注册
        DatasetRegistry.register(meta, pipeline)
        
        # 获取
        retrieved_meta, retrieved_pipeline = DatasetRegistry.get(test_dataset)
        
        assert retrieved_meta == meta
        assert len(retrieved_pipeline) == 1


class TestRepository:
    """测试 Repository 抽象基类。"""
    
    def test_repository_is_abstract(self):
        """测试 Repository 是抽象类，不能直接实例化。"""
        from datahub.core.repository import Repository
        
        with pytest.raises(TypeError):
            Repository()
    
    def test_repository_subclass_must_implement_methods(self):
        """测试 Repository 子类必须实现所有抽象方法。"""
        from datahub.core.repository import Repository
        
        class IncompleteRepo(Repository):
            pass
        
        with pytest.raises(TypeError):
            IncompleteRepo()


class TestSyncRepository:
    """测试 SyncRepository 同步仓库。"""
    
    @patch('datahub.sync.sync_repo.DatasetRegistry')
    def test_load_from_cache(self, mock_registry):
        """测试从缓存加载数据。"""
        from datahub.sync.sync_repo import SyncRepository
        from datahub.core.query import Query
        from datahub.core.dataset import Dataset, DatasetMeta
        
        # Mock store 和 source
        mock_store = Mock()
        mock_source = Mock()
        
        # Mock 返回缓存数据
        mock_df = pd.DataFrame({'ts_code': ['000001.SZ'], 'close': [10.0]})
        mock_store.load.return_value = mock_df
        
        # Mock registry
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
        mock_registry.get.return_value = (meta, [])
        
        repo = SyncRepository(mock_store, mock_source, auto_save=False)
        query = Query(dataset=Dataset.STOCK_DAILY, date='20240301')
        
        result = repo.load(query)
        
        assert not result.empty
        mock_store.load.assert_called_once()
        mock_source.call.assert_not_called()  # 不应该调用数据源
    
    @patch('datahub.sync.sync_repo.DatasetRegistry')
    def test_load_cache_miss_fetches_from_source(self, mock_registry):
        """测试缓存未命中时从数据源获取。"""
        from datahub.sync.sync_repo import SyncRepository
        from datahub.core.query import Query
        from datahub.core.dataset import Dataset, DatasetMeta
        from datahub.core.exceptions import DataNotFoundError
        
        # Mock store 抛出异常（缓存未命中）
        mock_store = Mock()
        mock_store.load.side_effect = DataNotFoundError("Not found")
        
        # Mock source 返回数据
        mock_source = Mock()
        mock_df = pd.DataFrame({'ts_code': ['000001.SZ'], 'close': [10.0]})
        mock_source.call.return_value = mock_df
        
        # Mock registry
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
        from datahub.core.dataset import FetchStep
        pipeline = [FetchStep(api_name='daily', param_mapping={'trade_date': 'date'})]
        mock_registry.get.return_value = (meta, pipeline)
        
        repo = SyncRepository(mock_store, mock_source, auto_save=False)
        query = Query(dataset=Dataset.STOCK_DAILY, date='20240301')
        
        result = repo.load(query)
        
        assert not result.empty
        mock_store.load.assert_called_once()
        mock_source.call.assert_called()  # 应该调用数据源
    
    def test_check_data_quality(self):
        """测试数据质量检查。"""
        from datahub.sync.sync_repo import SyncRepository
        
        mock_store = Mock()
        mock_source = Mock()
        repo = SyncRepository(mock_store, mock_source)
        
        # 高质量数据
        good_data = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
        assert repo._check_data_quality(good_data) == 0.0
        
        # 低质量数据（50% NaN）
        bad_data = pd.DataFrame({'a': [1, None], 'b': [None, 2]})
        assert repo._check_data_quality(bad_data) == 0.5
        
        # 空数据
        empty_data = pd.DataFrame()
        assert repo._check_data_quality(empty_data) == 1.0


class TestParquetStore:
    """测试 ParquetStore 存储层。"""
    
    def test_parquet_store_init(self):
        """测试 ParquetStore 初始化。"""
        from datahub.store.parquet_store import ParquetStore
        from pathlib import Path
        
        store = ParquetStore(Path('/tmp/test'))
        
        assert store.root == Path('/tmp/test')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
