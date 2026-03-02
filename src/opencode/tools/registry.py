"""Central registry for all available tools."""

from __future__ import annotations

from opencode.tools.base import Tool, ToolDefinition


class ToolRegistry:
    """Register, lookup, and list tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        defn = tool.definition()
        self._tools[defn.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_definitions(self) -> list[ToolDefinition]:
        return [t.definition() for t in self._tools.values()]

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)
