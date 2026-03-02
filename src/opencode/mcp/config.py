"""MCP server configuration models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server."""

    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    transport: str = "stdio"  # "stdio" or "streamable-http"
    url: str | None = None  # for HTTP transport
