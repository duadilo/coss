"""Plan mode — restricts the agent to read-only tools."""

from __future__ import annotations


class PlanMode:
    """
    When active, the agent is restricted to read-only tools only.
    Write, Edit, and Bash tools are filtered from the available tool list.
    The system prompt is augmented with plan-mode instructions.

    Toggle via /plan slash command or --plan CLI flag.
    """

    def __init__(self) -> None:
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    def activate(self) -> None:
        self._active = True

    def deactivate(self) -> None:
        self._active = False

    def toggle(self) -> bool:
        """Toggle plan mode. Returns the new state."""
        self._active = not self._active
        return self._active

    def get_system_prompt_addendum(self) -> str:
        if not self._active:
            return ""
        return (
            "\n=== PLAN MODE ACTIVE ===\n"
            "You are in read-only planning mode. You may ONLY use read-only "
            "tools (glob, grep, read). You MUST NOT modify any files or run "
            "commands that change state.\n\n"
            "Your job is to:\n"
            "1. Explore the codebase to understand the relevant code\n"
            "2. Design an implementation approach\n"
            "3. Present a clear, step-by-step plan to the user\n"
            "4. Wait for the user to approve before making changes\n\n"
            "When the user is ready to execute, they will exit plan mode with /plan."
        )
