"""Tests for Conversation history management."""
import pytest
from opencode.core.conversation import Conversation
from opencode.core.message import Message, Role, ToolCall, ToolResult


class TestConversation:
    def test_empty_initially(self):
        conv = Conversation()
        assert conv.messages == []

    def test_system_prompt_stored(self):
        conv = Conversation(system_prompt="You are helpful.")
        assert conv.system_prompt == "You are helpful."

    def test_add_user_message(self):
        conv = Conversation()
        conv.add_user_message("hello")
        assert len(conv.messages) == 1
        assert conv.messages[0].role == Role.USER
        assert conv.messages[0].content == "hello"

    def test_add_assistant_message(self):
        conv = Conversation()
        msg = Message(role=Role.ASSISTANT, content="hi there")
        conv.add_assistant_message(msg)
        assert len(conv.messages) == 1
        assert conv.messages[0].content == "hi there"

    def test_add_tool_results(self):
        conv = Conversation()
        results = [
            Message(role=Role.TOOL, content="result1"),
            Message(role=Role.TOOL, content="result2"),
        ]
        conv.add_tool_results(results)
        assert len(conv.messages) == 2

    def test_clear_removes_messages(self):
        conv = Conversation(system_prompt="sys")
        conv.add_user_message("a")
        conv.add_user_message("b")
        conv.clear()
        assert conv.messages == []
        assert conv.system_prompt == "sys"  # prompt preserved

    def test_token_estimate_empty(self):
        conv = Conversation()
        assert conv.token_estimate() == 0

    def test_token_estimate_counts_system_prompt(self):
        # 40 chars system prompt → ~10 tokens
        conv = Conversation(system_prompt="a" * 40)
        assert conv.token_estimate() == 10

    def test_token_estimate_counts_messages(self):
        conv = Conversation()
        conv.add_user_message("x" * 80)  # 80 chars → 20 tokens
        assert conv.token_estimate() == 20

    def test_token_estimate_includes_tool_calls(self):
        conv = Conversation()
        tc = ToolCall(id="1", name="bash", arguments={"command": "ls"})
        msg = Message(role=Role.ASSISTANT, tool_calls=[tc])
        conv.add_assistant_message(msg)
        # arguments str has some chars — estimate should be > 0
        assert conv.token_estimate() > 0

    def test_token_estimate_includes_tool_results(self):
        conv = Conversation()
        tr = ToolResult(tool_call_id="1", name="bash", content="x" * 400)
        msg = Message(role=Role.TOOL, tool_results=[tr])
        conv.add_tool_results([msg])
        # 400 chars → 100 tokens
        assert conv.token_estimate() == 100

    def test_compact_no_op_when_few_messages(self):
        conv = Conversation()
        for i in range(4):
            conv.add_user_message(f"msg {i}")
        conv.compact("summary")
        # 4 messages ≤ keep_last_n=4, should not compact
        assert len(conv.messages) == 4

    def test_compact_replaces_older_messages(self):
        conv = Conversation()
        for i in range(10):
            conv.add_user_message(f"msg {i}")
        conv.compact("the summary")
        # 1 summary message + 4 kept messages
        assert len(conv.messages) == 5
        assert "the summary" in conv.messages[0].content
        assert conv.messages[0].role == Role.USER

    def test_compact_keeps_last_4(self):
        conv = Conversation()
        messages = [f"message {i}" for i in range(8)]
        for m in messages:
            conv.add_user_message(m)
        conv.compact("summary")
        kept_contents = [m.content for m in conv.messages[1:]]
        assert kept_contents == messages[-4:]

    def test_compact_custom_keep_n(self):
        conv = Conversation()
        for i in range(10):
            conv.add_user_message(f"msg {i}")
        conv.compact("summary", keep_last_n=2)
        assert len(conv.messages) == 3  # 1 summary + 2 kept
