"""Tests for tool base classes and ToolDefinition.to_json_schema."""
import pytest
from opencode.tools.base import ToolDefinition, ToolParameter, ToolResult


class TestToolParameter:
    def test_required_by_default(self):
        p = ToolParameter(name="x", type="string", description="desc")
        assert p.required is True

    def test_optional_parameter(self):
        p = ToolParameter(name="x", type="string", description="desc", required=False)
        assert p.required is False

    def test_enum(self):
        p = ToolParameter(name="mode", type="string", description="d", enum=["a", "b"])
        assert p.enum == ["a", "b"]

    def test_default(self):
        p = ToolParameter(name="x", type="boolean", description="d", default=False)
        assert p.default is False


class TestToolDefinition:
    def test_basic_schema(self):
        td = ToolDefinition(
            name="my_tool",
            description="does things",
            parameters=[
                ToolParameter(name="path", type="string", description="file path"),
            ],
        )
        schema = td.to_json_schema()
        assert schema["type"] == "object"
        assert "path" in schema["properties"]
        assert schema["properties"]["path"]["type"] == "string"
        assert "path" in schema["required"]

    def test_optional_params_not_in_required(self):
        td = ToolDefinition(
            name="tool",
            description="desc",
            parameters=[
                ToolParameter(name="req", type="string", description="required"),
                ToolParameter(name="opt", type="integer", description="optional", required=False),
            ],
        )
        schema = td.to_json_schema()
        assert "req" in schema["required"]
        assert "opt" not in schema["required"]

    def test_enum_in_schema(self):
        td = ToolDefinition(
            name="tool",
            description="desc",
            parameters=[
                ToolParameter(name="mode", type="string", description="mode", enum=["fast", "slow"]),
            ],
        )
        schema = td.to_json_schema()
        assert schema["properties"]["mode"]["enum"] == ["fast", "slow"]

    def test_default_in_schema(self):
        td = ToolDefinition(
            name="tool",
            description="desc",
            parameters=[
                ToolParameter(name="verbose", type="boolean", description="v", required=False, default=False),
            ],
        )
        schema = td.to_json_schema()
        assert schema["properties"]["verbose"]["default"] is False

    def test_no_required_key_when_all_optional(self):
        td = ToolDefinition(
            name="tool",
            description="desc",
            parameters=[
                ToolParameter(name="opt", type="string", description="d", required=False),
            ],
        )
        schema = td.to_json_schema()
        assert "required" not in schema

    def test_empty_parameters(self):
        td = ToolDefinition(name="tool", description="desc")
        schema = td.to_json_schema()
        assert schema["type"] == "object"
        assert schema["properties"] == {}
        assert "required" not in schema

    def test_read_only_defaults_false(self):
        td = ToolDefinition(name="tool", description="desc")
        assert td.is_read_only is False

    def test_requires_permission_defaults_true(self):
        td = ToolDefinition(name="tool", description="desc")
        assert td.requires_permission is True


class TestToolResult:
    def test_success_result(self):
        tr = ToolResult(content="done")
        assert tr.content == "done"
        assert tr.is_error is False

    def test_error_result(self):
        tr = ToolResult(content="failed", is_error=True)
        assert tr.is_error is True
