"""自动注册装饰器 - 简化版.

使用方式:
    @tool_registry.register(description="工具描述", category="math")
    def my_tool(column: str, window: int = 5) -> str:
        return execute_my_tool(column, window)
"""

from __future__ import annotations

import inspect
from typing import Any, Callable


class ToolRegistry:
    """工具注册器."""
    
    def __init__(self):
        self._tools: dict[str, dict[str, Any]] = {}
        self._functions: dict[str, Callable] = {}
    
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
                
                param_info = {"description": f"Parameter {param_name}"}
                
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
            return func
        
        return decorator
    
    def get_tool_definitions(self) -> dict[str, dict[str, Any]]:
        """获取所有工具定义."""
        return self._tools.copy()
    
    def get_all_functions(self) -> dict[str, Callable]:
        """获取所有工具函数."""
        return self._functions.copy()
    
    def register_to_mcp(self, mcp_instance: Any) -> None:
        """将所有工具注册到 FastMCP 实例."""
        from mcp_server.executors import execute_tool as executor_execute
        
        for tool_name, definition in self._tools.items():
            description = definition.get("description", "")
            
            # 创建包装函数
            def create_wrapper(name: str, desc: str):
                async def wrapper(**kwargs):
                    try:
                        # execute_tool 需要 data 参数，这里暂时返回提示
                        if 'data' not in kwargs:
                            return f"Tool '{name}' requires data context. Use via ExpressionEvaluator."
                        result = executor_execute(name, **kwargs)
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
