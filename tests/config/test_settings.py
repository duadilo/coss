"""Tests for config settings models."""
import pytest
from opencode.config.settings import (
    HookEntry,
    MCPServerEntry,
    PermissionSettings,
    ProviderSettings,
    Settings,
)


class TestProviderSettings:
    def test_defaults(self):
        ps = ProviderSettings()
        assert ps.model == "default"
        assert ps.api_key is None
        assert ps.base_url is None
        assert ps.max_tokens == 4096
        assert ps.max_context_tokens == 128_000
        assert ps.temperature == 0.0
        assert ps.extra_params == {}

    def test_custom_values(self):
        ps = ProviderSettings(
            model="anthropic:claude-opus",
            api_key="sk-test",
            base_url="http://localhost",
            max_tokens=2048,
            temperature=0.7,
        )
        assert ps.model == "anthropic:claude-opus"
        assert ps.api_key == "sk-test"
        assert ps.max_tokens == 2048
        assert ps.temperature == 0.7


class TestPermissionSettings:
    def test_defaults(self):
        ps = PermissionSettings()
        assert ps.auto_allow_read_tools is True
        assert ps.auto_allow_write_tools is False
        assert ps.auto_allow_bash is False
        assert ps.allowed_bash_commands == []

    def test_custom_bash_commands(self):
        ps = PermissionSettings(allowed_bash_commands=["git *", "pytest *"])
        assert "git *" in ps.allowed_bash_commands
        assert "pytest *" in ps.allowed_bash_commands


class TestMCPServerEntry:
    def test_defaults(self):
        entry = MCPServerEntry(command="my-server")
        assert entry.command == "my-server"
        assert entry.args == []
        assert entry.env == {}
        assert entry.transport == "stdio"
        assert entry.url is None

    def test_http_transport(self):
        entry = MCPServerEntry(
            command="server",
            transport="streamable-http",
            url="http://localhost:3000",
        )
        assert entry.transport == "streamable-http"
        assert entry.url == "http://localhost:3000"


class TestHookEntry:
    def test_pre_tool_call_hook(self):
        hook = HookEntry(event="pre_tool_call", command="echo pre")
        assert hook.event == "pre_tool_call"
        assert hook.tool_pattern == "*"
        assert hook.command == "echo pre"

    def test_post_tool_call_hook(self):
        hook = HookEntry(event="post_tool_call", tool_pattern="bash", command="log.sh")
        assert hook.event == "post_tool_call"
        assert hook.tool_pattern == "bash"

    def test_default_tool_pattern(self):
        hook = HookEntry(event="pre_tool_call", command="check.sh")
        assert hook.tool_pattern == "*"


class TestSettings:
    def test_defaults(self):
        s = Settings()
        assert isinstance(s.provider, ProviderSettings)
        assert isinstance(s.permissions, PermissionSettings)
        assert s.mcp_servers == {}
        assert s.hooks == []
        assert s.compact_threshold == 0.8
        assert s.system_prompt_extra == ""

    def test_nested_construction(self):
        s = Settings(
            provider=ProviderSettings(model="anthropic:claude-opus"),
            permissions=PermissionSettings(auto_allow_bash=True),
            compact_threshold=0.9,
        )
        assert s.provider.model == "anthropic:claude-opus"
        assert s.permissions.auto_allow_bash is True
        assert s.compact_threshold == 0.9

    def test_with_hooks(self):
        s = Settings(
            hooks=[
                HookEntry(event="pre_tool_call", tool_pattern="bash", command="guard.sh"),
            ]
        )
        assert len(s.hooks) == 1
        assert s.hooks[0].tool_pattern == "bash"
