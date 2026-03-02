"""Content search tool using ripgrep or Python fallback."""

from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path
from typing import Any

from opencode.tools.base import Tool, ToolDefinition, ToolParameter, ToolResult

_RG_PATH: str | None = shutil.which("rg")


class GrepTool(Tool):
    def __init__(self, working_directory: str) -> None:
        self._cwd = working_directory

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="grep",
            description=(
                "Search file contents using a regex pattern. Uses ripgrep if available, "
                "otherwise falls back to Python regex. Returns matching lines with file paths "
                "and line numbers."
            ),
            parameters=[
                ToolParameter(
                    name="pattern",
                    type="string",
                    description="Regex pattern to search for",
                ),
                ToolParameter(
                    name="path",
                    type="string",
                    description="File or directory to search in (defaults to working directory)",
                    required=False,
                ),
                ToolParameter(
                    name="glob",
                    type="string",
                    description="Glob pattern to filter files (e.g. '*.py', '*.ts')",
                    required=False,
                ),
                ToolParameter(
                    name="case_insensitive",
                    type="boolean",
                    description="Case insensitive search (default false)",
                    required=False,
                    default=False,
                ),
            ],
            is_read_only=True,
            requires_permission=False,
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        pattern: str = kwargs["pattern"]
        search_path = kwargs.get("path", self._cwd)
        file_glob: str | None = kwargs.get("glob")
        case_insensitive: bool = kwargs.get("case_insensitive", False)

        if _RG_PATH:
            return await self._search_rg(pattern, search_path, file_glob, case_insensitive)
        return await self._search_python(pattern, search_path, file_glob, case_insensitive)

    async def _search_rg(
        self, pattern: str, path: str, file_glob: str | None, case_insensitive: bool
    ) -> ToolResult:
        cmd = [_RG_PATH, "--no-heading", "--line-number", "--color=never", "-m", "200"]  # type: ignore
        if case_insensitive:
            cmd.append("-i")
        if file_glob:
            cmd.extend(["--glob", file_glob])
        cmd.append(pattern)
        cmd.append(path)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._cwd,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            output = stdout.decode(errors="replace")

            if proc.returncode == 1:
                return ToolResult(content="No matches found.")
            if proc.returncode and proc.returncode > 1:
                return ToolResult(content=f"ripgrep error: {stderr.decode()}", is_error=True)

            # Truncate
            if len(output) > 100_000:
                output = output[:100_000] + "\n... (output truncated)"
            return ToolResult(content=output if output.strip() else "No matches found.")
        except asyncio.TimeoutError:
            return ToolResult(content="Search timed out after 30s", is_error=True)

    async def _search_python(
        self, pattern: str, path: str, file_glob: str | None, case_insensitive: bool
    ) -> ToolResult:
        """Fallback search using Python regex."""
        flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return ToolResult(content=f"Invalid regex: {e}", is_error=True)

        search_dir = Path(path).expanduser()
        if search_dir.is_file():
            files = [search_dir]
        else:
            glob_pattern = file_glob or "**/*"
            files = [f for f in search_dir.glob(glob_pattern) if f.is_file()]

        results: list[str] = []
        for file in files[:1000]:  # limit files scanned
            try:
                content = file.read_text(errors="replace")
            except (PermissionError, OSError):
                continue
            for i, line in enumerate(content.splitlines(), 1):
                if regex.search(line):
                    results.append(f"{file}:{i}:{line}")
                    if len(results) >= 200:
                        break
            if len(results) >= 200:
                break

        if not results:
            return ToolResult(content="No matches found.")

        output = "\n".join(results)
        if len(results) == 200:
            output += "\n... (results limited to 200 matches)"
        return ToolResult(content=output)
