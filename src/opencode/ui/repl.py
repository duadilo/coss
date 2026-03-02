"""Interactive REPL using prompt_toolkit."""

from __future__ import annotations

import os
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.markdown import Markdown

from opencode import __version__
from opencode.core.agent import AgentLoop
from opencode.core.message import ToolCall, ToolResult
from opencode.core.permissions import PermissionManager
from opencode.providers.base import StreamChunk
from opencode.tools.base import ToolDefinition
from opencode.ui.renderer import StreamRenderer
from opencode.ui.slash_commands import SlashCommandRegistry


class REPL:
    """Main interactive REPL loop."""

    def __init__(
        self,
        agent_loop: AgentLoop,
        renderer: StreamRenderer,
        slash_commands: SlashCommandRegistry,
        permission_manager: PermissionManager,
        console: Console,
    ) -> None:
        self._agent = agent_loop
        self._renderer = renderer
        self._slash = slash_commands
        self._permission_manager = permission_manager
        self._console = console

        # Set up history file
        history_dir = Path.home() / ".opencode"
        history_dir.mkdir(exist_ok=True)
        self._session: PromptSession[str] = PromptSession(
            history=FileHistory(str(history_dir / "history")),
        )

    def _print_welcome(self) -> None:
        self._console.print(f"\n[bold cyan]opencode[/bold cyan] v{__version__}")
        self._console.print(f"[dim]Model: {self._agent.provider.model}[/dim]")
        self._console.print(f"[dim]Working directory: {os.getcwd()}[/dim]")
        self._console.print("[dim]Type /help for commands, /exit to quit.[/dim]\n")

    def _handle_permission_request(
        self, tool_call: ToolCall, tool_def: ToolDefinition | None
    ) -> bool:
        """Prompt user to allow/deny a tool call."""
        self._console.print()
        self._console.print(f"[yellow]Tool call: {tool_call.name}[/yellow]")

        # Show relevant arguments
        for key, value in tool_call.arguments.items():
            display_val = str(value)
            if len(display_val) > 200:
                display_val = display_val[:200] + "..."
            self._console.print(f"  [dim]{key}:[/dim] {display_val}")

        try:
            response = self._session.prompt(
                HTML("<b>Allow?</b> [<green>y</green>]es / [<red>n</red>]o / [<cyan>a</cyan>]lways: "),
            )
        except (EOFError, KeyboardInterrupt):
            return False

        response = response.strip().lower()
        if response in ("y", "yes", ""):
            return True
        elif response in ("a", "always"):
            self._permission_manager.set_always_allow(tool_call.name)
            self._console.print(f"[dim]Always allowing '{tool_call.name}' for this session.[/dim]")
            return True
        else:
            return False

    async def run(self) -> None:
        """Main REPL loop."""
        self._print_welcome()

        while True:
            try:
                user_input = self._session.prompt(
                    HTML("<b><cyan>you></cyan></b> "),
                )

                if not user_input.strip():
                    continue

                # Handle slash commands
                if user_input.strip().startswith("/"):
                    await self._slash.dispatch(user_input.strip())
                    continue

                # Run agent loop
                self._console.print()
                await self._agent.run(
                    user_input,
                    on_stream_chunk=self._renderer.on_chunk,
                    on_tool_start=self._renderer.on_tool_start,
                    on_tool_end=self._renderer.on_tool_end,
                    on_permission_request=self._handle_permission_request,
                )
                self._renderer.finalize()
                self._console.print()

            except KeyboardInterrupt:
                self._renderer.finalize()
                self._console.print("\n[dim]Interrupted. Type /exit to quit.[/dim]")
            except EOFError:
                break
            except SystemExit:
                break
