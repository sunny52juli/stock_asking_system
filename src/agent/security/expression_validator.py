"""表达式安全验证器 - 集成到Bridge工具中."""

from __future__ import annotations

import json
from typing import Any

from src.agent.security import ASTValidationError, validate_expression


def safe_validate_expression(expression: str) -> dict[str, Any]:
    """安全地验证表达式（用于Bridge工具调用前检查）.
    
    Args:
        expression: 待验证的表达式字符串
        
    Returns:
        验证结果字典 {"valid": bool, "error": str | None}
    """
    try:
        validate_expression(expression)
        return {"valid": True, "error": None}
    except ASTValidationError as e:
        return {"valid": False, "error": f"表达式安全检查失败: {e}"}
    except SyntaxError as e:
        return {"valid": False, "error": f"表达式语法错误: {e}"}


def safe_execute_with_validation(
    tool_name: str, 
    arguments: dict[str, Any],
    executor_func
) -> str:
    """在执行工具前先验证表达式参数.
    
    Args:
        tool_name: 工具名称
        arguments: 工具参数
        executor_func: 实际执行函数
        
    Returns:
        JSON格式的执行结果
    """
    # 需要验证的参数名（包含表达式或列名的参数）
    expression_params = {"column", "values", "x", "y", "high", "low", "close", "pre_close", "vol"}
    
    # 验证所有可能的表达式参数
    for param_name, param_value in arguments.items():
        if param_name in expression_params and isinstance(param_value, str):
            validation_result = safe_validate_expression(param_value)
            if not validation_result["valid"]:
                return json.dumps({
                    "error": validation_result["error"],
                    "tool": tool_name,
                    "param": param_name
                }, ensure_ascii=False)
    
    # 验证通过，执行工具
    try:
        result = executor_func(tool_name, arguments)
        return json.dumps(result, ensure_ascii=False, indent=2) if isinstance(result, dict) else result
    except Exception as e:
        return json.dumps({"error": f"执行失败: {e}"}, ensure_ascii=False)
