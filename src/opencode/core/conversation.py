"""Conversation history management."""

from __future__ import annotations

from opencode.core.message import Message, Role


class Conversation:
    """Maintains the ordered list of messages for the current session."""

    def __init__(self, system_prompt: str = "") -> None:
        self.system_prompt = system_prompt
        self.messages: list[Message] = []

    def add_user_message(self, text: str) -> None:
        self.messages.append(Message(role=Role.USER, content=text))

    def add_assistant_message(self, msg: Message) -> None:
        self.messages.append(msg)

    def add_tool_results(self, results: list[Message]) -> None:
        """Append tool result messages."""
        self.messages.extend(results)

    def clear(self) -> None:
        """Clear all messages but keep the system prompt."""
        self.messages.clear()

    def token_estimate(self) -> int:
        """Rough token count using ~4 chars per token heuristic."""
        total = len(self.system_prompt) // 4
        for msg in self.messages:
            total += len(msg.content) // 4
            for tc in msg.tool_calls:
                total += len(str(tc.arguments)) // 4
            for tr in msg.tool_results:
                total += len(tr.content) // 4
        return total

    def compact(self, summary: str, keep_last_n: int = 4) -> None:
        """Replace older messages with a summary, keep recent ones."""
        if len(self.messages) <= keep_last_n:
            return
        kept = self.messages[-keep_last_n:]
        self.messages = [
            Message(role=Role.USER, content=f"[Previous conversation summary]\n{summary}"),
        ] + kept
