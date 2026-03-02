"""Canonical, provider-agnostic message data models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ToolCall(BaseModel):
    """A tool invocation requested by the LLM."""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """The result of executing a tool."""

    tool_call_id: str
    name: str
    content: str
    is_error: bool = False


class Usage(BaseModel):
    """Token usage statistics for a single LLM call."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class Message(BaseModel):
    """A single message in the conversation."""

    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0
