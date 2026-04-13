#!/usr/bin/env python3
"""Hook 脚本：验证策略格式和字段合法性.

Exit codes:
  0 - 通过
  1 - 警告但继续
  2 - 阻止，stderr 返回给 Agent
"""

import json
import sys


def validate_strategy(payload: dict) -> tuple[int, str]:
    """验证策略输入.
    
    Returns:
        (exit_code, message)
    """
    tool_input = payload.get("tool_input", {})
    
    # 检查必需字段
    required_fields = ["strategy_name", "screening_logic"]
    for field in required_fields:
        if field not in tool_input:
            return 2, f"Missing required field: {field}"
    
    # 验证策略名称
    strategy_name = tool_input.get("strategy_name", "")
    if not strategy_name or len(strategy_name) > 100:
        return 2, "Strategy name must be non-empty and less than 100 characters"
    
    # 验证筛选逻辑
    screening_logic = tool_input.get("screening_logic", {})
    if not isinstance(screening_logic, dict):
        return 2, "Screening logic must be a dictionary"
    
    # 检查是否有至少一个筛选条件
    if not screening_logic:
        return 1, "Warning: Screening logic is empty"
    
    return 0, "Validation passed"


if __name__ == "__main__":
    try:
        payload = json.load(sys.stdin)
        exit_code, message = validate_strategy(payload)
        
        if exit_code != 0:
            print(message, file=sys.stderr)
        
        sys.exit(exit_code)
        
    except json.JSONDecodeError as e:
        print(f"Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Validation error: {e}", file=sys.stderr)
        sys.exit(2)
