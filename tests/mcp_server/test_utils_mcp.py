"""测试 utils/mcp 模块 - 表达式解析、安全验证、命名空间构建."""

import pytest
import pandas as pd
import numpy as np

from utils.mcp import (
    ExpressionParser,
    ASTSecurityValidator,
    SecurityError,
    validate_expression,
    NamespaceBuilder,
    ExpressionEvaluator,
    evaluate_expression,
)


class TestExpressionParser:
    """测试表达式解析器."""
    
    def test_parse_chinese_fields(self):
        """测试中文字段替换."""
        parser = ExpressionParser()
        
        # 基础字段替换
        assert parser.parse_expression("收盘价 > 开盘价") == "close > open"
        assert parser.parse_expression("最高价 - 最低价") == "high - low"
        assert parser.parse_expression("成交量 * 收盘价") == "vol * close"
    
    def test_parse_n_day_pattern(self):
        """测试 N 日字段模式."""
        parser = ExpressionParser()
        
        # N日字段名 -> 字段名_Nd
        assert parser.parse_expression("5日close") == "close_5d"
        assert parser.parse_expression("10日high") == "high_10d"
        
        # N日平均字段名 -> 字段名_avg_Nd
        assert parser.parse_expression("5日平均close") == "close_avg_5d"
        assert parser.parse_expression("20日平均vol") == "vol_avg_20d"
    
    def test_extract_variables(self):
        """测试变量提取."""
        parser = ExpressionParser()
        
        # 简单表达式
        vars_list = parser.extract_variables("close + open")
        assert "close" in vars_list
        assert "open" in vars_list
        
        # 过滤关键字
        vars_list = parser.extract_variables("np.abs(close)")
        assert "close" in vars_list
        assert "np" not in vars_list  # np 在关键字列表中
        assert "abs" not in vars_list  # abs 在关键字列表中
        
        # 复杂表达式
        vars_list = parser.extract_variables("MA5 + RSI14")
        assert "MA5" in vars_list
        assert "RSI14" in vars_list
    
    def test_mixed_chinese_english(self):
        """测试中英文混合表达式."""
        parser = ExpressionParser()
        
        expr = "收盘价 > MA5 and 成交量 > 10日平均vol"
        parsed = parser.parse_expression(expr)
        
        assert "close" in parsed
        assert "MA5" in parsed
        assert "vol" in parsed
        assert "vol_avg_10d" in parsed


class TestSecurityValidator:
    """测试安全验证器."""
    
    def test_validate_safe_expression(self):
        """测试安全表达式验证."""
        # 基本数学运算
        assert validate_expression("close + open") is True
        assert validate_expression("high - low") is True
        assert validate_expression("close * vol") is True
        assert validate_expression("close / open") is True
    
    def test_validate_pandas_operations(self):
        """测试 pandas 操作验证."""
        assert validate_expression("close.rolling(5).mean()") is True
        assert validate_expression("close.diff()") is True
        assert validate_expression("close.pct_change()") is True
        assert validate_expression("close.rank()") is True
    
    def test_validate_numpy_functions(self):
        """测试 numpy 函数验证."""
        assert validate_expression("np.abs(close)") is True
        assert validate_expression("np.log(close)") is True
        assert validate_expression("np.sqrt(close)") is True
    
    def test_reject_import(self):
        """测试拒绝 import 语句."""
        # ast.parse 在 mode='eval' 下会直接抛出 SyntaxError
        with pytest.raises((SecurityError, SyntaxError)):
            validate_expression("__import__('os')")
        
        with pytest.raises((SecurityError, SyntaxError)):
            validate_expression("import os")
    
    def test_reject_function_definition(self):
        """测试拒绝函数定义."""
        with pytest.raises(SecurityError):
            validate_expression("def malicious(): pass")
    
    def test_reject_class_definition(self):
        """测试拒绝类定义."""
        with pytest.raises(SecurityError):
            validate_expression("class Malicious: pass")
    
    def test_invalid_syntax(self):
        """测试无效语法."""
        with pytest.raises(SecurityError):
            validate_expression("close +")


class TestNamespaceBuilder:
    """测试命名空间构建器."""
    
    @pytest.fixture
    def sample_data(self):
        """创建示例数据."""
        return pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'],
            'open': [10.0, 20.0],
            'high': [11.0, 21.0],
            'low': [9.5, 19.5],
            'close': [10.5, 20.5],
            'vol': [1000, 2000],
        })
    
    def test_build_basic_namespace(self, sample_data):
        """测试构建基础命名空间."""
        builder = NamespaceBuilder()
        namespace = builder.build_namespace(sample_data)
        
        # 检查数据列
        assert 'open' in namespace
        assert 'close' in namespace
        assert 'high' in namespace
        assert 'low' in namespace
        assert 'vol' in namespace
        
        # 检查 numpy/pandas
        assert 'np' in namespace
        assert 'pd' in namespace
        
        # 检查 numpy 函数
        assert 'abs' in namespace
        assert 'log' in namespace
        assert 'sqrt' in namespace
    
    def test_build_namespace_with_computed_vars(self, sample_data):
        """测试带计算变量的命名空间."""
        computed = {'MA5': pd.Series([10.0, 20.0])}
        builder = NamespaceBuilder()
        namespace = builder.build_namespace(sample_data, computed)
        
        assert 'MA5' in namespace
        assert 'close' in namespace
    
    def test_infer_ma_indicator(self, sample_data):
        """测试推断 MA 指标."""
        builder = NamespaceBuilder()
        namespace = builder.build_namespace(sample_data)
        namespace = builder.infer_and_add_variables(namespace, sample_data, ['MA5'])
        
        assert 'MA5' in namespace
        assert isinstance(namespace['MA5'], pd.Series)
    
    def test_infer_ema_indicator(self, sample_data):
        """测试推断 EMA 指标."""
        builder = NamespaceBuilder()
        namespace = builder.build_namespace(sample_data)
        namespace = builder.infer_and_add_variables(namespace, sample_data, ['EMA12'])
        
        assert 'EMA12' in namespace
        assert isinstance(namespace['EMA12'], pd.Series)
    
    def test_infer_rsi_indicator(self, sample_data):
        """测试推断 RSI 指标."""
        builder = NamespaceBuilder()
        namespace = builder.build_namespace(sample_data)
        namespace = builder.infer_and_add_variables(namespace, sample_data, ['RSI14'])
        
        assert 'RSI14' in namespace
        assert isinstance(namespace['RSI14'], pd.Series)
    
    def test_unknown_variable_not_added(self, sample_data):
        """测试未知变量不添加."""
        builder = NamespaceBuilder()
        namespace = builder.build_namespace(sample_data)
        namespace = builder.infer_and_add_variables(namespace, sample_data, ['UNKNOWN_VAR'])
        
        assert 'UNKNOWN_VAR' not in namespace


