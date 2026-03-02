"""Permission system for gating tool execution."""

from __future__ import annotations

from enum import Enum

from opencode.core.message import ToolCall
from opencode.tools.base import ToolDefinition


class PermissionDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    PROMPT = "prompt"


class PermissionManager:
    """
    Determines whether a tool call should be allowed, denied, or prompted.

    Rules:
    1. Read-only tools -> ALLOW
    2. Tools with session "always allow" -> ALLOW
    3. Otherwise -> PROMPT
    """

    def __init__(self) -> None:
        self._always_allow: set[str] = set()

    def check(self, tool_call: ToolCall, tool_def: ToolDefinition) -> PermissionDecision:
        if tool_def.is_read_only and not tool_def.requires_permission:
            return PermissionDecision.ALLOW
        if tool_call.name in self._always_allow:
            return PermissionDecision.ALLOW
        return PermissionDecision.PROMPT

    def set_always_allow(self, tool_name: str) -> None:
        self._always_allow.add(tool_name)
