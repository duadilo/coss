"""Dynamic system prompt assembly."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from opencode.memory.store import MemoryStore

if TYPE_CHECKING:
    from opencode.core.plan_mode import PlanMode
    from opencode.tools.base import ToolDefinition


BASE_PROMPT = """\
You are OpenCode, an agentic coding assistant running in the user's terminal.
You help with software engineering tasks: writing code, debugging, explaining \
code, running commands, searching codebases, and more.

You have access to tools for interacting with the local filesystem and running \
commands. Use them to accomplish the user's requests.

Guidelines:
- Read files before modifying them to understand existing code.
- Use the glob and grep tools to search for files and content.
- Use the bash tool for running shell commands (tests, git, builds, etc.).
- Be concise in your responses. Use markdown formatting.
- When editing files, use the edit tool for surgical changes, write tool for \
new files or complete rewrites.
- Always show your work: explain what you're doing and why.
"""


class SystemPromptBuilder:
    """
    Assembles the system prompt from:
    1. Base instructions
    2. Available tools summary
    3. Global memory (OPENCODE.md from home dir)
    4. Project memory (OPENCODE.md from project root)
    5. Plan mode instructions (if active)
    6. Environment context (cwd, platform)
    """

    def build(
        self,
        memory_store: MemoryStore,
        plan_mode: PlanMode | None = None,
        tools: list[ToolDefinition] | None = None,
        extra: str = "",
    ) -> str:
        parts: list[str] = [BASE_PROMPT]

        # Tool summary
        if tools:
            tool_lines = [f"- **{t.name}**: {t.description[:80]}" for t in tools]
            parts.append("## Available Tools\n" + "\n".join(tool_lines))

        # Environment
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        parts.append(f"\nCurrent date and time: {now}")
        parts.append(f"Working directory: {os.getcwd()}")

        # Global memory
        global_mem = memory_store.read_global()
        if global_mem:
            parts.append(
                "\n## Global Memory (from ~/.opencode/OPENCODE.md)\n" + global_mem
            )

        # Project memory
        project_mem = memory_store.read_project()
        if project_mem:
            parts.append(
                f"\n## Project Memory (from {memory_store.project_path})\n" + project_mem
            )

        # Plan mode
        if plan_mode and plan_mode.is_active:
            parts.append(plan_mode.get_system_prompt_addendum())

        # Extra from config
        if extra:
            parts.append("\n" + extra)

        return "\n\n".join(parts)
