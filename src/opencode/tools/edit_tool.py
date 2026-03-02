"""File editing tool using find-and-replace."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from opencode.tools.base import Tool, ToolDefinition, ToolParameter, ToolResult


class EditTool(Tool):
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="edit",
            description=(
                "Edit a file by replacing an exact string with a new string. "
                "The old_string must match exactly (including whitespace and indentation). "
                "If old_string appears multiple times, set replace_all=true to replace all occurrences, "
                "otherwise the edit will fail if the match is not unique."
            ),
            parameters=[
                ToolParameter(
                    name="file_path",
                    type="string",
                    description="Path to the file to edit",
                ),
                ToolParameter(
                    name="old_string",
                    type="string",
                    description="The exact string to find and replace",
                ),
                ToolParameter(
                    name="new_string",
                    type="string",
                    description="The replacement string",
                ),
                ToolParameter(
                    name="replace_all",
                    type="boolean",
                    description="Replace all occurrences (default false)",
                    required=False,
                    default=False,
                ),
            ],
            is_read_only=False,
            requires_permission=True,
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        file_path = kwargs["file_path"]
        old_string: str = kwargs["old_string"]
        new_string: str = kwargs["new_string"]
        replace_all: bool = kwargs.get("replace_all", False)

        path = Path(file_path).expanduser()
        if not path.exists():
            return ToolResult(content=f"File not found: {file_path}", is_error=True)

        try:
            content = path.read_text()
        except PermissionError:
            return ToolResult(content=f"Permission denied: {file_path}", is_error=True)

        count = content.count(old_string)
        if count == 0:
            return ToolResult(
                content=f"old_string not found in {file_path}. Make sure it matches exactly.",
                is_error=True,
            )

        if count > 1 and not replace_all:
            return ToolResult(
                content=(
                    f"old_string found {count} times in {file_path}. "
                    "Provide more context to make it unique, or set replace_all=true."
                ),
                is_error=True,
            )

        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)

        try:
            path.write_text(new_content)
            replacements = count if replace_all else 1
            return ToolResult(
                content=f"Replaced {replacements} occurrence(s) in {file_path}"
            )
        except Exception as e:
            return ToolResult(content=f"Error writing file: {e}", is_error=True)
