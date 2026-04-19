"""测试 MCP Server 执行器模块."""

import pytest
import pandas as pd
import polars as pl
import numpy as np

from mcp_server.executors import (
    execute_tool,
    get_available_tools,
    TOOL_FUNCTIONS,
)


class TestExecutorsInit:
    """测试执行器初始化."""
    
    def test_tool_functions_registered(self):
        """测试工具函数已注册."""
        assert len(TOOL_FUNCTIONS) > 0
        
        # 检查各类工具是否存在
        assert 'abs_value' in TOOL_FUNCTIONS
        assert 'rolling_mean' in TOOL_FUNCTIONS
        assert 'rsi' in TOOL_FUNCTIONS
        assert 'correlation' in TOOL_FUNCTIONS
    
    def test_get_available_tools(self):
        """测试获取可用工具列表."""
        tools = get_available_tools()
        
        assert isinstance(tools, list)
        assert len(tools) > 0
        assert 'abs_value' in tools
        assert 'macd' in tools
    
    def test_execute_tool_unknown_tool(self):
        """测试执行未知工具."""
        with pytest.raises(ValueError, match="Unknown tool"):
            execute_tool("nonexistent_tool", data=pd.DataFrame())
    
    def test_execute_tool_missing_data(self):
        """测试缺少 data 参数."""
        with pytest.raises(ValueError, match="requires 'data' parameter"):
            execute_tool("abs_value", column="close")


class TestMathTools:
    """测试数学工具."""
    
    @pytest.fixture
    def sample_data(self):
        """创建示例数据."""
        return pl.DataFrame({
            'value': [-2.0, -1.0, 0.0, 1.0, 2.0],
            'positive': [1.0, 2.0, 3.0, 4.0, 5.0],
        })
    
    def test_abs_value(self, sample_data):
        """测试绝对值."""
        result = execute_tool("abs_value", data=sample_data, column="value")
        
        assert isinstance(result, pl.Series)
        expected = pl.Series([2.0, 1.0, 0.0, 1.0, 2.0])
        assert result.equals(expected)
    
    def test_log_transform(self, sample_data):
        """测试对数变换."""
        result = execute_tool("log_transform", data=sample_data, column="positive")
        
        assert isinstance(result, pl.Series)
        expected = np.log1p(sample_data['positive'])
        assert result.equals(expected)
    
    def test_sqrt_transform(self, sample_data):
        """测试平方根变换."""
        result = execute_tool("sqrt_transform", data=sample_data, column="positive")
        
        assert isinstance(result, pl.Series)
        expected = np.sqrt(sample_data['positive'])
        assert result.equals(expected)
    
    def test_power_transform(self, sample_data):
        """测试幂次变换."""
        result = execute_tool("power_transform", data=sample_data, column="positive", power=2)
        
        assert isinstance(result, pl.Series)
        expected = sample_data['positive'] ** 2
        assert result.equals(expected)
    
    def test_rank_normalize(self, sample_data):
        """测试排名归一化."""
        result = execute_tool("rank_normalize", data=sample_data, column="positive")
        
        assert result.min() >= 0
        assert result.max() <= 1
        assert len(result) == len(sample_data)
    
    def test_zscore_normalize(self, sample_data):
        """测试 Z-score 标准化."""
        result = execute_tool("zscore_normalize", data=sample_data, column="positive")
        
        # Z-score 均值应接近 0，标准差应接近 1
        assert abs(result.mean()) < 1e-10
        assert abs(result.std() - 1.0) < 1e-10


