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
    # 1. 尝试从 result.candidates 获取（标准结构）
    result = payload.get("result", {})
    candidates = result.get("candidates", []) if isinstance(result, dict) else []
    
    # 2. 如果 result 为空，尝试从 payload 顶层获取（兼容模式）
    if not candidates and isinstance(payload, dict):
        candidates = payload.get("candidates", [])
        
    count = len(candidates)
    
    # 理想区间：5-30 只。只要在此范围内，强制通过，禁止 Agent 为了“优化”而继续迭代
    if 5 <= count <= 30:
        return 0, f"Quality check passed: {count} candidates found. Proceeding to final output."
    
    # 结果过多：约束太松（仅在这种情况下触发迭代）
    elif count > 30:
        msg = f"[ITERATION TRIGGER] Too many candidates ({count}). Constraints are too loose. Agent must tighten the logic."
        return 1, msg
    
    # 结果过少：约束太紧（仅在这种情况下触发迭代）
    else:
        msg = f"[ITERATION TRIGGER] Too few candidates ({count}). Constraints are too tight. Agent must relax the logic."
        return 1, msg


if __name__ == "__main__":
    try:
        payload = json.load(sys.stdin)
        exit_code, message = check_quality(payload)
        
        # 无论是否通过，都将信息输出到 stderr，确保 Agent 能看到
        if message:
            print(message, file=sys.stderr)
        
        sys.exit(exit_code)
        
    except json.JSONDecodeError as e:
        print(f"Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Quality check error: {e}", file=sys.stderr)
        sys.exit(2)
