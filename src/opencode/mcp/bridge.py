"""Bridge MCP server tools to native opencode Tool instances."""

from __future__ import annotations

from typing import Any

from opencode.tools.base import Tool, ToolDefinition, ToolParameter, ToolResult


class MCPToolBridge(Tool):
    """
    Wraps an MCP server tool as a native opencode Tool.
    Translates between our ToolDefinition/ToolResult and MCP's format.
    """

    def __init__(self, session: Any, mcp_tool: Any, server_name: str) -> None:
        self._session = session
        self._mcp_tool = mcp_tool
        self._server_name = server_name

    def definition(self) -> ToolDefinition:
        # Parse MCP input schema into our ToolParameter format
        params: list[ToolParameter] = []
        input_schema = getattr(self._mcp_tool, "inputSchema", None) or {}

        if isinstance(input_schema, dict):
            properties = input_schema.get("properties", {})
            required = input_schema.get("required", [])

            for name, prop in properties.items():
                params.append(ToolParameter(
                    name=name,
                    type=prop.get("type", "string"),
                    description=prop.get("description", ""),
                    required=name in required,
                    enum=prop.get("enum"),
                    default=prop.get("default"),
                ))

        tool_name = self._mcp_tool.name
        # Prefix with server name to avoid collisions
        prefixed_name = f"mcp_{self._server_name}_{tool_name}"

        return ToolDefinition(
            name=prefixed_name,
            description=getattr(self._mcp_tool, "description", "") or f"MCP tool: {tool_name}",
            parameters=params,
            is_read_only=False,
            requires_permission=True,
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            result = await self._session.call_tool(self._mcp_tool.name, kwargs)

            # Extract text from content parts
            text_parts: list[str] = []
            if hasattr(result, "content"):
                for part in result.content:
                    if hasattr(part, "text"):
                        text_parts.append(part.text)
                    elif hasattr(part, "data"):
                        text_parts.append(str(part.data))

            content = "\n".join(text_parts) if text_parts else str(result)
            is_error = getattr(result, "isError", False)

            return ToolResult(content=content, is_error=is_error)
        except Exception as e:
            return ToolResult(content=f"MCP tool error: {e}", is_error=True)
