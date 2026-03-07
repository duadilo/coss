"""Google Gemini provider."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from google import genai
from google.genai import types

from opencode.core.message import Message, Role, ToolCall, ToolResult, Usage
from opencode.providers.base import LLMProvider, StreamChunk
from opencode.tools.base import ToolDefinition


class GoogleProvider(LLMProvider):
    """Provider for Google Gemini models via the google-genai SDK."""

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        api_key: str | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> None:
        self.name = "google"
        self.model = model
        self.extra_params = extra_params or {}
        self._client = genai.Client(api_key=api_key)

    def format_tools(self, tools: list[ToolDefinition]) -> list[types.Tool]:
        """Convert to Gemini function declarations."""
        declarations = []
        for tool in tools:
            schema = tool.to_json_schema()
            declarations.append(types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters=schema,
            ))
        return [types.Tool(function_declarations=declarations)]

    def format_messages(
        self, messages: list[Message], system_prompt: str
    ) -> list[types.Content]:
        """Convert canonical messages to Gemini Content format."""
        contents: list[types.Content] = []

        for msg in messages:
            if msg.role == Role.USER:
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=msg.content)],
                ))

            elif msg.role == Role.ASSISTANT:
                parts: list[types.Part] = []
                if msg.content:
                    parts.append(types.Part.from_text(text=msg.content))
                for tc in msg.tool_calls:
                    parts.append(types.Part.from_function_call(
                        name=tc.name,
                        args=tc.arguments,
                    ))
                contents.append(types.Content(role="model", parts=parts))

            elif msg.role == Role.TOOL:
                parts = []
                for tr in msg.tool_results:
                    parts.append(types.Part.from_function_response(
                        name=tr.name,
                        response={"result": tr.content, "is_error": tr.is_error},
                    ))
                contents.append(types.Content(role="user", parts=parts))

        return contents

    async def stream(
        self,
        messages: list[Message],
        system_prompt: str,
        tools: list[ToolDefinition],
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a response from the Gemini API."""
        contents = self.format_messages(messages, system_prompt)

        # Apply extra params
        if "temperature" in self.extra_params:
            temperature = self.extra_params["temperature"]
        if "max_tokens" in self.extra_params:
            max_tokens = self.extra_params["max_tokens"]

        config_kwargs: dict[str, Any] = {
            "system_instruction": system_prompt,
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if "top_p" in self.extra_params:
            config_kwargs["top_p"] = self.extra_params["top_p"]
        if "top_k" in self.extra_params:
            config_kwargs["top_k"] = self.extra_params["top_k"]
        if "presence_penalty" in self.extra_params:
            config_kwargs["presence_penalty"] = self.extra_params["presence_penalty"]

        config = types.GenerateContentConfig(**config_kwargs)
        if tools:
            config.tools = self.format_tools(tools)

        response = self._client.models.generate_content_stream(
            model=self.model,
            contents=contents,
            config=config,
        )

        total_text = ""
        for chunk in response:
            if not chunk.candidates:
                continue

            candidate = chunk.candidates[0]
            if not candidate.content or not candidate.content.parts:
                continue

            for part in candidate.content.parts:
                if part.text:
                    total_text += part.text
                    yield StreamChunk(text=part.text)
                elif part.function_call:
                    fc = part.function_call
                    # Gemini returns complete function calls, not deltas
                    call_id = f"call_{fc.name}_{id(fc)}"
                    args_json = json.dumps(dict(fc.args)) if fc.args else "{}"
                    yield StreamChunk(
                        tool_call_id=call_id,
                        tool_call_name=fc.name,
                        tool_call_arguments_delta=args_json,
                    )

            # Check finish reason
            if candidate.finish_reason:
                yield StreamChunk(finish_reason=str(candidate.finish_reason))

        # Usage from the final chunk
        if chunk and chunk.usage_metadata:
            meta = chunk.usage_metadata
            yield StreamChunk(
                usage=Usage(
                    input_tokens=meta.prompt_token_count or 0,
                    output_tokens=meta.candidates_token_count or 0,
                    total_tokens=meta.total_token_count or 0,
                )
            )
