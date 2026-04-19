"""自动注册装饰器 - 简化版.

使用方式:
    @tool_registry.register(description="工具描述", category="math")
    def my_tool(column: str, window: int = 5) -> str:
        return execute_my_tool(column, window)
"""

from __future__ import annotations

import inspect
from typing import Any, Callable
from pydantic import BaseModel, create_model, Field


class ToolRegistry:
    """工具注册器."""
    
    def __init__(self):
        self._tools: dict[str, dict[str, Any]] = {}
        self._functions: dict[str, Callable] = {}
        self._validators: dict[str, type[BaseModel]] = {}  # Pydantic 验证器
    
    def register(
        self,
        description: str,
        category: str,
        name: str | None = None
    ) -> Callable:
        """注册工具的装饰器."""
        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            
            # 从函数签名提取参数信息
            sig = inspect.signature(func)
            properties = {}
            required = []
            
            for param_name, param in sig.parameters.items():
                if param_name in ('self', 'data'):
                    continue
                
                # 构建更详细的参数描述
                param_desc = f"{param_name}"
                if param.annotation != inspect.Parameter.empty:
                    type_name = param.annotation.__name__ if hasattr(param.annotation, '__name__') else str(param.annotation)
                    param_desc += f" ({type_name})"
                if param.default != inspect.Parameter.empty:
                    param_desc += f", default={param.default}"
                
                param_info = {"description": param_desc}
                
                # 推断类型
                if param.annotation != inspect.Parameter.empty:
                    type_map = {
                        str: "string",
                        int: "integer",
                        float: "number",
                        bool: "boolean",
                    }
                    param_type = type_map.get(param.annotation, "string")
                    param_info["type"] = param_type
                
                # 检查是否有默认值
                if param.default != inspect.Parameter.empty:
                    param_info["default"] = param.default
                else:
                    required.append(param_name)
                
                properties[param_name] = param_info
            
            # 构建工具定义
            self._tools[tool_name] = {
                "category": category,
                "description": description,
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            }
            
            self._functions[tool_name] = func
            
            # 创建 Pydantic 模型用于参数验证
            field_definitions = {}
            for param_name, param in sig.parameters.items():
                # 跳过系统自动注入的参数（data, stock_data, index_data）
                if param_name in ('self', 'data', 'stock_data', 'index_data'):
                    continue
                
                # 确定字段类型：将复杂类型（如 pl.DataFrame）替换为 Any
                field_type = param.annotation
                if field_type != inspect.Parameter.empty:
                    # 检查是否是 DataFrame/Series 等复杂类型
                    type_str = str(field_type)
                    if 'DataFrame' in type_str or 'Series' in type_str or 'pl.' in type_str:
                        field_type = Any
                else:
                    field_type = Any
                
                # 确定默认值
                if param.default != inspect.Parameter.empty:
                    default_value = param.default
                    field_definitions[param_name] = (field_type, Field(default=default_value))
                else:
                    field_definitions[param_name] = (field_type, Field(...))
            
            # 动态创建 Pydantic 模型
            validator_class = create_model(
                f"{tool_name.capitalize()}Params",
                **field_definitions
            )
            self._validators[tool_name] = validator_class
            
            return func
        
        return decorator
    
    def get_tool_definitions(self) -> dict[str, dict[str, Any]]:
        """获取所有工具定义."""
        return self._tools.copy()
    
    def get_all_functions(self) -> dict[str, Callable]:
        """获取所有工具函数."""
        return self._functions.copy()
    
    def validate_params(self, tool_name: str, params: dict) -> dict:
        """使用 Pydantic 验证工具参数.
        
        Args:
            tool_name: 工具名称
            params: 原始参数字典
            
        Returns:
            验证后的参数字典
            
        Raises:
            ValueError: 参数验证失败
        """
        if tool_name not in self._validators:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        validator = self._validators[tool_name]
        try:
            validated = validator(**params)
            return validated.model_dump()
        except Exception as e:
            raise ValueError(f"参数验证失败 [{tool_name}]: {e}") from e
    
    def register_to_mcp(self, mcp_instance: Any) -> None:
        """将所有工具注册到 FastMCP 实例."""
        
        for tool_name, definition in self._tools.items():
            description = definition.get("description", "")
            
            # 创建包装函数
            def create_wrapper(name: str, desc: str):
                async def wrapper(**kwargs):
                    try:
                        # 延迟导入避免循环依赖
                        from mcp_server.executors import execute_tool
                        
                        # execute_tool 需要 data 参数，这里暂时返回提示
                        if 'data' not in kwargs:
                            return f"Tool '{name}' requires data context. Use via ExpressionEvaluator."
                        result = execute_tool(name, **kwargs)
                        return str(result)
                    except Exception as e:
                        return f"Error: {e}"
                
                wrapper.__name__ = name
                wrapper.__doc__ = desc
                return wrapper
            
            wrapper = create_wrapper(tool_name, description)
            
            try:
                mcp_instance.tool(
                    name=tool_name,
                    description=description,
                )(wrapper)
            except Exception as e:
                print(f"Warning: Failed to register tool '{tool_name}': {e}")


# 全局注册器实例
tool_registry = ToolRegistry()
