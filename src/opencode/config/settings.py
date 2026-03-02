"""Settings model for opencode configuration."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderSettings(BaseModel):
    """LLM provider configuration."""

    model: str = "default"
    api_key: str | None = None
    base_url: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.0


class PermissionSettings(BaseModel):
    """Permission policies."""

    auto_allow_read_tools: bool = True
    auto_allow_write_tools: bool = False
    auto_allow_bash: bool = False
    allowed_bash_commands: list[str] = Field(default_factory=list)


class MCPServerEntry(BaseModel):
    """Configuration for a single MCP server."""

    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    transport: str = "stdio"
    url: str | None = None


class HookEntry(BaseModel):
    """Configuration for a pre/post tool hook."""

    event: str  # "pre_tool_call", "post_tool_call"
    tool_pattern: str = "*"
    command: str


class Settings(BaseModel):
    """Root settings model."""

    provider: ProviderSettings = Field(default_factory=ProviderSettings)
    permissions: PermissionSettings = Field(default_factory=PermissionSettings)
    mcp_servers: dict[str, MCPServerEntry] = Field(default_factory=dict)
    hooks: list[HookEntry] = Field(default_factory=list)
    max_context_tokens: int = 128_000
    compact_threshold: float = 0.8
    system_prompt_extra: str = ""
