"""Screening Logic 数据模型 - 用于强制 Agent 输出结构化数据."""

from pydantic import BaseModel, Field, field_validator
from typing import Any


class ToolStep(BaseModel):
    """工具调用步骤."""
    tool: str = Field(..., description="工具名称，必须与注册的工具完全匹配")
    params: dict[str, Any] = Field(..., description="工具参数，必须包含所有必需参数")
    var: str = Field(..., description="输出变量名，将在 expression 中使用")
    
    @field_validator('tool')
    @classmethod
    def validate_tool_name(cls, v: str) -> str:
        """验证工具名称不为空."""
        if not v or not v.strip():
            raise ValueError("Tool name cannot be empty")
        return v.strip()
    
    @field_validator('var')
    @classmethod
    def validate_var_name(cls, v: str) -> str:
        """验证变量名符合 Python 标识符规范."""
        if not v or not v.strip():
            raise ValueError("Variable name cannot be empty")
        if not v[0].isalpha() and v[0] != '_':
            raise ValueError(f"Variable name must start with letter or underscore: {v}")
        return v.strip()


class ScreeningLogic(BaseModel):
    """筛选逻辑完整结构."""
    name: str = Field(..., description="策略名称，简洁明了")
    tools: list[ToolStep] = Field(default_factory=list, description="工具调用列表，可以为空（如果 expression 只使用基础字段）")
    expression: str = Field(..., description="筛选表达式，可以使用基础字段或 tools 中定义的变量")
    confidence_formula: str = Field(default="1.0", description="置信度计算公式")
    rationale: str = Field(default="", description="筛选理由说明")
    
    @field_validator('expression')
    @classmethod
    def validate_expression_not_empty(cls, v: str) -> str:
        """验证表达式不为空."""
        if not v or not v.strip():
            raise ValueError("Expression cannot be empty")
        return v.strip()
    
    def validate_variable_consistency(self) -> list[str]:
        """验证 expression 中的变量都在 tools 中定义.
        
        Returns:
            错误信息列表，为空表示校验通过
        """
        import re
        
        # 收集所有定义的变量
        defined_vars = {tool.var for tool in self.tools}
        
        # 基础数据字段（不需要在 tools 中定义）
        base_fields = {
            'close', 'open', 'high', 'low', 'vol', 'volume', 'amount',
            'turnover_rate', 'pe', 'pb', 'total_mv', 'circ_mv',
            'ts_code', 'name', 'industry', 'market', 'pct_chg', 'change',
            'pre_close'
        }
        
        # Python 关键字和内置函数
        keywords = {
            'True', 'False', 'None', 'and', 'or', 'not', 'if', 'else',
            'for', 'while', 'in', 'is', 'lambda', 'def', 'class', 'return'
        }
        builtins = {
            'abs', 'max', 'min', 'sum', 'len', 'int', 'float', 'str',
            'np', 'pd', 'numpy', 'pandas', 'pi', 'e'
        }
        
        # 提取表达式中的变量
        expression_vars = set(re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', self.expression))
        
        # 找出未定义的变量
        undefined_vars = expression_vars - keywords - builtins - base_fields - defined_vars
        
        if undefined_vars:
            return [
                f"Expression uses undefined variables: {', '.join(sorted(undefined_vars))}. "
                f"Defined vars: {', '.join(sorted(defined_vars))}"
            ]
        
        return []
