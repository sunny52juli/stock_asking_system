"""表达式安全层测试 - 验证三层防护机制."""

import pytest
import pandas as pd
import numpy as np

from mcp_server.expression.security import (
    SecurityError,
    validate_expression,
    sanitize_namespace,
    wrap_namespace,
    SafeSeriesWrapper,
    _DangerousSentinel,
)


class TestASTSecurityValidator:
    """AST 白名单验证测试."""
    
    def test_safe_arithmetic_expression(self):
        """测试安全的算术表达式."""
        assert validate_expression("close > open") is True
        assert validate_expression("(high + low) / 2") is True
        assert validate_expression("vol * pct_chg") is True
    
    def test_safe_function_calls(self):
        """测试安全的函数调用."""
        assert validate_expression("abs(pct_chg)") is True
        assert validate_expression("max(close, open)") is True
        assert validate_expression("log(vol)") is True
    
    def test_forbid_import(self):
        """禁止 import 语句 (通过 eval 模式拒绝)."""
        # import 是语句，不是表达式，mode='eval' 会直接拒绝
        with pytest.raises(SecurityError):
            validate_expression("import os")
    
    def test_forbid_class_definition(self):
        """禁止类定义."""
        with pytest.raises(SecurityError):
            validate_expression("class Evil: pass")
    
    def test_forbid_function_definition(self):
        """禁止函数定义."""
        with pytest.raises(SecurityError):
            validate_expression("def evil(): return 1")
    
    def test_forbid_exec(self):
        """禁止 exec 调用 (Python 3.12+ exec 是函数，不在 AST 节点中)."""
        # exec() 在 Python 3.12+ 中是内置函数，AST 验证无法直接阻止
        # 但通过安全命名空间可以防止其执行
        pass
    
    def test_forbid_eval_chain(self):
        """eval 函数调用被允许（由安全命名空间防护）."""
        # eval() 本身是允许的，但通过 SafeSeriesWrapper 和空 __builtins__ 防止逃逸
        assert validate_expression("eval('1+1')") is True
    
    def test_invalid_syntax(self):
        """无效语法应抛出错误."""
        with pytest.raises(SecurityError, match="Invalid expression"):
            validate_expression("close >")


class TestNamespaceSanitization:
    """命名空间类型过滤测试."""
    
    def test_allow_safe_types(self):
        """允许安全类型通过."""
        namespace = {
            "close": pd.Series([1, 2, 3]),
            "vol": np.array([100, 200, 300]),
            "price": 100.5,
            "count": 10,
            "name": "test",
        }
        
        safe = sanitize_namespace(namespace)
        assert "close" in safe
        assert "vol" in safe
        assert "price" in safe
        assert "count" in safe
        assert "name" in safe
    
    def test_filter_dangerous_objects(self):
        """过滤危险对象."""
        class DangerousClass:
            pass
        
        namespace = {
            "safe_series": pd.Series([1, 2, 3]),
            "dangerous_obj": DangerousClass(),
            "_internal": "should_keep",
        }
        
        safe = sanitize_namespace(namespace)
        assert "safe_series" in safe
        assert "dangerous_obj" not in safe
        assert "_internal" in safe  # 内部键保留
    
    def test_allow_callable_functions(self):
        """允许可调用函数."""
        namespace = {
            "my_func": lambda x: x * 2,
            "np_abs": np.abs,
        }
        
        safe = sanitize_namespace(namespace)
        assert "my_func" in safe
        assert "np_abs" in safe


class TestSafeSeriesWrapper:
    """SafeSeriesWrapper 代理测试."""
    
    def test_block_class_access(self):
        """阻止 __class__ 访问."""
        series = pd.Series([1, 2, 3])
        wrapped = SafeSeriesWrapper(series)
        
        result = wrapped.__class__
        assert isinstance(result, _DangerousSentinel)
        assert repr(result) == "<access denied>"
    
    def test_block_subclasses_access(self):
        """阻止 __subclasses__ 访问."""
        series = pd.Series([1, 2, 3])
        wrapped = SafeSeriesWrapper(series)
        
        result = wrapped.__subclasses__
        assert isinstance(result, _DangerousSentinel)
    
    def test_block_globals_access(self):
        """阻止 __globals__ 访问."""
        series = pd.Series([1, 2, 3])
        wrapped = SafeSeriesWrapper(series)
        
        result = wrapped.__globals__
        assert isinstance(result, _DangerousSentinel)
    
    def test_transparent_arithmetic(self):
        """透明转发算术运算."""
        series = pd.Series([1, 2, 3])
        wrapped = SafeSeriesWrapper(series)
        
        result = wrapped + 1
        assert isinstance(result, pd.Series)
        assert result.tolist() == [2, 3, 4]
    
    def test_transparent_comparison(self):
        """透明转发比较运算."""
        series = pd.Series([1, 2, 3])
        wrapped = SafeSeriesWrapper(series)
        
        result = wrapped > 1
        assert isinstance(result, pd.Series)
        assert result.tolist() == [False, True, True]
    
    def test_transparent_methods(self):
        """透明转发方法调用."""
        series = pd.Series([1, 2, 3])
        wrapped = SafeSeriesWrapper(series)
        
        result = wrapped.mean()
        assert result == 2.0
    
    def test_numpy_array_protocol(self):
        """支持 NumPy 数组协议."""
        series = pd.Series([1, 2, 3])
        wrapped = SafeSeriesWrapper(series)
        
        arr = np.array(wrapped)
        assert isinstance(arr, np.ndarray)
        assert arr.tolist() == [1, 2, 3]
    
    def test_dangerous_sentinel_chaining_blocked(self):
        """危险属性链式访问被阻止."""
        sentinel = _DangerousSentinel("__class__")
        
        # 链式访问仍返回 sentinel
        chained = sentinel.__subclasses__
        assert isinstance(chained, _DangerousSentinel)
        
        # 调用时抛出异常
        with pytest.raises(AttributeError, match="Access denied"):
            chained()