class TestTimeSeriesTools:
    """测试时间序列工具."""
    
    @pytest.fixture
    def time_series_data(self):
        """创建时间序列数据."""
        return pl.DataFrame({
            'ts_code': ['000001.SZ'] * 20,
            'trade_date': [f'202401{i+1:02d}' for i in range(20)],
            'close': np.arange(100, 120, dtype=float),
            'high': np.arange(101, 121, dtype=float),
            'low': np.arange(99, 119, dtype=float),
            'vol': np.arange(1000, 2000, 50, dtype=float),
        })
    
    def test_rolling_mean(self, time_series_data):
        """测试移动平均."""
        result = execute_tool("rolling_mean", data=time_series_data, column="close", window=5)
        
        assert isinstance(result, pl.Series)
        assert len(result) == len(time_series_data)
        # 前 4 个值为 null
        assert result.null_count() >= 4
    
    def test_pct_change(self, time_series_data):
        """测试百分比变化."""
        result = execute_tool("pct_change", data=time_series_data, column="close", periods=1)
        
        assert isinstance(result, pl.Series)
        # close 是等差数列，pct_change 应该递减
        assert result[1] > 0
    
    def test_rolling_std(self, time_series_data):
        """测试移动标准差."""
        result = execute_tool("rolling_std", data=time_series_data, column="close", window=5)
        
        assert isinstance(result, pl.Series)
        # 等差数列的标准差应该是常数（忽略 null）
        non_null = result.drop_nulls()
        assert len(non_null.unique()) == 1
    
    def test_rolling_max(self, time_series_data):
        """测试移动最大值."""
        result = execute_tool("rolling_max", data=time_series_data, column="close", window=5)
        
        assert isinstance(result, pl.Series)
        # 递增序列的 rolling max 应该等于当前值（从第 5 个开始）
        assert result[4] == time_series_data['close'][4]
    
    def test_ewm(self, time_series_data):
        """测试指数加权移动平均."""
        result = execute_tool("ewm", data=time_series_data, column="close", span=12)
        
        assert isinstance(result, pl.Series)
        assert len(result) == len(time_series_data)
    
    def test_price_change(self, time_series_data):
        """测试价格涨幅."""
        result = execute_tool("price_change", data=time_series_data, column="close", periods=1)
        
        assert isinstance(result, pl.Series)
        # 等差数列的价格涨幅应该递减
        assert result[1] > 0
    
    def test_high_in_period(self, time_series_data):
        """测试近期最高价."""
        result = execute_tool("high_in_period", data=time_series_data, column="high", window=5)
        
        assert isinstance(result, pl.Series)
        # 递增序列的 rolling max 应该等于当前值
        assert result[-1] == time_series_data['high'][-1]


class TestTechnicalTools:
    """测试技术指标工具."""
    
    @pytest.fixture
    def ohlcv_data(self):
        """创建 OHLCV 数据."""
        np.random.seed(42)
        return pl.DataFrame({
            'ts_code': ['000001.SZ'] * 30,
            'trade_date': [f'202401{i+1:02d}' for i in range(30)],
            'open': 100 + np.random.randn(30).cumsum(),
            'high': 102 + np.random.randn(30).cumsum(),
            'low': 98 + np.random.randn(30).cumsum(),
            'close': 100 + np.random.randn(30).cumsum(),
            'vol': np.random.randint(1000, 5000, 30),
            'pre_close': 100 + np.random.randn(30).cumsum(),
        })
    
    def test_rsi(self, ohlcv_data):
        """测试 RSI 指标."""
        result = execute_tool("rsi", data=ohlcv_data, column="close", window=14)
        
        assert isinstance(result, pl.Series)
        assert len(result) == len(ohlcv_data)
        # RSI 应该在 0-100 之间（忽略 NaN）
        non_nan = result.drop_nulls()
        assert (non_nan >= 0).all() and (non_nan <= 100).all()
    
    def test_macd(self, ohlcv_data):
        """测试 MACD 指标."""
        result = execute_tool("macd", data=ohlcv_data, column="close", fast=12, slow=26, signal=9)
        
        assert isinstance(result, pl.Series)
        assert len(result) == len(ohlcv_data)
    
    def test_kdj(self, ohlcv_data):
        """测试 KDJ 指标."""
        result = execute_tool("kdj", data=ohlcv_data, high="high", low="low", close="close", window=9)
        
        assert isinstance(result, pl.Series)
        assert len(result) == len(ohlcv_data)
    
    def test_atr(self, ohlcv_data):
        """测试 ATR 指标."""
        result = execute_tool("atr", data=ohlcv_data, high="high", low="low", close="close", window=14)
        
        assert isinstance(result, pl.Series)
        assert len(result) == len(ohlcv_data)
        # ATR 应该非负
        non_nan = result.drop_nulls()
        assert (non_nan >= 0).all()
    
    def test_obv(self, ohlcv_data):
        """测试 OBV 指标."""
        result = execute_tool("obv", data=ohlcv_data, close="close", vol="vol")
        
        assert isinstance(result, pl.Series)
        assert len(result) == len(ohlcv_data)
    
    def test_amplitude(self, ohlcv_data):
        """测试振幅指标."""
        result = execute_tool("amplitude", data=ohlcv_data, high="high", low="low", pre_close="pre_close", window=5)
        
        assert isinstance(result, pl.Series)
        assert len(result) == len(ohlcv_data)
    
    def test_volume_ratio(self, ohlcv_data):
        """测试成交量比率."""
        result = execute_tool("volume_ratio", data=ohlcv_data, column="vol", window=5)
        
        assert isinstance(result, pl.Series)
        assert len(result) == len(ohlcv_data)
    
    def test_close_above_high(self, ohlcv_data):
        """测试突破判断."""
        result = execute_tool("close_above_high", data=ohlcv_data, column="close", high_column="high", window=20)
        
        assert isinstance(result, pl.Series)
        assert len(result) == len(ohlcv_data)
        # 结果应该是 0 或 1
        non_nan = result.drop_nulls()
        assert set(non_nan.unique()).issubset({0, 1})


