"""Abstract base for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from opencode.core.message import Message, Usage
from opencode.tools.base import ToolDefinition


@dataclass
class StreamChunk:
    """One piece of a streaming response."""

    text: str | None = None
    tool_call_id: str | None = None
    tool_call_name: str | None = None
    tool_call_arguments_delta: str | None = None
    usage: Usage | None = None
    finish_reason: str | None = None


class LLMProvider(ABC):
    """
    Abstract interface for all LLM providers.
    Each provider translates between our canonical Message format
    and the provider's wire format.
    """

    name: str
    model: str

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        system_prompt: str,
        tools: list[ToolDefinition],
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a response from the LLM."""
        ...

    @abstractmethod
    def format_messages(self, messages: list[Message], system_prompt: str) -> list[dict[str, Any]]:
        """Convert canonical messages to provider wire format."""
        ...

    @abstractmethod
    def format_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        """Convert canonical tool definitions to provider-specific format."""
        ...
