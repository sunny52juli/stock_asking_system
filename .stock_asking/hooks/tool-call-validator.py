#!/usr/bin/env python3
"""Hook 脚本：统一验证策略格式与工具调用.

合并了 validate-strategy 和 validate-tool-call 的功能。
Exit codes:
  0 - 通过
  1 - 警告但继续
  2 - 阻止，stderr 返回给 Agent
"""

import json
import sys

# 常见错误工具名到正确工具名的映射
TOOL_NAME_CORRECTIONS = {
    "std_return": "volatility",
    "return_std": "volatility",
    "volatility_annual": "volatility",
    "annual_volatility": "volatility",
    "sma": "rolling_mean",
    "ema": "rolling_mean",
    "wma": "rolling_mean",
    "macd_diff": "macd",
    "rsi_value": "rsi",
    "bollinger_upper": "bollinger_bands",
    "bollinger_lower": "bollinger_bands",
    "bollinger_middle": "bollinger_bands",
}


def validate_screening(payload: dict) -> tuple[int, str]:
    """统一验证逻辑."""
    tool_input = payload.get("tool_input", {})
    
    # 1. 检查工具名称拼写 (优先检查，因为这是最常见的错误)
    tool_name = tool_input.get("name", "")
    if tool_name in TOOL_NAME_CORRECTIONS:
        correct_name = TOOL_NAME_CORRECTIONS[tool_name]
        error_msg = (
            f"❌ 错误：工具 '{tool_name}' 不存在\n"
            f"✅ 正确工具：'{correct_name}'\n"
            f"\n💡 说明：请使用 '可用工具' 列表中列出的标准名称。\n"
            f"🔧 请修正后重试"
        )
        return 2, error_msg

    # 2. 检查策略保存时的基本格式
    if "strategy_name" in tool_input:
        strategy_name = tool_input.get("strategy_name", "")
        if not strategy_name or len(strategy_name) > 100:
            return 2, "Strategy name must be non-empty and less than 100 characters"
        
        screening_logic = tool_input.get("screening_logic", {})
        if not isinstance(screening_logic, dict):
            return 2, "Screening logic must be a dictionary"

    return 0, "Validation passed"


if __name__ == "__main__":
    try:
        payload = json.load(sys.stdin)
        exit_code, message = validate_screening(payload)
        
        if exit_code != 0:
            print(message, file=sys.stderr)
        
        sys.exit(exit_code)
        
    except json.JSONDecodeError as e:
        print(f"Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Validation error: {e}", file=sys.stderr)
        sys.exit(2)
