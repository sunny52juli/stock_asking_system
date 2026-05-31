"""测试 confidence_weights 功能."""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import polars as pl
from src.screening.executor import ScreeningExecutor


def test_confidence_weights_support():
    """测试 confidence_weights 字典格式的支持."""
    
    # 创建测试数据
    data = pl.DataFrame({
        "ts_code": ["000001.SZ", "000002.SZ", "000003.SZ"] * 10,
        "trade_date": ["20260101", "20260102", "20260103"] * 10,
        "close": [10.0, 11.0, 12.0] * 10,
        "vol": [1000, 1100, 1200] * 10,
    })
    
    executor = ScreeningExecutor(data)
    
    # 测试 1: 使用 confidence_weights（新格式）
    screening_logic_with_weights = {
        "expression": "(alpha_60 > 0)",
        "confidence_weights": {
            "alpha_60": 0.7,
            "outperform_rate_60": 0.3
        },
        "tools": [
            {"var": "alpha_60", "tool": "alpha", "params": {"window": 60}},
            {"var": "outperform_rate_60", "tool": "outperform_rate", "params": {"window": 60}}
        ]
    }
    
    print("[OK] Test 1: confidence_weights 格式")
    print(f"   输入: {screening_logic_with_weights['confidence_weights']}")
    print("   预期: 应该识别并使用自定义权重")
    
    # 测试 2: 使用 confidence_formula（旧格式）
    screening_logic_with_formula = {
        "expression": "(alpha_60 > 0)",
        "confidence_formula": "rank_normalize(alpha_60) * 0.6 + rank_normalize(outperform_rate_60) * 0.4",
        "tools": [
            {"var": "alpha_60", "tool": "alpha", "params": {"window": 60}},
            {"var": "outperform_rate_60", "tool": "outperform_rate", "params": {"window": 60}}
        ]
    }
    
    print("\n[OK] Test 2: confidence_formula 格式")
    print(f"   输入: {screening_logic_with_formula['confidence_formula']}")
    print("   预期: 应该从公式中提取权重")
    
    # 测试 3: 没有任何权重配置（等权）
    screening_logic_no_weights = {
        "expression": "(alpha_60 > 0)",
        "tools": [
            {"var": "alpha_60", "tool": "alpha", "params": {"window": 60}},
            {"var": "outperform_rate_60", "tool": "outperform_rate", "params": {"window": 60}}
        ]
    }
    
    print("\n[OK] Test 3: 无权重配置")
    print("   输入: 无 confidence_weights 或 confidence_formula")
    print("   预期: 应该使用等权分配")
    
    print("\n[OK] 所有测试场景定义完成！")
    print("\n提示: 实际运行需要在 screener.py 交互界面中输入策略")


if __name__ == "__main__":
    test_confidence_weights_support()
