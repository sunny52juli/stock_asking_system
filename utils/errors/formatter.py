"""错误消息格式化 - 统一的错误提示构建器."""

from __future__ import annotations


def format_error_message(
    error: str,
    suggestions: list[str] | None = None,
    tips: list[str] | None = None,
) -> str:
    """格式化错误消息.
    
    Args:
        error: 错误描述
        suggestions: 建议列表（可选）
        tips: 提示列表（可选）
        
    Returns:
        格式化后的错误消息字符串
    """
    msg = f"❌ 错误：{error}\n"
    
    if suggestions:
        msg += "\n💡 建议：\n" + "\n".join(f"   • {s}" for s in suggestions)
    
    if tips:
        msg += "\n🔧 提示：\n" + "\n".join(f"   • {t}" for t in tips)
    
    return msg


def format_validation_error(
    field: str,
    issue: str,
    fix_suggestion: str,
) -> str:
    """格式化验证错误消息.
    
    Args:
        field: 字段名
        issue: 问题描述
        fix_suggestion: 修复建议
        
    Returns:
        格式化后的验证错误消息
    """
    return format_error_message(
        error=f"{field} 验证失败",
        suggestions=[issue],
        tips=[fix_suggestion],
    )


def format_tool_error(
    tool_name: str,
    error_msg: str,
    correct_tool: str | None = None,
) -> str:
    """格式化工具执行错误消息.
    
    Args:
        tool_name: 工具名称
        error_msg: 错误信息
        correct_tool: 正确的工具名称（如果是因为拼写错误）
        
    Returns:
        格式化后的工具错误消息
    """
    if correct_tool:
        return format_error_message(
            error=f"工具 '{tool_name}' 不存在",
            suggestions=[f"正确工具：'{correct_tool}'"],
            tips=["请使用 '可用工具' 列表中列出的标准名称"],
        )
    else:
        return format_error_message(
            error=f"工具 '{tool_name}' 执行失败",
            tips=[error_msg],
        )
