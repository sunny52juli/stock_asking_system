"""运行所有 mcp_server 测试."""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    import pytest
    
    # 运行所有 mcp_server 测试
    exit_code = pytest.main([
        "tests/mcp_server/",
        "-v",
        "--tb=short",
        "-m", "not slow"  # 跳过慢速测试
    ])
    
    sys.exit(exit_code)
