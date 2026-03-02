"""Streaming markdown renderer using Rich."""

from __future__ import annotations

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.text import Text

from opencode.core.message import ToolCall, ToolResult
from opencode.providers.base import StreamChunk
from opencode.tools.base import ToolDefinition


class StreamRenderer:
    """
    Renders streaming LLM output using Rich Live + Markdown.
    Accumulates text chunks and re-renders the full Markdown
    on each update for correct formatting.
    """

    def __init__(self, console: Console) -> None:
        self._console = console
        self._accumulated_text = ""
        self._live: Live | None = None

    def on_chunk(self, chunk: StreamChunk) -> None:
        if chunk.text:
            self._accumulated_text += chunk.text
            if self._live is None:
                self._live = Live(
                    Markdown(self._accumulated_text),
                    console=self._console,
                    refresh_per_second=8,
                    auto_refresh=True,
                )
                self._live.start()
            else:
                self._live.update(Markdown(self._accumulated_text))

    def on_tool_start(self, tool_call: ToolCall, tool_def: ToolDefinition | None) -> None:
        """Stop live display, show tool execution indicator."""
        self._stop_live()
        label = tool_call.name
        args_preview = ""
        if tool_call.name == "bash" and "command" in tool_call.arguments:
            args_preview = f" `{tool_call.arguments['command'][:80]}`"
        elif tool_call.name == "read" and "file_path" in tool_call.arguments:
            args_preview = f" {tool_call.arguments['file_path']}"
        elif tool_call.name == "write" and "file_path" in tool_call.arguments:
            args_preview = f" {tool_call.arguments['file_path']}"
        elif tool_call.name == "edit" and "file_path" in tool_call.arguments:
            args_preview = f" {tool_call.arguments['file_path']}"
        elif tool_call.name == "glob" and "pattern" in tool_call.arguments:
            args_preview = f" {tool_call.arguments['pattern']}"
        elif tool_call.name == "grep" and "pattern" in tool_call.arguments:
            args_preview = f" /{tool_call.arguments['pattern']}/"

        self._console.print(
            Text(f"  > {label}{args_preview} ...", style="dim"),
            highlight=False,
        )

    def on_tool_end(self, tool_call: ToolCall, result: ToolResult) -> None:
        status = "[green]done[/green]" if not result.is_error else "[red]error[/red]"
        self._console.print(f"  > {tool_call.name} {status}")

    def finalize(self) -> None:
        """End the current streaming display."""
        self._stop_live()
        self._accumulated_text = ""

    def _stop_live(self) -> None:
        if self._live:
            self._live.stop()
            self._live = None
