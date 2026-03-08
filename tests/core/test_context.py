"""Tests for ContextManager."""
import pytest
from opencode.core.context import ContextManager
from opencode.core.conversation import Conversation
from opencode.core.message import Message, Role, ToolCall, ToolResult


class TestContextManagerShouldCompact:
    def test_no_compact_when_empty(self):
        cm = ContextManager(max_tokens=1000, compact_threshold=0.8)
        conv = Conversation()
        assert cm.should_compact(conv) is False

    def test_no_compact_below_threshold(self):
        cm = ContextManager(max_tokens=1000, compact_threshold=0.8)
        conv = Conversation()
        # 400 chars → 100 tokens; threshold is 800 tokens
        conv.add_user_message("x" * 400)
        assert cm.should_compact(conv) is False

    def test_compact_above_threshold(self):
        cm = ContextManager(max_tokens=1000, compact_threshold=0.8)
        conv = Conversation()
        # 3500 chars → 875 tokens > 800 threshold
        conv.add_user_message("x" * 3500)
        assert cm.should_compact(conv) is True

    def test_compact_exactly_at_threshold(self):
        cm = ContextManager(max_tokens=1000, compact_threshold=0.8)
        conv = Conversation()
        # 3200 chars → 800 tokens = threshold, not strictly greater
        conv.add_user_message("x" * 3200)
        assert cm.should_compact(conv) is False

    def test_custom_threshold(self):
        cm = ContextManager(max_tokens=1000, compact_threshold=0.5)
        conv = Conversation()
        # 2100 chars → 525 tokens > 500 (50% of 1000)
        conv.add_user_message("x" * 2100)
        assert cm.should_compact(conv) is True

    def test_max_tokens_property(self):
        cm = ContextManager(max_tokens=50_000)
        assert cm.max_tokens == 50_000


class TestContextManagerMessagesToText:
    def test_user_message(self):
        cm = ContextManager()
        msgs = [Message(role=Role.USER, content="hello world")]
        text = cm._messages_to_text(msgs)
        assert "[USER]: hello world" in text

    def test_assistant_message(self):
        cm = ContextManager()
        msgs = [Message(role=Role.ASSISTANT, content="I will help")]
        text = cm._messages_to_text(msgs)
        assert "[ASSISTANT]: I will help" in text

    def test_tool_call_in_text(self):
        cm = ContextManager()
        tc = ToolCall(id="1", name="bash", arguments={"command": "ls"})
        msgs = [Message(role=Role.ASSISTANT, tool_calls=[tc])]
        text = cm._messages_to_text(msgs)
        assert "TOOL CALL" in text
        assert "bash" in text

    def test_tool_result_ok(self):
        cm = ContextManager()
        tr = ToolResult(tool_call_id="1", name="bash", content="file.txt", is_error=False)
        msgs = [Message(role=Role.TOOL, tool_results=[tr])]
        text = cm._messages_to_text(msgs)
        assert "TOOL RESULT OK" in text
        assert "bash" in text
        assert "file.txt" in text

    def test_tool_result_error(self):
        cm = ContextManager()
        tr = ToolResult(tool_call_id="1", name="bash", content="error msg", is_error=True)
        msgs = [Message(role=Role.TOOL, tool_results=[tr])]
        text = cm._messages_to_text(msgs)
        assert "TOOL RESULT ERROR" in text

    def test_content_truncated_at_2000(self):
        cm = ContextManager()
        long_content = "x" * 3000
        msgs = [Message(role=Role.USER, content=long_content)]
        text = cm._messages_to_text(msgs)
        # Should only include first 2000 chars of content
        assert len(text) < 3000 + 50  # 50 for prefix

    def test_empty_messages_returns_empty(self):
        cm = ContextManager()
        assert cm._messages_to_text([]) == ""

    def test_message_without_content_skipped(self):
        cm = ContextManager()
        msgs = [Message(role=Role.ASSISTANT, content="")]
        text = cm._messages_to_text(msgs)
        assert "[ASSISTANT]:" not in text
