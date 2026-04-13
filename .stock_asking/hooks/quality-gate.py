#!/usr/bin/env python3
"""Hook 脚本：结果质量门禁.

Exit codes:
  0 - 通过
  1 - 警告但继续
  2 - 阻止，stderr 返回给 Agent
"""

import json
import sys


def check_quality(payload: dict) -> tuple[int, str]:
    """检查结果质量.
    
    Returns:
        (exit_code, message)
    """
    # 基本检查：确保有结果数据
    result = payload.get("result", {})
    if not result:
        return 2, "Error: Empty result"
    
    # 通过（详细质量评估由 quality_evaluator 负责）
    return 0, "Quality check passed"


if __name__ == "__main__":
    try:
        payload = json.load(sys.stdin)
        exit_code, message = check_quality(payload)
        
        if exit_code != 0:
            print(message, file=sys.stderr)
        
        sys.exit(exit_code)
        
    except json.JSONDecodeError as e:
        print(f"Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Quality check error: {e}", file=sys.stderr)
        sys.exit(2)
