"""Pre/post tool-call hook execution."""

from __future__ import annotations

import asyncio
import fnmatch
from typing import Any

from opencode.config.settings import HookEntry
from opencode.core.message import ToolCall


class HookResult:
    """Result of a hook execution."""

    def __init__(self, hook: HookEntry, output: str, returncode: int) -> None:
        self.hook = hook
        self.output = output
        self.returncode = returncode

    @property
    def success(self) -> bool:
        return self.returncode == 0


class HookManager:
    """
    Manages pre/post tool-call shell command hooks.

    Hooks are configured in settings and match tool names via glob patterns.
    Pre-hooks can block tool execution if they return non-zero exit code.
    """

    def __init__(self, hooks: list[HookEntry] | None = None) -> None:
        self._hooks = hooks or []

    async def run_pre_hooks(self, tool_call: ToolCall) -> list[HookResult]:
        """Run pre-tool-call hooks. Returns results for all matching hooks."""
        matching = self._find_matching("pre_tool_call", tool_call.name)
        return await self._run_hooks(matching, tool_call)

    async def run_post_hooks(self, tool_call: ToolCall) -> list[HookResult]:
        """Run post-tool-call hooks."""
        matching = self._find_matching("post_tool_call", tool_call.name)
        return await self._run_hooks(matching, tool_call)

    def has_blocking_failure(self, results: list[HookResult]) -> str | None:
        """Check if any pre-hook failed. Returns error message or None."""
        for result in results:
            if not result.success:
                return (
                    f"Pre-hook blocked execution: `{result.hook.command}` "
                    f"exited with code {result.returncode}\n{result.output}"
                )
        return None

    def _find_matching(self, event: str, tool_name: str) -> list[HookEntry]:
        return [
            h
            for h in self._hooks
            if h.event == event and fnmatch.fnmatch(tool_name, h.tool_pattern)
        ]

    async def _run_hooks(
        self, hooks: list[HookEntry], tool_call: ToolCall
    ) -> list[HookResult]:
        results: list[HookResult] = []
        for hook in hooks:
            # Set environment variables for the hook
            env_vars = {
                "OPENCODE_TOOL_NAME": tool_call.name,
                "OPENCODE_TOOL_CALL_ID": tool_call.id,
            }
            # Add tool arguments as env vars
            for key, value in tool_call.arguments.items():
                env_key = f"OPENCODE_TOOL_ARG_{key.upper()}"
                env_vars[env_key] = str(value)[:4096]

            try:
                import os

                env = {**os.environ, **env_vars}
                proc = await asyncio.create_subprocess_shell(
                    hook.command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
                output = (stdout.decode(errors="replace") + stderr.decode(errors="replace")).strip()
                results.append(HookResult(hook, output, proc.returncode or 0))
            except asyncio.TimeoutError:
                results.append(HookResult(hook, "Hook timed out after 30s", 1))
            except Exception as e:
                results.append(HookResult(hook, f"Hook error: {e}", 1))

        return results
