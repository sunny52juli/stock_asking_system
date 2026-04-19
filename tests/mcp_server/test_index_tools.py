"""指数工具测试 - 使用伪数据验证所有指数相关工具."""
import numpy as np
import polars as pl
import pytest
from datetime import datetime, timedelta

from mcp_server.executors.index_tools import (
    beta,
    alpha,
    outperform_rate,
    correlation_with_index,
    tracking_error,
    information_ratio,
)


def generate_mock_stock_data(n_stocks=10, n_days=100, start_date="2025-01-01"):
    """生成模拟股票数据.
    
    Args:
        n_stocks: 股票数量
        n_days: 交易日数量
        start_date: 起始日期
        
    Returns:
        DataFrame with columns: ts_code, trade_date, close, ...
    """
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    dates = [start_dt + timedelta(days=i) for i in range(n_days)]
    
    rows = []
    for i in range(n_stocks):
        # 根据股票代码前缀分配不同市场
        if i < 4:
            ts_code = f"60000{i}.SH"  # 上证
        elif i < 7:
            ts_code = f"00000{i}.SZ"  # 深证
        else:
            ts_code = f"30000{i}.SZ"  # 创业板
        
        # 生成随机价格序列（几何布朗运动）
        base_price = 10 + np.random.rand() * 90
        returns = np.random.normal(0.0005, 0.02, n_days)  # 日收益率
        prices = base_price * np.cumprod(1 + returns)
        
        for j, date in enumerate(dates):
            rows.append({
                "ts_code": ts_code,
                "trade_date": date.strftime("%Y%m%d"),
                "close": round(prices[j], 2),
                "open": round(prices[j] * (1 + np.random.normal(0, 0.005)), 2),
                "high": round(prices[j] * (1 + abs(np.random.normal(0, 0.01))), 2),
                "low": round(prices[j] * (1 - abs(np.random.normal(0, 0.01))), 2),
            })
    
    return pl.DataFrame(rows)


def generate_mock_index_data(n_days=100, start_date="2025-01-01"):
    """生成模拟指数数据（多指数）.
    
    Args:
        n_days: 交易日数量
        start_date: 起始日期
        
    Returns:
        DataFrame with columns: trade_date, index_code, close
    """
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    dates = [start_dt + timedelta(days=i) for i in range(n_days)]
    
    indices = {
        "000001.SH": {"base": 3000, "drift": 0.0003, "vol": 0.015},  # 上证指数
        "399001.SZ": {"base": 10000, "drift": 0.0004, "vol": 0.018},  # 深证成指
        "399006.SZ": {"base": 2000, "drift": 0.0005, "vol": 0.022},  # 创业板指
    }
    
    rows = []
    for idx_code, params in indices.items():
        returns = np.random.normal(params["drift"], params["vol"], n_days)
        prices = params["base"] * np.cumprod(1 + returns)
        
        for j, date in enumerate(dates):
            rows.append({
                "trade_date": date.strftime("%Y%m%d"),
                "index_code": idx_code,
                "close": round(prices[j], 2),
            })
    
    return pl.DataFrame(rows)


def test_beta():
    """测试 Beta 计算."""
    print("\n=== 测试 Beta ===")
    
    stock_data = generate_mock_stock_data(n_stocks=5, n_days=100)
    index_data = generate_mock_index_data(n_days=100)
    
    result = beta(stock_data, index_data, stock_col="close")
    
    print(f"输入股票数: {stock_data['ts_code'].n_unique()}")
    print(f"输出行数: {len(result)}")
    print(f"列名: {result.columns}")
    print(f"Beta 统计:\n{result['beta'].describe()}")
    
    assert len(result) == stock_data['ts_code'].n_unique(), "输出行数应等于股票数"
    assert 'ts_code' in result.columns, "应包含 ts_code 列"
    assert 'beta' in result.columns, "应包含 beta 列"
    
    print("✅ Beta 测试通过")
    return result


def test_alpha():
    """测试 Alpha 计算."""
    print("\n=== 测试 Alpha ===")
    
    stock_data = generate_mock_stock_data(n_stocks=5, n_days=100)
    index_data = generate_mock_index_data(n_days=100)
    
    result = alpha(stock_data, index_data, stock_col="close", risk_free_rate=0.03)
    
    print(f"输入股票数: {stock_data['ts_code'].n_unique()}")
    print(f"输出行数: {len(result)}")
    print(f"Alpha 统计:\n{result['alpha'].describe()}")
    
    assert len(result) == stock_data['ts_code'].n_unique(), "输出行数应等于股票数"
    assert 'alpha' in result.columns, "应包含 alpha 列"
    
    print("✅ Alpha 测试通过")
    return result


