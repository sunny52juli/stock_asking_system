"""工具参数自动验证器 - 基于装饰器和函数签名.

使用 Pydantic 进行类型检查，但通过装饰器自动生成验证规则，
避免手动维护大量验证类。
"""

from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable

from pydantic import BaseModel, Field, create_model


def _python_type_to_pydantic_field(param: inspect.Parameter) -> tuple[type, Field]:
    """将 Python 类型注解转换为 Pydantic Field.
    
    Args:
        param: 函数参数
        
    Returns:
        (Pydantic 类型, Field 配置)
    """
    annotation = param.annotation
    default = param.default
    
    # 处理默认值
    if default is inspect.Parameter.empty:
        # 必需参数
        field = Field(...)
    else:
        # 可选参数，带默认值
        field = Field(default)
    
    # 处理类型注解
    if annotation is inspect.Parameter.empty:
        # 无类型注解，使用 Any
        return (Any, field)
    
    # 特殊处理：pandas/numpy 类型替换为 Any（Pydantic 无法验证这些复杂类型）
    type_name = str(annotation)
    if 'pd.DataFrame' in type_name or 'pd.Series' in type_name or 'numpy' in type_name:
        return (Any, field)
    
    # 处理 Optional 类型
    origin = getattr(annotation, '__origin__', None)
    if origin is not None:
        # Union 类型（包括 Optional）
        args = getattr(annotation, '__args__', ())
        if type(None) in args:
            # Optional[T] -> T | None
            non_none_types = [t for t in args if t is not type(None)]
            if len(non_none_types) == 1:
                # 检查是否为 pandas 类型
                inner_type = non_none_types[0]
                inner_type_name = str(inner_type)
                if 'pd.DataFrame' in inner_type_name or 'pd.Series' in inner_type_name or 'numpy' in inner_type_name:
                    return (Any, field)
                return (inner_type, field)
    
    return (annotation, field)


def auto_validate(func: Callable) -> Callable:
    """自动验证装饰器 - 从函数签名生成 Pydantic 验证.
    
    用法:
        @auto_validate
        def rolling_mean(data: pd.DataFrame, column: str, window: int = 5) -> pd.Series:
            ...
    
    特性:
        1. 自动从函数签名提取参数类型和默认值
        2. 动态创建 Pydantic 模型进行验证
        3. 提供清晰的错误信息
        4. 不影响原有函数逻辑
    """
    sig = inspect.signature(func)
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 绑定参数到签名
        try:
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
        except TypeError as e:
            raise ValueError(f"参数绑定失败: {e}") from e
        
        # 获取参数字典（排除 self/cls）
        params_dict = {
            k: v for k, v in bound.arguments.items()
            if k not in ('self', 'cls')
        }
        
        # 动态创建 Pydantic 模型
        fields = {}
        for param_name, param in sig.parameters.items():
            if param_name in ('self', 'cls'):
                continue
            
            pydantic_type, field = _python_type_to_pydantic_field(param)
            fields[param_name] = (pydantic_type, field)
        
        # 创建临时验证模型
        validator_name = f"{func.__name__}_Params"
        try:
            ValidatorModel = create_model(validator_name, **fields)
            validated = ValidatorModel(**params_dict)
            validated_dict = validated.model_dump()
        except Exception as e:
            # 格式化验证错误
            if hasattr(e, 'errors'):
                error_details = []
                for error in e.errors():
                    loc = " -> ".join(str(x) for x in error.get('loc', []))
                    msg = error.get('msg', '未知错误')
                    error_details.append(f"字段 '{loc}': {msg}")
                
                raise ValueError(
                    f"工具 '{func.__name__}' 参数验证失败:\n" + "\n".join(error_details)
                ) from e
            else:
                raise ValueError(f"工具 '{func.__name__}' 参数验证失败: {e}") from e
        
        # 调用原函数（使用验证后的参数）
        return func(**validated_dict)
    
    # 保留原始签名信息（用于 introspection）
    wrapper.__signature__ = sig
    wrapper.__wrapped__ = func
    
    return wrapper


def validate_tool_params_auto(tool_func: Callable, params: dict[str, Any]) -> dict[str, Any]:
    """手动验证工具参数（不执行函数）.
    
    用于在 stock_screener.py 中提前验证，避免在执行时才报错。
    
    Args:
        tool_func: 工具函数
        params: 待验证的参数字典（不包含 data）
        
    Returns:
        验证后的参数字典
        
    Raises:
        ValueError: 参数验证失败
    """
    sig = inspect.signature(tool_func)
    
    # 过滤掉 data 参数（由 execute_tool 注入）
    filtered_params = {k: v for k, v in params.items() if k != 'data'}
    
    # 构建参数字典（应用默认值）
    try:
        bound = sig.bind_partial(**filtered_params)
        bound.apply_defaults()
        params_with_defaults = bound.arguments
    except TypeError as e:
        raise ValueError(f"参数绑定失败: {e}") from e
    
    # 动态创建验证模型（排除 data 参数）
    fields = {}
    for param_name, param in sig.parameters.items():
        if param_name in ('self', 'cls', 'data'):
            continue
        
        pydantic_type, field = _python_type_to_pydantic_field(param)
        fields[param_name] = (pydantic_type, field)
    
    validator_name = f"{tool_func.__name__}_Params"
    try:
        ValidatorModel = create_model(validator_name, **fields)
        validated = ValidatorModel(**params_with_defaults)
        return validated.model_dump(exclude_none=False)
    except Exception as e:
        if hasattr(e, 'errors'):
            error_details = []
            for error in e.errors():
                loc = " -> ".join(str(x) for x in error.get('loc', []))
                msg = error.get('msg', '未知错误')
                error_details.append(f"字段 '{loc}': {msg}")
            
            raise ValueError(
                f"工具 '{tool_func.__name__}' 参数验证失败:\n" + "\n".join(error_details)
            ) from e
        else:
            raise ValueError(f"工具 '{tool_func.__name__}' 参数验证失败: {e}") from e