class TestStatisticalTools:
    """测试统计工具."""
    
    @pytest.fixture
    def stats_data(self):
        """创建统计数据."""
        np.random.seed(42)
        return pl.DataFrame({
            'ts_code': ['000001.SZ'] * 30,
            'trade_date': [f'202401{i+1:02d}' for i in range(30)],
            'x': np.random.randn(30),
            'y': np.random.randn(30),
            'z': np.random.randn(30),
        })
    
    def test_correlation(self, stats_data):
        """测试相关系数."""
        result = execute_tool("correlation", data=stats_data, x="x", y="y", window=10)
        
        assert isinstance(result, pl.Series)
        assert len(result) == len(stats_data)
        # 相关系数应该在 -1 到 1 之间（忽略 NaN/null）
        non_null = result.drop_nulls()
        if len(non_null) > 0:
            # 过滤掉NaN值
            valid = non_null.filter((non_null >= -1) & (non_null <= 1))
            assert len(valid) == len(non_null), f"存在超出范围的相关系数: {non_null}"
    
    def test_skewness(self, stats_data):
        """测试偏度."""
        result = execute_tool("skewness", data=stats_data, column="x", window=10)
        
        assert isinstance(result, pl.Series)
        assert len(result) == len(stats_data)
    
    def test_kurtosis(self, stats_data):
        """测试峰度."""
        result = execute_tool("kurtosis", data=stats_data, column="x", window=10)
        
        assert isinstance(result, pl.Series)
        assert len(result) == len(stats_data)


class TestFeatureEngineeringTools:
    """测试特征工程工具."""
    
    @pytest.fixture
    def feature_data(self):
        """创建特征数据."""
        dates = pd.date_range('2024-01-01', periods=20)
        return pl.DataFrame({
            'value': np.random.randn(20),
        })
    
    def test_ts_rank(self, feature_data):
        """测试时间序列排名."""
        result = execute_tool("ts_rank", data=feature_data, column="value", window=10)
        
        assert isinstance(result, pl.Series)
        assert len(result) == len(feature_data)
        # 排名应该在 0-1 之间（忽略 NaN）
        non_nan = result.drop_nulls()
        assert (non_nan >= 0).all() and (non_nan <= 1).all()
    
    def test_ts_argmax(self, feature_data):
        """测试时间序列最大值位置."""
        result = execute_tool("ts_argmax", data=feature_data, column="value", window=10)
        
        assert isinstance(result, pl.Series)
        assert len(result) == len(feature_data)
    
    def test_ts_argmin(self, feature_data):
        """测试时间序列最小值位置."""
        result = execute_tool("ts_argmin", data=feature_data, column="value", window=10)
        
        assert isinstance(result, pl.Series)
        assert len(result) == len(feature_data)
    
    def test_decay_linear(self, feature_data):
        """测试线性衰减加权平均."""
        result = execute_tool("decay_linear", data=feature_data, column="value", window=10)
        
        assert isinstance(result, pl.Series)
        assert len(result) == len(feature_data)


class TestRiskMetricsTools:
    """测试风险度量工具."""
    
    @pytest.fixture
    def returns_data(self):
        """创建收益率数据."""
        dates = pd.date_range('2024-01-01', periods=60)
        np.random.seed(42)
        return pl.DataFrame({
            'returns': np.random.randn(60) * 0.02,  # 日收益率
        })
    
    def test_volatility(self, returns_data):
        """测试波动率."""
        result = execute_tool("volatility", data=returns_data, column="returns", window=20)
        
        assert isinstance(result, pl.Series)
        assert len(result) == len(returns_data)
        # 波动率应该非负
        non_nan = result.drop_nulls()
        assert (non_nan >= 0).all()
    
    def test_max_drawdown(self, returns_data):
        """测试最大回撤."""
        # 将收益率转换为累计收益
        cumulative = (1 + returns_data['returns']).cum_sum()
        data = returns_data.with_columns(cumulative=cumulative)
        
        result = execute_tool("max_drawdown", data=data, column="cumulative", window=60)
        
        assert isinstance(result, pl.Series)
        assert len(result) == len(data)
        # 最大回撤应该非正
        non_nan = result.drop_nulls()
        assert (non_nan <= 0).all()


class TestScreeningTools:
    """测试筛选工具."""
    
    @pytest.fixture
    def stock_data(self):
        """创建股票数据."""
        return pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ', '600000.SH', '600001.SH', '830001.BJ'],
            'industry': ['银行', '地产', '银行', '保险', '科技'],
            'close': [10.0, 20.0, 15.0, 25.0, 30.0],
        })
    
    # 注意：filter_by_industry 和 filter_by_market 已移除
    # 行业和市场过滤应在 StockPoolService 层面统一处理（预筛选阶段）
    # 不应作为 MCP tools 暴露给 Agent