def test_outperform_rate():
    """测试跑赢比例计算."""
    print("\n=== 测试 Outperform Rate ===")
    
    stock_data = generate_mock_stock_data(n_stocks=5, n_days=100)
    index_data = generate_mock_index_data(n_days=100)
    
    result = outperform_rate(stock_data, index_data, stock_col="close")
    
    print(f"输出行数: {len(result)}")
    print(f"Outperform Ratio 统计:\n{result['outperform_ratio'].describe()}")
    
    assert len(result) == stock_data['ts_code'].n_unique()
    assert 'outperform_ratio' in result.columns
    # 比例应在 0-1 之间
    valid_ratios = result['outperform_ratio'].drop_nulls()
    if len(valid_ratios) > 0:
        assert valid_ratios.min() >= 0 and valid_ratios.max() <= 1
    
    print("✅ Outperform Rate 测试通过")
    return result


def test_correlation_with_index():
    """测试与指数相关系数."""
    print("\n=== 测试 Correlation with Index ===")
    
    stock_data = generate_mock_stock_data(n_stocks=5, n_days=100)
    index_data = generate_mock_index_data(n_days=100)
    
    result = correlation_with_index(stock_data, index_data, stock_col="close")
    
    print(f"输出行数: {len(result)}")
    print(f"Correlation 统计:\n{result['correlation'].describe()}")
    
    assert len(result) == stock_data['ts_code'].n_unique()
    assert 'correlation' in result.columns
    
    print("✅ Correlation 测试通过")
    return result


def test_tracking_error():
    """测试跟踪误差."""
    print("\n=== 测试 Tracking Error ===")
    
    stock_data = generate_mock_stock_data(n_stocks=5, n_days=100)
    index_data = generate_mock_index_data(n_days=100)
    
    result = tracking_error(stock_data, index_data, stock_col="close", annualize=True)
    
    print(f"输出行数: {len(result)}")
    print(f"Tracking Error 统计:\n{result['tracking_error'].describe()}")
    
    assert len(result) == stock_data['ts_code'].n_unique()
    assert 'tracking_error' in result.columns
    
    print("✅ Tracking Error 测试通过")
    return result


def test_information_ratio():
    """测试信息比率."""
    print("\n=== 测试 Information Ratio ===")
    
    stock_data = generate_mock_stock_data(n_stocks=5, n_days=100)
    index_data = generate_mock_index_data(n_days=100)
    
    result = information_ratio(stock_data, index_data, stock_col="close", annualize=True)
    
    print(f"输出行数: {len(result)}")
    print(f"Information Ratio 统计:\n{result['information_ratio'].describe()}")
    
    assert len(result) == stock_data['ts_code'].n_unique()
    assert 'information_ratio' in result.columns
    
    print("✅ Information Ratio 测试通过")
    return result


def test_empty_index_data():
    """测试空指数数据的错误处理."""
    print("\n=== 测试空指数数据 ===")
    
    stock_data = generate_mock_stock_data(n_stocks=5, n_days=100)
    empty_index = pl.DataFrame({"trade_date": [], "index_code": [], "close": []})
    
    try:
        beta(stock_data, empty_index)
        assert False, "应该抛出 ValueError"
    except ValueError as e:
        print(f"✅ 正确捕获错误: {e}")


def test_missing_index_code_column():
    """测试缺少 index_code 列的错误处理."""
    print("\n=== 测试缺少 index_code 列 ===")
    
    stock_data = generate_mock_stock_data(n_stocks=5, n_days=100)
    bad_index = pl.DataFrame({
        "trade_date": ["20250101"],
        "close": [3000],
    })
    
    try:
        beta(stock_data, bad_index)
        assert False, "应该抛出 ValueError"
    except ValueError as e:
        print(f"✅ 正确捕获错误: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("指数工具测试套件")
    print("=" * 60)
    
    # 运行所有测试
    test_beta()
    test_alpha()
    test_outperform_rate()
    test_correlation_with_index()
    test_tracking_error()
    test_information_ratio()
    
    # 错误处理测试
    test_empty_index_data()
    test_missing_index_code_column()
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)
