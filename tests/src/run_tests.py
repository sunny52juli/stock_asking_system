#!/usr/bin/env python
"""运行 Core 模块所有测试.

使用方法:
    python tests/src/run_tests.py
    
或者使用 pytest:
    pytest tests/src/ -v
"""

import sys
import pytest


def main():
    """运行所有 src 模块测试."""
    print("=" * 80)
    print("运行 Core 模块测试套件")
    print("=" * 80)
    
    # 构建测试路径
    test_path = "tests/src"
    
    # pytest 参数
    pytest_args = [
        test_path,
        "-v",                    # 详细输出
        "--tb=short",           # 简短的traceback
        "-ra",                  # 显示所有测试结果摘要
        "--strict-markers",     # 严格的标记检查
    ]
    
    # 运行测试
    exit_code = pytest.main(pytest_args)
    
    print("\n" + "=" * 80)
    if exit_code == 0:
        print("✅ 所有测试通过！")
    else:
        print(f"❌ 测试失败，退出码: {exit_code}")
    print("=" * 80)
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
