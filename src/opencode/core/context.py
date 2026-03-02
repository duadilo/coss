"""Context window management with automatic compaction."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from opencode.core.conversation import Conversation
from opencode.core.message import Message, Role, Usage

if TYPE_CHECKING:
    from opencode.providers.base import LLMProvider


SUMMARY_PROMPT = """\
Summarize the conversation so far for context continuity. Preserve:
- Key decisions made and their rationale
- File paths that were read, edited, or created
- Important tool results (errors, findings, test outcomes)
- The current state of the task (what's done, what's remaining)
- Any user preferences or instructions mentioned

Be concise but thorough. Use bullet points. This summary replaces the older \
messages and will be the only context for the ongoing conversation."""


class ContextManager:
    """
    Tracks estimated token usage and triggers compression when
    approaching the context window limit.
    """

    def __init__(
        self,
        max_tokens: int = 128_000,
        compact_threshold: float = 0.8,
    ) -> None:
        self._max_tokens = max_tokens
        self._threshold = compact_threshold

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    def should_compact(self, conversation: Conversation) -> bool:
        """Check if the conversation is approaching the context limit."""
        estimated = conversation.token_estimate()
        return estimated > int(self._max_tokens * self._threshold)

    async def compact(
        self,
        conversation: Conversation,
        provider: LLMProvider,
    ) -> str:
        """
        Compress conversation by summarizing older messages.

        1. Take all messages except the most recent 4
        2. Ask the LLM to summarize them
        3. Replace old messages with the summary
        4. Return the summary text
        """
        keep_last_n = 4
        if len(conversation.messages) <= keep_last_n:
            return ""

        older_messages = conversation.messages[:-keep_last_n]

        # Build a summary request from the older messages
        summary_text = self._messages_to_text(older_messages)
        summary_request = f"{SUMMARY_PROMPT}\n\n---\n\nConversation to summarize:\n{summary_text}"

        # Use the provider to generate a summary (non-streaming)
        summary_messages = [Message(role=Role.USER, content=summary_request)]

        accumulated = ""
        async for chunk in provider.stream(
            summary_messages,
            system_prompt="You are a helpful assistant that summarizes conversations concisely.",
            tools=[],
            max_tokens=2048,
        ):
            if chunk.text:
                accumulated += chunk.text

        if accumulated:
            conversation.compact(accumulated, keep_last_n=keep_last_n)

        return accumulated

    def _messages_to_text(self, messages: list[Message]) -> str:
        """Convert messages to readable text for summarization."""
        parts: list[str] = []
        for msg in messages:
            prefix = msg.role.value.upper()
            if msg.content:
                parts.append(f"[{prefix}]: {msg.content[:2000]}")
            for tc in msg.tool_calls:
                args_str = json.dumps(tc.arguments)[:500]
                parts.append(f"[{prefix} TOOL CALL]: {tc.name}({args_str})")
            for tr in msg.tool_results:
                content_preview = tr.content[:1000]
                status = "ERROR" if tr.is_error else "OK"
                parts.append(f"[TOOL RESULT {status}]: {tr.name}: {content_preview}")
        return "\n".join(parts)
