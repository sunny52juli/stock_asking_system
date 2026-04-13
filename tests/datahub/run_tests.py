"""Run all datahub tests."""

import sys
import pytest
from pathlib import Path


def run_tests():
    """运行所有 datahub 测试。"""
    # 获取当前目录
    test_dir = Path(__file__).parent
    
    print(f"🧪 运行 datahub 模块测试")
    print(f"📁 测试目录: {test_dir}")
    print("=" * 60)
    
    # 运行当前目录下所有测试
    exit_code = pytest.main([
        str(test_dir),
        '-v',
        '--tb=short',
        '--color=yes',
    ])
    
    if exit_code == 0:
        print("\n✅ 所有 datahub 测试通过！")
    else:
        print(f"\n❌ 测试失败，退出码：{exit_code}")
    
    return exit_code == 0


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
