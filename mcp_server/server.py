"""Stock Asking MCP Server - 独立的 MCP 服务器.

基于 FastMCP 框架，提供量化工具服务。
可直接运行: python -m mcp_server.server
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 确保项目根目录在路径中
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from mcp.server.fastmcp import FastMCP

from mcp_server.registered_tools import register_to_mcp


def create_server() -> FastMCP:
    """创建 MCP 服务器实例.
    
    Returns:
        FastMCP 实例
    """
    server = FastMCP(name="mcp_server")
    
    # 注册所有工具
    register_to_mcp(server)
    
    return server


def main():
    """主入口函数."""
    parser = argparse.ArgumentParser(description="Stock Asking MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind (for SSE transport)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind (for SSE transport)",
    )
    
    args = parser.parse_args()
    
    server = create_server()
    
    if args.transport == "sse":
        print(f"Starting MCP server on {args.host}:{args.port} (SSE)")
        server.run(transport="sse", host=args.host, port=args.port)
    else:
        print("Starting MCP server (stdio)")
        server.run(transport="stdio")


if __name__ == "__main__":
    main()
