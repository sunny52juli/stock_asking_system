"""Tool provider for distributing tools across agents.

Each agent receives only the tools relevant to its role:
- IntentAgent: No tools (pure NLU)
- PlannerAgent: Tool metadata + get_available_industries
- ExecutorAgent: ALL MCP tools + run_screening
- EvaluatorAgent: save_screening_script
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ScreenerToolProvider:
    """Distributes tools across agents based on their roles."""

    _AGENT_TOOL_MAP: dict[str, dict[str, list[str]]] = {
        "intent": {"screener_mcp": [], "bridge": []},
        "planner": {"screener_mcp": [], "bridge": ["get_available_industries"]},
        "executor": {"screener_mcp": ["__ALL__"], "bridge": ["run_screening"]},
        "evaluator": {
            "screener_mcp": [],
            "bridge": ["save_screening_script"],
        },
    }

    def __init__(
        self,
        mcp_tools: list[Any],
        bridge_tools: dict[str, Any],
    ) -> None:
        """Initialize tool provider.

        Args:
            mcp_tools: List of MCP tool objects
            bridge_tools: Dict mapping tool name to tool callable
        """
        self._mcp_tools = mcp_tools
        self._bridge_tools = bridge_tools
        self._mcp_by_name = {t.name: t for t in mcp_tools}

        logger.info(
            "ScreenerToolProvider initialized with %d MCP tools and %d bridge tools",
            len(mcp_tools),
            len(bridge_tools),
        )

    def get_tools_for_agent(self, agent_name: str) -> list[Any]:
        """Return the tool set authorized for a specific agent.

        Args:
            agent_name: Name of the agent ("intent", "planner", "executor", "evaluator", "all")

        Returns:
            List of tool objects the agent can use
        """
        # Special case: return all tools
        if agent_name == "all":
            tools = list(self._mcp_tools) + list(self._bridge_tools.values())
            logger.debug("Returning ALL tools: %d total", len(tools))
            return tools

        spec = self._AGENT_TOOL_MAP.get(agent_name, {"screener_mcp": [], "bridge": []})
        tools: list[Any] = []

        # Add MCP tools
        mcp_names = spec["screener_mcp"]
        if "__ALL__" in mcp_names:
            tools.extend(self._mcp_tools)
            logger.debug("Agent '%s' receives ALL %d MCP tools", agent_name, len(self._mcp_tools))
        else:
            for name in mcp_names:
                if name in self._mcp_by_name:
                    tools.append(self._mcp_by_name[name])
            if mcp_names:
                logger.debug(
                    "Agent '%s' receives %d specific MCP tools", agent_name, len(mcp_names)
                )

        # Add bridge tools
        for bridge_name in spec["bridge"]:
            if bridge_name in self._bridge_tools:
                tools.append(self._bridge_tools[bridge_name])
            else:
                logger.warning(
                    "Bridge tool '%s' requested by agent '%s' not found",
                    bridge_name,
                    agent_name,
                )

        logger.debug("Agent '%s' total tools: %d", agent_name, len(tools))
        return tools

    def get_tool_descriptions(self) -> list[dict[str, str]]:
        """Return metadata-only descriptions (name + desc) for planning.

        Used by PlannerAgent to know what tools exist without executing them.

        Returns:
            List of dicts with 'name' and 'description' keys
        """
        descriptions = []
        for tool in self._mcp_tools:
            desc = {
                "name": tool.name,
                "description": getattr(tool, "description", ""),
            }
            descriptions.append(desc)

        logger.debug("Returning %d tool descriptions", len(descriptions))
        return descriptions

    @property
    def mcp_tool_names(self) -> list[str]:
        """Return list of all MCP tool names."""
        return list(self._mcp_by_name.keys())

    @property
    def bridge_tool_names(self) -> list[str]:
        """Return list of all bridge tool names."""
        return list(self._bridge_tools.keys())
