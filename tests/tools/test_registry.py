"""Tests for ToolRegistry."""
import pytest
from opencode.tools.base import Tool, ToolDefinition, ToolResult
from opencode.tools.registry import ToolRegistry


class FakeTool(Tool):
    def __init__(self, name: str, is_read_only: bool = False):
        self._name = name
        self._is_read_only = is_read_only

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self._name,
            description="A fake tool",
            is_read_only=self._is_read_only,
        )

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(content="executed")


class TestToolRegistry:
    def test_empty_initially(self):
        registry = ToolRegistry()
        assert registry.list_definitions() == []

    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = FakeTool("bash")
        registry.register(tool)
        retrieved = registry.get("bash")
        assert retrieved is tool

    def test_get_nonexistent_returns_none(self):
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None

    def test_list_definitions(self):
        registry = ToolRegistry()
        registry.register(FakeTool("bash"))
        registry.register(FakeTool("read"))
        defs = registry.list_definitions()
        names = {d.name for d in defs}
        assert names == {"bash", "read"}

    def test_register_overwrites_existing(self):
        registry = ToolRegistry()
        tool1 = FakeTool("bash")
        tool2 = FakeTool("bash")
        registry.register(tool1)
        registry.register(tool2)
        assert registry.get("bash") is tool2
        assert len(registry.list_definitions()) == 1

    def test_unregister(self):
        registry = ToolRegistry()
        registry.register(FakeTool("bash"))
        registry.unregister("bash")
        assert registry.get("bash") is None
        assert registry.list_definitions() == []

    def test_unregister_nonexistent_no_error(self):
        registry = ToolRegistry()
        registry.unregister("nonexistent")  # should not raise

    def test_multiple_tools(self):
        registry = ToolRegistry()
        tools = ["bash", "read", "write", "edit", "glob"]
        for name in tools:
            registry.register(FakeTool(name))
        assert len(registry.list_definitions()) == 5

    def test_definition_attributes_preserved(self):
        registry = ToolRegistry()
        registry.register(FakeTool("glob", is_read_only=True))
        defn = registry.list_definitions()[0]
        assert defn.is_read_only is True
        assert defn.name == "glob"