class TestExpressionEvaluator:
    """测试表达式评估器."""
    
    @pytest.fixture
    def sample_data(self):
        """创建示例数据."""
        dates = pd.date_range('2024-01-01', periods=10)
        return pd.DataFrame({
            'ts_code': ['000001.SZ'] * 10,
            'open': np.arange(10, 20, dtype=float),
            'high': np.arange(11, 21, dtype=float),
            'low': np.arange(9, 19, dtype=float),
            'close': np.arange(10.5, 20.5, dtype=float),
            'vol': np.arange(1000, 2000, 100, dtype=float),
        }, index=dates)
    
    def test_evaluate_simple_expression(self, sample_data):
        """测试简单表达式评估."""
        evaluator = ExpressionEvaluator()
        result = evaluator.evaluate("close - open", sample_data)
        
        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_data)
        assert all(result == 0.5)  # close - open = 0.5
    
    def test_evaluate_with_numpy(self, sample_data):
        """测试带 numpy 函数的表达式."""
        evaluator = ExpressionEvaluator()
        result = evaluator.evaluate("np.abs(close - open)", sample_data)
        
        assert isinstance(result, pd.Series)
        assert all(result == 0.5)
    
    def test_evaluate_with_pandas_method(self, sample_data):
        """测试带 pandas 方法的表达式."""
        evaluator = ExpressionEvaluator()
        result = evaluator.evaluate("close.rolling(3).mean()", sample_data)
        
        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_data)
        # 前两个值为 NaN（窗口不足）
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert not pd.isna(result.iloc[2])
    
    def test_evaluate_chinese_expression(self, sample_data):
        """测试中文表达式."""
        evaluator = ExpressionEvaluator()
        result = evaluator.evaluate("收盘价 - 开盘价", sample_data)
        
        assert isinstance(result, pd.Series)
        assert all(result == 0.5)
    
    def test_evaluate_with_computed_vars(self, sample_data):
        """测试带预计算变量的表达式."""
        computed = {'MA5': sample_data['close'].rolling(5).mean()}
        evaluator = ExpressionEvaluator()
        result = evaluator.evaluate("close - MA5", sample_data, computed)
        
        assert isinstance(result, pd.Series)
    
    def test_evaluate_security_check(self, sample_data):
        """测试安全验证."""
        evaluator = ExpressionEvaluator()
        
        # 安全表达式应该成功
        result = evaluator.evaluate("close + open", sample_data)
        assert isinstance(result, pd.Series)
        
        # 不安全表达式应该抛出异常
        with pytest.raises(Exception):
            evaluator.evaluate("__import__('os')", sample_data)
    
    def test_convenience_function(self, sample_data):
        """测试便捷函数."""
        result = evaluate_expression("close * 2", sample_data)
        
        assert isinstance(result, pd.Series)
        assert all(result == sample_data['close'] * 2)


class TestIntegration:
    """集成测试."""
    
    @pytest.mark.slow
    def test_full_pipeline(self):
        """测试完整流程：解析 -> 验证 -> 评估."""
        # 创建测试数据
        dates = pd.date_range('2024-01-01', periods=20)
        data = pd.DataFrame({
            'close': np.random.randn(20).cumsum() + 100,
            'open': np.random.randn(20).cumsum() + 99,
            'vol': np.random.randint(1000, 5000, 20),
        }, index=dates)
        
        # 1. 解析中文表达式
        parser = ExpressionParser()
        chinese_expr = "收盘价 > 5日平均收盘价"
        parsed = parser.parse_expression(chinese_expr)
        
        # 2. 验证安全性
        assert validate_expression(parsed) is True
        
        # 3. 构建命名空间并添加计算变量
        builder = NamespaceBuilder()
        namespace = builder.build_namespace(data)
        # close_avg_5d 需要从 close 列计算，使用 rolling().mean()
        namespace['close_avg_5d'] = data['close'].rolling(5).mean()
        
        # 4. 评估表达式
        evaluator = ExpressionEvaluator()
        result = evaluator.evaluate_with_namespace(parsed, namespace)
        
        assert isinstance(result, pd.Series)
        assert len(result) == len(data)
        assert result.dtype == bool
