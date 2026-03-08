"""Tests for core message models."""
import pytest
from opencode.core.message import Message, Role, ToolCall, ToolResult, Usage


class TestRole:
    def test_values(self):
        assert Role.USER == "user"
        assert Role.ASSISTANT == "assistant"
        assert Role.SYSTEM == "system"
        assert Role.TOOL == "tool"

    def test_is_str_enum(self):
        assert isinstance(Role.USER, str)


class TestToolCall:
    def test_basic(self):
        tc = ToolCall(id="1", name="bash", arguments={"command": "ls"})
        assert tc.id == "1"
        assert tc.name == "bash"
        assert tc.arguments == {"command": "ls"}

    def test_default_arguments(self):
        tc = ToolCall(id="x", name="read")
        assert tc.arguments == {}

    def test_arguments_are_independent(self):
        tc1 = ToolCall(id="1", name="a")
        tc2 = ToolCall(id="2", name="b")
        tc1.arguments["key"] = "val"
        assert "key" not in tc2.arguments


class TestToolResult:
    def test_basic(self):
        tr = ToolResult(tool_call_id="1", name="bash", content="output")
        assert tr.tool_call_id == "1"
        assert tr.name == "bash"
        assert tr.content == "output"
        assert tr.is_error is False

    def test_error_flag(self):
        tr = ToolResult(tool_call_id="1", name="bash", content="err", is_error=True)
        assert tr.is_error is True


class TestUsage:
    def test_defaults(self):
        u = Usage()
        assert u.input_tokens == 0
        assert u.output_tokens == 0
        assert u.total_tokens == 0

    def test_fields(self):
        u = Usage(input_tokens=100, output_tokens=50, total_tokens=150)
        assert u.input_tokens == 100
        assert u.output_tokens == 50
        assert u.total_tokens == 150


class TestMessage:
    def test_user_message(self):
        msg = Message(role=Role.USER, content="hello")
        assert msg.role == Role.USER
        assert msg.content == "hello"
        assert msg.tool_calls == []
        assert msg.tool_results == []

    def test_has_tool_calls_false(self):
        msg = Message(role=Role.ASSISTANT, content="hi")
        assert msg.has_tool_calls is False

    def test_has_tool_calls_true(self):
        tc = ToolCall(id="1", name="bash", arguments={"command": "echo"})
        msg = Message(role=Role.ASSISTANT, tool_calls=[tc])
        assert msg.has_tool_calls is True

    def test_default_content(self):
        msg = Message(role=Role.USER)
        assert msg.content == ""

    def test_usage_default(self):
        msg = Message(role=Role.ASSISTANT)
        assert msg.usage.input_tokens == 0
        assert msg.usage.output_tokens == 0
