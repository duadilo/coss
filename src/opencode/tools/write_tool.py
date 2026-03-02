"""File writing tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from opencode.tools.base import Tool, ToolDefinition, ToolParameter, ToolResult


class WriteTool(Tool):
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="write",
            description=(
                "Write content to a file. Creates the file and any parent directories "
                "if they don't exist. Overwrites the file if it already exists."
            ),
            parameters=[
                ToolParameter(
                    name="file_path",
                    type="string",
                    description="Absolute or relative path to the file to write",
                ),
                ToolParameter(
                    name="content",
                    type="string",
                    description="The content to write to the file",
                ),
            ],
            is_read_only=False,
            requires_permission=True,
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        file_path = kwargs["file_path"]
        content: str = kwargs["content"]

        path = Path(file_path).expanduser()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            return ToolResult(content=f"Successfully wrote {len(content)} bytes to {file_path}")
        except PermissionError:
            return ToolResult(content=f"Permission denied: {file_path}", is_error=True)
        except Exception as e:
            return ToolResult(content=f"Error writing file: {e}", is_error=True)
