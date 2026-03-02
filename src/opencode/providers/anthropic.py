"""Anthropic Claude provider."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import anthropic

from opencode.core.message import Message, Role, ToolCall, ToolResult, Usage
from opencode.providers.base import LLMProvider, StreamChunk
from opencode.tools.base import ToolDefinition


class AnthropicProvider(LLMProvider):
    """Provider for the Anthropic API (Claude models)."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
    ) -> None:
        self.name = "anthropic"
        self.model = model
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    def format_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        """Anthropic format: {name, description, input_schema}."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.to_json_schema(),
            }
            for tool in tools
        ]

    def format_messages(
        self, messages: list[Message], system_prompt: str
    ) -> list[dict[str, Any]]:
        """
        Convert canonical messages to Anthropic format.

        Anthropic requires strict user/assistant alternation.
        Tool results go inside user messages as tool_result content blocks.
        """
        formatted: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == Role.USER:
                formatted.append({"role": "user", "content": msg.content})

            elif msg.role == Role.ASSISTANT:
                content: list[dict[str, Any]] = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    })
                formatted.append({"role": "assistant", "content": content})

            elif msg.role == Role.TOOL:
                # Anthropic: tool results go in a user message
                content_blocks: list[dict[str, Any]] = []
                for tr in msg.tool_results:
                    content_blocks.append({
                        "type": "tool_result",
                        "tool_use_id": tr.tool_call_id,
                        "content": tr.content,
                        "is_error": tr.is_error,
                    })
                formatted.append({"role": "user", "content": content_blocks})

        # Merge consecutive same-role messages (Anthropic requires alternation)
        merged: list[dict[str, Any]] = []
        for entry in formatted:
            if merged and merged[-1]["role"] == entry["role"]:
                # Merge content
                prev = merged[-1]["content"]
                curr = entry["content"]
                if isinstance(prev, str) and isinstance(curr, str):
                    merged[-1]["content"] = prev + "\n" + curr
                elif isinstance(prev, list) and isinstance(curr, list):
                    merged[-1]["content"] = prev + curr
                elif isinstance(prev, str) and isinstance(curr, list):
                    merged[-1]["content"] = [{"type": "text", "text": prev}] + curr
                elif isinstance(prev, list) and isinstance(curr, str):
                    merged[-1]["content"] = prev + [{"type": "text", "text": curr}]
            else:
                merged.append(entry)

        return merged

    async def stream(
        self,
        messages: list[Message],
        system_prompt: str,
        tools: list[ToolDefinition],
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a response from the Anthropic API."""
        formatted_messages = self.format_messages(messages, system_prompt)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
            "system": system_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            kwargs["tools"] = self.format_tools(tools)

        async with self._client.messages.stream(**kwargs) as stream:
            current_tool_id: str | None = None
            current_tool_name: str | None = None

            async for event in stream:
                if event.type == "content_block_start":
                    block = event.content_block
                    if block.type == "tool_use":
                        current_tool_id = block.id
                        current_tool_name = block.name
                        yield StreamChunk(
                            tool_call_id=block.id,
                            tool_call_name=block.name,
                        )
                    elif block.type == "text":
                        pass  # text deltas come in content_block_delta

                elif event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        yield StreamChunk(text=delta.text)
                    elif delta.type == "input_json_delta":
                        yield StreamChunk(
                            tool_call_arguments_delta=delta.partial_json,
                        )

                elif event.type == "content_block_stop":
                    current_tool_id = None
                    current_tool_name = None

                elif event.type == "message_delta":
                    yield StreamChunk(
                        finish_reason=event.delta.stop_reason,
                    )

            # Get final message for usage
            final = await stream.get_final_message()
            yield StreamChunk(
                usage=Usage(
                    input_tokens=final.usage.input_tokens,
                    output_tokens=final.usage.output_tokens,
                    total_tokens=final.usage.input_tokens + final.usage.output_tokens,
                )
            )
