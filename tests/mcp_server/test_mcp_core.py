"""测试 MCP Server 核心模块 - server, auto_register, registered_tools."""

import pytest
from unittest.mock import Mock, patch

from mcp_server.server import create_server, main
from mcp_server.auto_register import ToolRegistry, tool_registry
from mcp_server.registered_tools import get_all_tools, register_to_mcp


class TestServer:
    """测试 MCP Server."""
    
    def test_create_server(self):
        """测试创建服务器实例."""
        server = create_server()
        
        assert server is not None
        assert hasattr(server, 'run')
        # FastMCP 不支持 description 参数，只验证 name
    
    @patch('argparse.ArgumentParser.parse_args')
    @patch('mcp_server.server.create_server')
    def test_main_stdio(self, mock_create_server, mock_parse_args):
        """测试主函数 - stdio 模式."""
        # Mock
        mock_server = Mock()
        mock_create_server.return_value = mock_server
        mock_parse_args.return_value = Mock(transport="stdio", host=None, port=None)
        
        # 调用 main
        main()
        
        # 验证 server 被创建和运行
        mock_create_server.assert_called_once()
        mock_server.run.assert_called_once_with(transport="stdio")
    
    @patch('argparse.ArgumentParser.parse_args')
    @patch('mcp_server.server.create_server')
    def test_main_sse(self, mock_create_server, mock_parse_args):
        """测试主函数 - SSE 模式."""
        mock_server = Mock()
        mock_create_server.return_value = mock_server
        mock_parse_args.return_value = Mock(transport="sse", host="127.0.0.1", port=8000)
        
        main()
        
        mock_create_server.assert_called_once()
        mock_server.run.assert_called_once_with(transport="sse", host="127.0.0.1", port=8000)


class TestToolRegistry:
    """测试工具注册器."""
    
    def test_register_simple_function(self):
        """测试注册简单函数."""
        registry = ToolRegistry()
        
        @registry.register(description="测试工具", category="math")
        def test_tool(param1: str, param2: int = 5):
            return param1
        
        # 检查工具已注册
        definitions = registry.get_tool_definitions()
        assert 'test_tool' in definitions
        
        # 检查定义内容
        tool_def = definitions['test_tool']
        assert tool_def['category'] == 'math'
        assert tool_def['description'] == '测试工具'
        
        # 检查参数
        schema = tool_def['inputSchema']
        assert 'param1' in schema['properties']
        assert 'param2' in schema['properties']
        assert 'param1' in schema['required']
        assert 'param2' not in schema['required']  # 有默认值
    
    def test_register_with_custom_name(self):
        """测试使用自定义名称注册."""
        registry = ToolRegistry()
        
        @registry.register(description="测试", category="math", name="custom_name")
        def my_function():
            pass
        
        definitions = registry.get_tool_definitions()
        assert 'custom_name' in definitions
        assert 'my_function' not in definitions
    
    def test_register_type_inference(self):
        """测试类型推断."""
        registry = ToolRegistry()
        
        @registry.register(description="测试", category="math")
        def typed_tool(
            str_param: str,
            int_param: int,
            float_param: float,
            bool_param: bool
        ):
            pass
        
        definitions = registry.get_tool_definitions()
        props = definitions['typed_tool']['inputSchema']['properties']
        
        assert props['str_param']['type'] == 'string'
        assert props['int_param']['type'] == 'integer'
        assert props['float_param']['type'] == 'number'
        assert props['bool_param']['type'] == 'boolean'
    
    def test_get_all_functions(self):
        """测试获取所有函数."""
        registry = ToolRegistry()
        
        @registry.register(description="工具1", category="math")
        def tool1():
            pass
        
        @registry.register(description="工具2", category="math")
        def tool2():
            pass
        
        functions = registry.get_all_functions()
        assert len(functions) == 2
        assert 'tool1' in functions
        assert 'tool2' in functions
    
    def test_register_to_mcp(self):
        """测试注册到 MCP 实例."""
        registry = ToolRegistry()
        
        @registry.register(description="测试工具", category="math")
        def test_tool(column: str):
            return column
        
        # Mock MCP 实例
        mock_mcp = Mock()
        mock_mcp.tool.return_value = lambda f: f
        
        # 注册
        registry.register_to_mcp(mock_mcp)
        
        # 验证 tool 方法被调用
        assert mock_mcp.tool.called
    
    def test_global_registry(self):
        """测试全局注册器实例."""
        assert isinstance(tool_registry, ToolRegistry)


class TestRegisteredTools:
    """测试注册工具模块."""
    
    def test_get_all_tools_empty(self):
        """测试获取所有工具（初始为空）."""
        # 注意：由于 auto_register.py 中没有实际注册工具
        # 这里应该返回空字典或仅包含测试中注册的工具
        tools = get_all_tools()
        assert isinstance(tools, dict)
    
    def test_register_to_mcp(self):
        """测试注册到 MCP."""
        mock_mcp = Mock()
        mock_mcp.tool.return_value = lambda f: f
        
        # 不应该抛出异常
        register_to_mcp(mock_mcp)


class TestIntegration:
    """集成测试."""
    
    def test_full_registration_flow(self):
        """测试完整注册流程."""
        # 1. 创建注册器
        registry = ToolRegistry()
        
        # 2. 注册工具
        @registry.register(description="加法", category="math")
        def add(a: int, b: int) -> int:
            return a + b
        
        # 3. 获取定义
        definitions = registry.get_tool_definitions()
        assert 'add' in definitions
        
        # 4. 注册到 Mock MCP
        mock_mcp = Mock()
        mock_mcp.tool.return_value = lambda f: f
        registry.register_to_mcp(mock_mcp)
        
        # 5. 验证
        assert mock_mcp.tool.called
