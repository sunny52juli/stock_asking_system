"""Screening Logic 数据模型 - 用于强制 Agent 输出结构化数据."""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Any


import re
class ToolStep(BaseModel):
    """工具调用步骤."""
    tool: str = Field(..., description="工具名称，必须与注册的工具完全匹配")
    params: dict[str, Any] = Field(..., description="工具参数，必须包含所有必需参数")
    var: str = Field(..., description="输出变量名，将在 expression 中使用")
    
    # 类变量：观察期约束（从配置加载）
    _observation_days: int = 60  # 默认值，可通过 set_observation_days 修改
    
    @classmethod
    def set_observation_days(cls, days: int):
        """设置全局观察期约束."""
        cls._observation_days = days
    
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
    
    @model_validator(mode='after')
    def validate_window_params(self) -> 'ToolStep':
        """验证窗口参数不超过 observation_days.
        
        检查规则：
        1. 如果 params 中包含 window 参数，其值不能超过 observation_days
        2. 适用于所有时间序列工具（rolling_mean, rolling_std, rsi, macd等）
        """
        if 'window' in self.params:
            window_value = self.params['window']
            if isinstance(window_value, (int, float)):
                max_window = self._observation_days
                if window_value > max_window:
                    raise ValueError(
                        f"窗口参数 window={window_value} 超过最大允许值 {max_window} (observation_days)。\n"
                        f"工具 '{self.tool}' 的窗口大小不能超过系统配置的观察期长度。\n"
                        f"建议：使用 window <= {max_window}，或调整配置文件中的 observation_days 参数。"
                    )
                elif window_value <= 0:
                    raise ValueError(
                        f"窗口参数 window={window_value} 必须为正整数。"
                    )
        
        return self


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
    
    @field_validator('expression')
    @classmethod
    def validate_no_hardcoded_thresholds(cls, v: str) -> str:
        """验证表达式中没有硬编码的绝对阈值.
        
        检测模式：
        - < 0.0X 或 > 0.0X （如 volatility < 0.03）
        - < 0.X 或 > 0.X （如 return > 0.05）
        - 其他常见的硬编码数值（如 volatility < 5, pe < 30）
        
        允许的模式：
        - 与变量比较：volatility_20d < volatility_ma60
        - 与0比较：return_20d > 0
        - 技术指标合理范围：rsi > 30, rsi < 70
        - 指数相关指标：beta < 1.2, outperform_rate > 0.5（有明确金融含义）
        """
        
        # 检测硬编码的小数阈值（排除合理的 RSI、百分比等）
        # 匹配模式：变量 < 0.0X 或 变量 > 0.0X
        hardcoded_patterns = [
            r'[a-zA-Z_]\w*\s*[<>]\s*0\.0[1-9]',  # < 0.01 to 0.09
            r'0\.0[1-9]\s*[<>]\s*[a-zA-Z_]\w*',  # 0.01 to 0.09 > variable
            r'[a-zA-Z_]\w*\s*[<>]\s*[1-9]+\.?[0-9]*',  # 整数或小数阈值（如 < 5, < 30）
        ]
        
        # 需要排除的合理模式
        allowed_patterns = [
            r'rsi\w*\s*[<>]\s*[0-9]+',  # RSI 指标可以使用固定值
            r'\b0\b',  # 与0比较是允许的
            # 指数相关指标允许使用具体数值（有明确的金融含义和行业标准）
            r'beta\w*\s*[<>]\s*[0-9]+\.?[0-9]*',  # beta < 1.2 （波动性相对于指数）
            r'outperform_rate\w*\s*[<>]\s*[0-9]+\.?[0-9]*',  # outperform_rate > 0.5 （跑赢比例，0-1之间）
            r'alpha\w*\s*[<>]\s*-?[0-9]+\.?[0-9]*',  # alpha > 0.05 （超额收益）
            r'tracking_error\w*\s*[<>]\s*[0-9]+\.?[0-9]*',  # tracking_error < 0.1 （跟踪误差）
            r'information_ratio\w*\s*[<>]\s*-?[0-9]+\.?[0-9]*',  # information_ratio > 1 （信息比率）
            r'correlation_with_index\w*\s*[<>]\s*-?[0-9]+\.?[0-9]*',  # correlation > 0.8 （相关性）
        ]
        
        for pattern in hardcoded_patterns:
            matches = re.findall(pattern, v)
            if matches:
                # 检查是否是允许的模式
                is_allowed = False
                for allowed in allowed_patterns:
                    if re.search(allowed, ' '.join(matches)):
                        is_allowed = True
                        break
                
                if not is_allowed:
                    raise ValueError(
                        f"检测到硬编码的绝对阈值：{', '.join(matches)}\n"
                        f"请使用相对指标，例如：\n"
                        f"  - volatility_20d < volatility_ma60 （与历史均值比较）\n"
                        f"  - volatility_rank < 0.3 （使用分位数）\n"
                        f"  - excess_return > 0 （相对于指数）\n"
                        f"避免使用固定值如 0.03、0.05、5、30 等，因为它们无法适应不同市场环境。\n"
                        f"注：指数相关指标（beta、outperform_rate、alpha等）可以使用具体数值，因为它们有明确的金融含义。"
                    )
        
        return v
    
    def validate_variable_consistency(self) -> list[str]:
        """验证 expression 中的变量都在 tools 中定义.
        
        Returns:
            错误信息列表，为空表示校验通过
        """
        
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
            # 检测是否使用了工具函数名
            common_tool_names = {
                'rolling_mean', 'rolling_std', 'rolling_max', 'rolling_min',
                'volatility', 'rsi', 'macd', 'kdj', 'atr', 'obv',
                'rank_normalize', 'zscore_normalize', 'pct_change',
                'beta', 'alpha', 'outperform_rate', 'correlation_with_index'
            }
            tool_names_in_expr = undefined_vars & common_tool_names
            
            error_msg = (
                f"Expression uses undefined variables: {', '.join(sorted(undefined_vars))}. "
                f"Defined vars: {', '.join(sorted(defined_vars))}"
            )
            
            if tool_names_in_expr:
                error_msg += (
                    f"\n\n⚠️ 错误：表达式中直接使用了工具函数名 {', '.join(sorted(tool_names_in_expr))}！"
                    f"\n正确做法："
                    f"\n1. 在 tools 列表中定义变量，例如：{{'var': 'ma20', 'tool': 'rolling_mean', ...}}"
                    f"\n2. 在表达式中使用变量名，例如：'expression': 'ma20 > close'"
                    f"\n3. 不要在表达式中直接调用工具函数，如 rolling_mean(close, 20)"
                )
            
            return [error_msg]
        
        return []
