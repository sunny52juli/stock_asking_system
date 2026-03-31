"""
Screener MCP 服务器入口：FastMCP + stdio.

工具通过装饰器自动注册，无需手动维护列表。
"""

from mcp.server.fastmcp import FastMCP

from screener_mcp.registered_tools import register_to_mcp

mcp = FastMCP("screener-mcp")
register_to_mcp(mcp)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
