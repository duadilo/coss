"""Permission system for gating tool execution."""

from __future__ import annotations

import fnmatch
from enum import Enum

from opencode.core.message import ToolCall
from opencode.tools.base import ToolDefinition


class PermissionDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    PROMPT = "prompt"


class PermissionCategory(Enum):
    READ = "read"
    WRITE = "write"
    BASH = "bash"
    WEB = "web"
    OTHER = "other"


_TOOL_CATEGORIES: dict[str, PermissionCategory] = {
    "bash": PermissionCategory.BASH,
    "edit": PermissionCategory.WRITE,
    "write": PermissionCategory.WRITE,
    "read": PermissionCategory.READ,
    "glob": PermissionCategory.READ,
    "grep": PermissionCategory.READ,
    "web_fetch": PermissionCategory.WEB,
    "web_search": PermissionCategory.WEB,
}


class PermissionManager:
    """
    Determines whether a tool call should be allowed, denied, or prompted.

    Supports:
    - Per-category auto-allow (read, write, bash, web)
    - Session-level "always allow" for a category
    - Bash command glob patterns (e.g. "git *")
    """

    def __init__(
        self,
        auto_allow_reads: bool = True,
        auto_allow_writes: bool = False,
        auto_allow_bash: bool = False,
        bash_patterns: list[str] | None = None,
    ) -> None:
        self._auto_allow_reads = auto_allow_reads
        self._always_allow_categories: set[PermissionCategory] = set()
        self._bash_patterns: list[str] = list(bash_patterns or [])

        if auto_allow_writes:
            self._always_allow_categories.add(PermissionCategory.WRITE)
        if auto_allow_bash:
            self._always_allow_categories.add(PermissionCategory.BASH)

    def get_category(self, tool_name: str) -> PermissionCategory:
        return _TOOL_CATEGORIES.get(tool_name, PermissionCategory.OTHER)

    def check(self, tool_call: ToolCall, tool_def: ToolDefinition) -> PermissionDecision:
        category = self.get_category(tool_call.name)

        # Read-only tools
        if tool_def.is_read_only and not tool_def.requires_permission:
            return PermissionDecision.ALLOW
        if self._auto_allow_reads and category == PermissionCategory.READ:
            return PermissionDecision.ALLOW

        # Always-allow categories (set via config or session)
        if category in self._always_allow_categories:
            return PermissionDecision.ALLOW

        # Bash command pattern matching
        if category == PermissionCategory.BASH:
            command = tool_call.arguments.get("command", "")
            for pattern in self._bash_patterns:
                if fnmatch.fnmatch(command, pattern):
                    return PermissionDecision.ALLOW

        return PermissionDecision.PROMPT

    def always_allow_category(self, category: PermissionCategory) -> None:
        """Allow all tools in this category for the rest of the session."""
        self._always_allow_categories.add(category)

    def add_bash_pattern(self, pattern: str) -> None:
        """Allow any bash command matching this glob pattern."""
        self._bash_patterns.append(pattern)

    @property
    def bash_patterns(self) -> list[str]:
        return list(self._bash_patterns)