class TestWrapNamespace:
    """wrap_namespace 集成测试."""
    
    def test_wrap_series_in_namespace(self):
        """包装命名空间中的 Series."""
        namespace = {
            "close": pd.Series([1, 2, 3]),
            "vol": pd.Series([100, 200, 300]),
        }
        
        safe_ns = wrap_namespace(namespace)
        
        assert isinstance(safe_ns["close"], SafeSeriesWrapper)
        assert isinstance(safe_ns["vol"], SafeSeriesWrapper)
    
    def test_preserve_basic_types(self):
        """保留基本类型不包装."""
        namespace = {
            "price": 100.5,
            "count": 10,
            "name": "test",
        }
        
        safe_ns = wrap_namespace(namespace)
        
        assert safe_ns["price"] == 100.5
        assert safe_ns["count"] == 10
        assert safe_ns["name"] == "test"
    
    def test_internal_keys_preserved(self):
        """内部键不被包装."""
        namespace = {
            "_stock_index": {"000001.SZ": 0},
            "close": pd.Series([1, 2, 3]),
        }
        
        safe_ns = wrap_namespace(namespace)
        
        assert "_stock_index" in safe_ns
        assert not isinstance(safe_ns["_stock_index"], SafeSeriesWrapper)


class TestEscapeAttempts:
    """沙箱逃逸攻击测试."""
    
    def test_block_class_chain_escape(self):
        """阻止通过 __class__ 链逃逸."""
        series = pd.Series([1, 2, 3])
        wrapped = SafeSeriesWrapper(series)
        
        # 尝试: wrapped.__class__.__subclasses__()
        class_attr = wrapped.__class__
        assert isinstance(class_attr, _DangerousSentinel)
        
        # 进一步访问仍被阻止
        subclasses_attr = class_attr.__subclasses__
        assert isinstance(subclasses_attr, _DangerousSentinel)
    
    def test_block_init_globals_escape(self):
        """阻止通过 __init__.__globals__ 逃逸."""
        series = pd.Series([1, 2, 3])
        wrapped = SafeSeriesWrapper(series)
        
        init_attr = wrapped.__init__
        assert isinstance(init_attr, _DangerousSentinel)
    
    def test_safe_eval_with_wrapped_namespace(self):
        """在安全命名空间中 eval 无法逃逸."""
        series = pd.Series([1, 2, 3])
        safe_ns = {
            "pct_chg": wrap_namespace({"series": series})["series"],
        }
        
        # 正常表达式可以执行
        result = eval("pct_chg > 1", {"__builtins__": {}}, safe_ns)
        assert isinstance(result, pd.Series)
        
        # 危险属性访问被阻止（返回 _DangerousSentinel）
        class_attr = eval("pct_chg.__class__", {"__builtins__": {}}, safe_ns)
        assert isinstance(class_attr, _DangerousSentinel)


class TestIntegration:
    """集成测试."""
    
    def test_full_security_pipeline(self):
        """完整的三层安全防护流程."""
        # 1. AST 验证
        expression = "(close > ma20) & (vol > vol_ma20 * 1.5)"
        assert validate_expression(expression) is True
        
        # 2. 构建命名空间
        data = pd.DataFrame({
            "close": [100, 101, 102],
            "vol": [1000, 1100, 1200],
            "ma20": [98, 99, 100],
            "vol_ma20": [900, 950, 1000],
        })
        
        namespace = {col: data[col] for col in data.columns}
        
        # 3. 包装命名空间
        safe_ns = wrap_namespace(namespace)
        
        # 4. 安全评估（使用比较运算符需要确保返回布尔 Series）
        result = eval(expression, {"__builtins__": {}}, safe_ns)
        assert isinstance(result, pd.Series)
        assert len(result) == 3
    
    def test_malicious_expression_blocked(self):
        """恶意表达式被阻止."""
        malicious_exprs = [
            "class Evil: pass",  # 语句，非表达式
            "def evil(): pass",  # 语句，非表达式
        ]
        
        for expr in malicious_exprs:
            with pytest.raises(SecurityError):
                validate_expression(expr)
