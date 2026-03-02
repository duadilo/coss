"""Bash command execution tool."""

from __future__ import annotations

import asyncio
from typing import Any

from opencode.tools.base import Tool, ToolDefinition, ToolParameter, ToolResult


class BashTool(Tool):
    def __init__(self, working_directory: str, timeout_default: int = 120) -> None:
        self._cwd = working_directory
        self._timeout = timeout_default

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="bash",
            description=(
                "Execute a bash command and return its stdout and stderr. "
                "Use this for running shell commands, installing packages, "
                "running tests, git operations, etc."
            ),
            parameters=[
                ToolParameter(
                    name="command",
                    type="string",
                    description="The bash command to execute",
                ),
                ToolParameter(
                    name="timeout",
                    type="integer",
                    description="Timeout in seconds (default 120)",
                    required=False,
                    default=120,
                ),
            ],
            is_read_only=False,
            requires_permission=True,
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        command: str = kwargs["command"]
        timeout: int = kwargs.get("timeout", self._timeout)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._cwd,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            output_parts: list[str] = []
            if stdout:
                output_parts.append(stdout.decode(errors="replace"))
            if stderr:
                output_parts.append(stderr.decode(errors="replace"))

            output = "\n".join(output_parts) if output_parts else "(no output)"
            # Truncate very long output
            if len(output) > 100_000:
                output = output[:100_000] + "\n... (output truncated)"

            return ToolResult(
                content=output,
                is_error=proc.returncode != 0,
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()  # type: ignore[possibly-undefined]
            except ProcessLookupError:
                pass
            return ToolResult(content=f"Command timed out after {timeout}s", is_error=True)
        except Exception as e:
            return ToolResult(content=f"Error executing command: {e}", is_error=True)
