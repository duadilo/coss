"""File search tool using glob patterns."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from opencode.tools.base import Tool, ToolDefinition, ToolParameter, ToolResult


class GlobTool(Tool):
    def __init__(self, working_directory: str) -> None:
        self._cwd = working_directory

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="glob",
            description=(
                "Find files matching a glob pattern. Returns matching file paths "
                "sorted by modification time (most recent first). "
                "Examples: '**/*.py', 'src/**/*.ts', '*.json'"
            ),
            parameters=[
                ToolParameter(
                    name="pattern",
                    type="string",
                    description="The glob pattern to match files against",
                ),
                ToolParameter(
                    name="path",
                    type="string",
                    description="Directory to search in (defaults to working directory)",
                    required=False,
                ),
            ],
            is_read_only=True,
            requires_permission=False,
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        pattern: str = kwargs["pattern"]
        search_path = Path(kwargs.get("path", self._cwd)).expanduser()

        if not search_path.is_dir():
            return ToolResult(content=f"Not a directory: {search_path}", is_error=True)

        try:
            matches = sorted(search_path.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        except Exception as e:
            return ToolResult(content=f"Glob error: {e}", is_error=True)

        if not matches:
            return ToolResult(content=f"No files matching '{pattern}' in {search_path}")

        # Limit output
        total = len(matches)
        display = matches[:200]
        lines = [str(p) for p in display]
        if total > 200:
            lines.append(f"... and {total - 200} more files")

        return ToolResult(content="\n".join(lines))
