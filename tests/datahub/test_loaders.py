"""Tests for datahub loaders module."""

import pytest
import pandas as pd
import polars as pl
import numpy as np
import importlib
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

import datahub
from datahub.core.dataset import Dataset
from datahub.data_fields import FIELD_MAPPING, FIELD_DESCRIPTIONS
from datahub.loaders.base import BaseDataLoader, DataLoaderMixin
from datahub.loaders.factor_loader import FactorDataLoader
from datahub.loaders.stock_loader import (
    StockDataLoader,
    _get_stock_pool_from_datahub,
    get_available_industries,
    load_latest_market_data,
)
from datahub.registry import stock as stock_registry
from datahub.registry.stock import DatasetRegistry
class TestBaseDataLoader:
    """测试 BaseDataLoader 基类功能。"""
    
    def test_set_multi_index_basic(self):
        """测试设置 MultiIndex 基本功能。"""
        
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
        
        class ConcreteLoader(BaseDataLoader):
            def load_data(self, **kwargs):
                return pd.DataFrame()
        
        loader = ConcreteLoader()
        result = loader.set_multi_index(pd.DataFrame())
        
        assert result.empty
    
    def test_filter_by_stock_pool_with_multiindex(self):
        """测试基于股票池过滤（MultiIndex）。"""
        
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
        
        loader = StockDataLoader()
        
        assert loader.exclude_st is True
        assert loader.min_list_days == 180
        assert loader.index_code is None
    
    @patch('datahub.loaders.stock_loader.Stock')
    @patch('datahub.loaders.stock_loader.Calendar')
    def test_get_latest_trade_date_success(self, mock_calendar, mock_stock):
        """测试获取最新交易日期成功场景。"""
        
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
        
        # Mock calendar 抛出异常
        mock_cal_instance = Mock()
        mock_cal_instance.latest_trade_date.side_effect = Exception("Error")
        
        loader = StockDataLoader(calendar=mock_cal_instance)
        result = loader._get_latest_trade_date()
        
        # 应该返回当前日期
        expected = datetime.now().strftime("%Y%m%d")
        assert result == expected
    
    def test_calculate_default_dates(self):
        """测试默认日期计算。"""
        
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
        
        loader = FactorDataLoader()
        
        assert loader._stock is not None
        assert loader._calendar is not None
    
    @patch('datahub.loaders.factor_loader.Stock')
    @patch('datahub.loaders.factor_loader.Calendar')
    def test_get_stock_pool_requires_trade_date(self, mock_calendar, mock_stock):
        """测试 get_stock_pool 必须传入 trade_date。"""
        
        loader = FactorDataLoader()
        
        with pytest.raises(ValueError, match="trade_date.*必须显式传入"):
            loader.get_stock_pool()


class TestHelperFunctions:
    """测试辅助函数。"""
    
    @patch('datahub.loaders.stock_loader.Stock')
    def test_get_stock_pool_from_datahub_no_trade_date(self, mock_stock):
        """测试 _get_stock_pool_from_datahub 在没有 trade_date 时抛出异常。"""
        
        with pytest.raises(ValueError, match="trade_date.*必须显式传入"):
            _get_stock_pool_from_datahub(mock_stock())
    
    @patch('datahub.loaders.stock_loader.Stock')
    def test_get_stock_pool_from_datahub_with_universe(self, mock_stock):
        """测试 _get_stock_pool_from_datahub 正常获取股票池。"""
        
        # Mock universe 数据 (polars)
        mock_stock_instance = Mock()
        mock_universe = pl.DataFrame({
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
        """测试 load_market_data 已被移除(业务逻辑应在调用方实现)。"""
        # 该函数已删除,因为依赖外部模块
        with pytest.raises(ImportError):
            from datahub.loaders.stock_loader import load_market_data
            load_market_data()

    @patch('datahub.loaders.stock_loader.StockDataLoader')
    def test_load_latest_market_data(self, mock_loader_class):
        """测试加载最新市场数据。"""
        
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
    
    @patch('datahub.loaders.stock_loader.StockDataLoader')
    def test_get_available_industries_with_data(self, mock_loader_class):
        """测试获取行业列表（带数据）。"""
        
        # Mock loader
        mock_loader = Mock()
        mock_loader.get_available_industries.return_value = ['证券', '银行']  # sorted
        mock_loader_class.return_value = mock_loader
        
        data = pl.DataFrame({'industry': ['银行', '证券']})
        result = get_available_industries(data)
        
        # 结果是排序后的
        assert result == ['证券', '银行']


class TestTushareFieldMapping:
    """测试 Tushare 字段映射配置。"""
    
    def test_volume_ratio_field_name(self):
        """测试量比字段名正确性（应为 volume_ratio 而非 vol_ratio）。"""
        
        # 验证中文到英文的映射
        assert FIELD_MAPPING['量比'] == 'volume_ratio'
        
        # 验证字段描述存在
        assert 'volume_ratio' in FIELD_DESCRIPTIONS
        assert FIELD_DESCRIPTIONS['volume_ratio'] == '量比'
    
    def test_daily_basic_fields_completeness(self):
        """测试 daily_basic 接口字段完整性。"""
        
        # 验证所有估值指标字段都存在
        required_fields = [
            'turnover_rate', 'turnover_rate_f', 'volume_ratio',
            'pe', 'pe_ttm', 'pb', 'ps', 'ps_ttm',
            'dv_ratio', 'dv_ttm',
            'total_share', 'float_share', 'free_share',
            'total_mv', 'circ_mv'
        ]
        
        # 检查这些字段是否在映射中（通过中文名或英文名）
        field_values = set(FIELD_MAPPING.values())
        for field in required_fields:
            assert field in field_values, f"字段 {field} 缺失"
    
    def test_field_mapping_consistency(self):
        """测试字段映射一致性（registry 和 data_fields 应该一致）。"""
        
        # 重新导入 registry 模块以确保注册（避免被其他测试的 mock 影响）
        importlib.reload(datahub.registry.stock)
        
        
        # 获取 STOCK_DAILY 的 daily_basic 步骤配置
        result = DatasetRegistry.get(Dataset.STOCK_DAILY)
        # DatasetRegistry.get 返回 (meta, pipeline) 元组
        if isinstance(result, tuple):
            meta, pipeline = result
        else:
            pipeline = result.pipeline if hasattr(result, 'pipeline') else []
        
        daily_basic_step = None
        for step in pipeline:
            if step.api_name == 'daily_basic':
                daily_basic_step = step
                break
        
        assert daily_basic_step is not None, "daily_basic 步骤不存在"
        
        # 验证关键字段都在配置中
        expected_fields = ['volume_ratio', 'turnover_rate', 'pe', 'pb', 'total_mv']
        for field in expected_fields:
            assert field in daily_basic_step.fields, f"字段 {field} 不在 daily_basic 配置中"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
