"""
Screener MCP server (standalone, no dependency on this repo).

Run: uvx --from ./mcp screener-mcp-server  (from repo root)
"""

from screener_mcp.server import main, mcp

__all__ = ["mcp", "main"]
