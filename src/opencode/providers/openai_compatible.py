"""OpenAI-compatible provider for llama.cpp, vLLM, Ollama, OpenAI, etc."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

from openai import AsyncOpenAI, APIConnectionError, APITimeoutError, RateLimitError

from opencode.core.message import Message, Role, ToolCall, ToolResult, Usage
from opencode.providers.base import LLMProvider, StreamChunk
from opencode.tools.base import ToolDefinition

logger = logging.getLogger(__name__)

RETRYABLE_ERRORS = (APIConnectionError, APITimeoutError, RateLimitError)
MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2, 4]  # seconds


class OpenAICompatibleProvider(LLMProvider):
    """
    Provider for any OpenAI-compatible API endpoint.
    Works with: llama.cpp server, vLLM, Ollama, OpenAI, Together, Groq, etc.
    """

    def __init__(
        self,
        model: str = "default",
        base_url: str = "http://localhost:8080/v1",
        api_key: str = "not-needed",
        extra_params: dict[str, Any] | None = None,
    ) -> None:
        self.name = "openai-compatible"
        self.model = model
        self.extra_params = extra_params or {}
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    def format_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        """Convert to OpenAI function calling format."""
        result = []
        for tool in tools:
            result.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.to_json_schema(),
                },
            })
        return result

    def format_messages(
        self, messages: list[Message], system_prompt: str
    ) -> list[dict[str, Any]]:
        """Convert canonical messages to OpenAI chat format."""
        formatted: list[dict[str, Any]] = []

        if system_prompt:
            formatted.append({"role": "system", "content": system_prompt})

        for msg in messages:
            if msg.role == Role.USER:
                formatted.append({"role": "user", "content": msg.content})

            elif msg.role == Role.ASSISTANT:
                entry: dict[str, Any] = {"role": "assistant"}
                if msg.content:
                    entry["content"] = msg.content
                if msg.tool_calls:
                    entry["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                    if not msg.content:
                        entry["content"] = None
                formatted.append(entry)

            elif msg.role == Role.TOOL:
                for tr in msg.tool_results:
                    formatted.append({
                        "role": "tool",
                        "tool_call_id": tr.tool_call_id,
                        "content": tr.content,
                    })

        return formatted

    async def stream(
        self,
        messages: list[Message],
        system_prompt: str,
        tools: list[ToolDefinition],
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a response from the OpenAI-compatible endpoint."""
        formatted_messages = self.format_messages(messages, system_prompt)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        # Merge extra params (can override temperature, add top_p, top_k, etc.)
        if self.extra_params:
            kwargs["extra_body"] = {
                k: v for k, v in self.extra_params.items()
                if k not in ("temperature", "max_tokens")
            }
            # temperature and max_tokens are first-class OpenAI params
            if "temperature" in self.extra_params:
                kwargs["temperature"] = self.extra_params["temperature"]
            if "max_tokens" in self.extra_params:
                kwargs["max_tokens"] = self.extra_params["max_tokens"]

        if tools:
            formatted_tools = self.format_tools(tools)
            kwargs["tools"] = formatted_tools

        response = await self._create_with_retry(**kwargs)

        async for chunk in response:
            if not chunk.choices and chunk.usage:
                # Final usage-only chunk
                yield StreamChunk(
                    usage=Usage(
                        input_tokens=chunk.usage.prompt_tokens or 0,
                        output_tokens=chunk.usage.completion_tokens or 0,
                        total_tokens=chunk.usage.total_tokens or 0,
                    )
                )
                continue

            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            delta = choice.delta

            sc = StreamChunk(finish_reason=choice.finish_reason)

            if delta.content:
                sc.text = delta.content

            if delta.tool_calls:
                tc_delta = delta.tool_calls[0]
                if tc_delta.id:
                    sc.tool_call_id = tc_delta.id
                if tc_delta.function and tc_delta.function.name:
                    sc.tool_call_name = tc_delta.function.name
                if tc_delta.function and tc_delta.function.arguments:
                    sc.tool_call_arguments_delta = tc_delta.function.arguments

            yield sc

    async def _create_with_retry(self, **kwargs: Any) -> Any:
        """Call chat.completions.create with retries on transient errors."""
        for attempt in range(MAX_RETRIES):
            try:
                return await self._client.chat.completions.create(**kwargs)
            except RETRYABLE_ERRORS as e:
                if attempt == MAX_RETRIES - 1:
                    raise
                wait = RETRY_BACKOFF[attempt]
                logger.warning(f"API error (attempt {attempt + 1}/{MAX_RETRIES}): {e}. Retrying in {wait}s...")
                await asyncio.sleep(wait)
        raise RuntimeError("Unreachable")
