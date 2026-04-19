"""筛选逻辑校验器 - 验证 screening_logic 结构."""

from __future__ import annotations


from src.agent.models.screening_logic import ScreeningLogic
def validate_screening_logic(screening_logic: dict) -> str | None:
    """校验 screening_logic 结构的完整性（使用 Pydantic 模型）.
    
    Args:
        screening_logic: 待校验的筛选逻辑
        
    Returns:
        错误信息，如果校验通过则返回 None
    """
    try:
        
        # 1. 尝试解析为 Pydantic 模型（自动校验字段类型和必需性）
        logic_model = ScreeningLogic(**screening_logic)
        
        # 2. 校验变量一致性
        validation_errors = logic_model.validate_variable_consistency()
        if validation_errors:
            return "; ".join(validation_errors)
        
        return None
        
    except Exception as e:
        # Pydantic 会提供详细的校验错误信息
        return f"Validation error: {str(e)}"
