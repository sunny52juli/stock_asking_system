"""测试新增的指数相关性工具."""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from mcp_server.executors.index_tools import (
    beta,
    alpha,
    outperform_rate,
    correlation_with_index,
    tracking_error,
    information_ratio,
)


def generate_test_data(n_days=120):
    """生成测试数据（股票和指数价格）."""
    dates = pd.date_range('2025-01-01', periods=n_days, freq='D')
    
    # 模拟指数价格（随机游走）
    np.random.seed(42)
    index_returns = np.random.normal(0.0005, 0.015, n_days)
    index_prices = 100 * np.cumprod(1 + index_returns)
    
    # 模拟股票价格（与指数相关，但有alpha）
    stock_returns = 0.001 + 1.2 * index_returns + np.random.normal(0, 0.01, n_days)
    stock_prices = 50 * np.cumprod(1 + stock_returns)
    
    # 返回polars DataFrame
    import polars as pl
    stock_data = pl.DataFrame({
        'trade_date': dates.strftime('%Y%m%d').tolist(),
        'ts_code': ['000001.SZ'] * n_days,
        'close': stock_prices,
    })
    
    index_data = pl.DataFrame({
        'trade_date': dates.strftime('%Y%m%d').tolist(),
        'index_code': ['000001.SH'] * n_days,
        'close': index_prices,
    })
    
    return stock_data, index_data


def test_beta():
    """测试 Beta 计算."""
    print("\n=== 测试 Beta ===")
    stock_data, index_data = generate_test_data()
    
    result = beta(stock_data, index_data)
    print(f"结果形状: {result.shape}")
    print(f"列名: {result.columns}")
    
    # 验证：每只股票一行
    assert len(result) == stock_data['ts_code'].n_unique()
    assert 'beta' in result.columns
    
    beta_val = result['beta'][0]
    if beta_val is not None:
        print(f"Beta 值: {beta_val:.4f}")
        assert 1.0 < beta_val < 1.4, f"Beta 应该在 1.0-1.4 之间，实际: {beta_val}"
    else:
        print("Beta 值为 None")
    print("✅ Beta 测试通过")


def test_alpha():
    """测试 Alpha 计算."""
    print("\n=== 测试 Alpha ===")
    stock_data, index_data = generate_test_data()
    
    result = alpha(stock_data, index_data)
    print(f"结果形状: {result.shape}")
    assert 'alpha' in result.columns
    
    alpha_val = result['alpha'][0]
    if alpha_val is not None:
        print(f"Alpha 值: {alpha_val:.6f}")
        assert alpha_val > 0, f"Alpha 应该为正，实际: {alpha_val}"
    else:
        print("Alpha 值为 None")
    print("✅ Alpha 测试通过")


def test_outperform_rate():
    """测试跑赢比例计算（0-1之间）."""
    print("\n=== 测试 Outperform Rate ===")
    stock_data, index_data = generate_test_data()
    
    result = outperform_rate(stock_data, index_data)
    print(f"结果形状: {result.shape}")
    assert 'outperform_ratio' in result.columns
    
    rate = result['outperform_ratio'][0]
    if rate is not None:
        print(f"跑赢比例: {rate:.4f} ({rate*100:.1f}%)")
        assert 0 <= rate <= 1, "跑赢比例应该在 0-1 之间"
    else:
        print("跑赢比例为 None")
    print("✅ Outperform Rate 测试通过")


def test_correlation_with_index():
    """测试相关系数计算."""
    print("\n=== 测试 Correlation with Index ===")
    stock_data, index_data = generate_test_data()
    
    result = correlation_with_index(stock_data, index_data)
    print(f"结果形状: {result.shape}")
    assert 'correlation' in result.columns
    
    corr = result['correlation'][0]
    if corr is not None:
        print(f"相关系数: {corr:.4f}")
        assert -1 <= corr <= 1, "相关系数应该在 -1 到 1 之间"
    else:
        print("相关系数为 None")
    print("✅ Correlation 测试通过")


def test_tracking_error():
    """测试跟踪误差计算."""
    print("\n=== 测试 Tracking Error ===")
    stock_data, index_data = generate_test_data()
    
    result = tracking_error(stock_data, index_data, annualize=True)
    print(f"结果形状: {result.shape}")
    assert 'tracking_error' in result.columns
    
    te = result['tracking_error'][0]
    if te is not None:
        print(f"年化跟踪误差: {te:.4f}")
        assert te > 0, "跟踪误差应该为正"
    else:
        print("跟踪误差为 None")
    print("✅ Tracking Error 测试通过")


def test_information_ratio():
    """测试信息比率计算."""
    print("\n=== 测试 Information Ratio ===")
    stock_data, index_data = generate_test_data()
    
    result = information_ratio(stock_data, index_data, annualize=True)
    print(f"结果形状: {result.shape}")
    assert 'information_ratio' in result.columns
    
    ir = result['information_ratio'][0]
    if ir is not None:
        print(f"信息比率: {ir:.4f}")
    else:
        print("信息比率为 None")
    print("✅ Information Ratio 测试通过")


if __name__ == "__main__":
    print("开始测试指数相关性工具...")
    
    try:
        test_beta()
        test_alpha()
        test_outperform_rate()
        test_correlation_with_index()
        test_tracking_error()
        test_information_ratio()
        
        print("\n" + "="*60)
        print("✅ 所有测试通过！")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
