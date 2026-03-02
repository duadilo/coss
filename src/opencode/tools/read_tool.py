"""File reading tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from opencode.tools.base import Tool, ToolDefinition, ToolParameter, ToolResult


class ReadTool(Tool):
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="read",
            description=(
                "Read the contents of a file. Returns the file content with line numbers. "
                "You can optionally specify offset and limit to read a portion of the file."
            ),
            parameters=[
                ToolParameter(
                    name="file_path",
                    type="string",
                    description="Absolute or relative path to the file to read",
                ),
                ToolParameter(
                    name="offset",
                    type="integer",
                    description="Line number to start reading from (1-based)",
                    required=False,
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of lines to read",
                    required=False,
                ),
            ],
            is_read_only=True,
            requires_permission=False,
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        file_path = kwargs["file_path"]
        offset: int | None = kwargs.get("offset")
        limit: int | None = kwargs.get("limit")

        path = Path(file_path).expanduser()
        if not path.exists():
            return ToolResult(content=f"File not found: {file_path}", is_error=True)
        if not path.is_file():
            return ToolResult(content=f"Not a file: {file_path}", is_error=True)

        try:
            text = path.read_text(errors="replace")
        except PermissionError:
            return ToolResult(content=f"Permission denied: {file_path}", is_error=True)

        lines = text.splitlines()

        start = (offset - 1) if offset and offset > 0 else 0
        end = (start + limit) if limit else len(lines)
        selected = lines[start:end]

        # Format with line numbers
        numbered = []
        for i, line in enumerate(selected, start=start + 1):
            # Truncate very long lines
            if len(line) > 2000:
                line = line[:2000] + "..."
            numbered.append(f"{i:>6}\t{line}")

        if not numbered:
            return ToolResult(content="(empty file)")

        return ToolResult(content="\n".join(numbered))
