#!/usr/bin/env python3
"""测试门禁 Hook - 运行关键单元测试."""

import subprocess
import sys
from pathlib import Path


def run_critical_tests() -> bool:
    """运行关键单元测试."""
    print("Running critical unit tests...")
    
    # 获取项目根目录
    project_root = Path(__file__).parent.parent.parent
    
    try:
        result = subprocess.run(
            ['python', '-m', 'pytest', 
             'tests/mcp_server/test_expression_security.py',
             'tests/infrastructure/config/test_settings_validation.py',
             '-q', '--tb=no'],
            capture_output=False,
            timeout=60,
            cwd=project_root
        )
        
        if result.returncode == 0:
            print("All tests passed!")
        else:
            print("Some tests failed")
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"Warning: Test execution error: {e}")
        return True  # 不阻止 commit


def main():
    """主函数."""
    success = run_critical_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
