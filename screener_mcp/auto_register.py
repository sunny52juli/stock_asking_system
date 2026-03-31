"""
自动化工具注册框架 - 使用装饰器实现"定义即注册"

新增工具时只需在一个地方定义一个函数，自动完成所有注册工作。
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolMetadata:
    """工具元数据"""
    name: str
    description: str
    category: str
    parameters: dict[str, Any] = field(default_factory=dict)
    required_params: list[str] = field(default_factory=list)
    function: Callable | None = None


class ToolRegistry:
    """全局工具注册表 - 单例模式"""
    
    _instance: "ToolRegistry | None" = None
    _tools: dict[str, ToolMetadata]
    _categories: dict[str, list[str]]
    
    def __new__(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
            cls._instance._categories = {}
        return cls._instance
    
    def register(
        self,
        name: str | None = None,
        description: str = "",
        category: str = "general",
    ) -> Callable:
        """
        装饰器：注册 MCP 工具
        
        Args:
            name: 工具名称（默认使用函数名）
            description: 工具描述
            category: 工具类别（math/time_series/technical/statistical/feature_engineering/risk_metrics/screening）
        
        Returns:
            装饰器函数
        
        Example:
            @tool_registry.register(
                name="rolling_mean",
                description="移动平均",
                category="time_series"
            )
            def rolling_mean(column: str, window: int = 5) -> str:
                return _run_tool("rolling_mean", {"column": column, "window": window})
        """
        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            
            # 从函数签名中提取参数信息
            sig = inspect.signature(func)
            parameters = {}
            required_params = []
            
            for param_name, param in sig.parameters.items():
                param_type = "string"
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == float:
                    param_type = "number"
                
                param_info = {
                    "type": param_type,
                    "description": f"{param_name}参数",
                }
                
                if param.default != inspect.Parameter.empty:
                    param_info["default"] = param.default
                else:
                    required_params.append(param_name)
                
                parameters[param_name] = param_info
            
            # 构建 inputSchema
            input_schema = {
                "type": "object",
                "properties": parameters,
                "required": required_params,
            }
            
            # 创建元数据
            metadata = ToolMetadata(
                name=tool_name,
                description=description,
                category=category,
                parameters=parameters,
                required_params=required_params,
                function=func,
            )
            
            # 注册到全局注册表
            self._tools[tool_name] = metadata
            
            # 更新类别索引
            if category not in self._categories:
                self._categories[category] = []
            self._categories[category].append(tool_name)
            
            return func
        
        return decorator
    
    def get_tool(self, name: str) -> ToolMetadata | None:
        """获取工具的元数据"""
        return self._tools.get(name)
    
    def get_all_tools(self) -> dict[str, ToolMetadata]:
        """获取所有已注册的工具"""
        return self._tools.copy()
    
    def get_categories(self) -> dict[str, list[str]]:
        """获取所有类别及其工具列表"""
        return self._categories.copy()
    
    def get_tool_definitions(self) -> dict[str, Any]:
        """生成符合 MCP 规范的工具定义"""
        definitions = {}
        
        for name, metadata in self._tools.items():
            definitions[name] = {
                "description": metadata.description,
                "category": metadata.category,
                "inputSchema": {
                    "type": "object",
                    "properties": metadata.parameters,
                    "required": metadata.required_params,
                },
            }
        
        return definitions
    
    def register_to_mcp(self, mcp_instance: Any) -> None:
        """将所有工具注册到 FastMCP 实例"""
        TOOL_ANNOTATIONS = {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
        
        for name, metadata in self._tools.items():
            if metadata.function:
                mcp_instance.tool(
                    name=name,
                    description=metadata.description,
                    annotations=TOOL_ANNOTATIONS,
                )(metadata.function)


# 全局单例
tool_registry = ToolRegistry()
