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
from opencode.core.agent import AgentAbortError, AgentLoop
from opencode.core.message import ToolCall, ToolResult
from opencode.core.permissions import PermissionCategory, PermissionManager
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

    async def _handle_permission_request(
        self, tool_call: ToolCall, tool_def: ToolDefinition | None
    ) -> bool:
        """Prompt user to allow/deny a tool call."""
        # Stop any active live display before prompting — live + prompt_toolkit conflict
        self._renderer._stop_live()

        category = self._permission_manager.get_category(tool_call.name)
        self._console.print()

        if category == PermissionCategory.BASH:
            command = tool_call.arguments.get("command", "")
            self._console.print(f"[yellow bold]bash[/yellow bold] [dim]{command}[/dim]")
            prompt = HTML(
                "<b>Run?</b> "
                "[<green>c</green>]ontinue / [<yellow>s</yellow>]kip / [<red>a</red>]bort"
                " · [<cyan>!</cyan>] always allow bash"
                " · [<cyan>p</cyan>]attern: "
            )
        elif category == PermissionCategory.WRITE:
            path = tool_call.arguments.get("file_path", "")
            self._console.print(f"[yellow bold]{tool_call.name}[/yellow bold] [dim]{path}[/dim]")
            prompt = HTML(
                "<b>Allow?</b> "
                "[<green>c</green>]ontinue / [<yellow>s</yellow>]kip / [<red>a</red>]bort"
                " · [<cyan>!</cyan>] always allow edits: "
            )
        elif category == PermissionCategory.WEB:
            target = tool_call.arguments.get("url") or tool_call.arguments.get("query", "")
            self._console.print(f"[yellow bold]{tool_call.name}[/yellow bold] [dim]{target}[/dim]")
            prompt = HTML(
                "<b>Allow?</b> "
                "[<green>c</green>]ontinue / [<yellow>s</yellow>]kip / [<red>a</red>]bort"
                " · [<cyan>!</cyan>] always allow web: "
            )
        else:
            self._console.print(f"[yellow bold]{tool_call.name}[/yellow bold]")
            for key, value in tool_call.arguments.items():
                display_val = str(value)
                if len(display_val) > 200:
                    display_val = display_val[:200] + "..."
                self._console.print(f"  [dim]{key}:[/dim] {display_val}")
            prompt = HTML(
                "<b>Allow?</b> "
                "[<green>c</green>]ontinue / [<yellow>s</yellow>]kip / [<red>a</red>]bort"
                " · [<cyan>!</cyan>] always allow: "
            )

        try:
            response = await self._session.prompt_async(prompt)
        except (EOFError, KeyboardInterrupt):
            raise AgentAbortError()

        response = response.strip().lower()

        if response in ("c", "continue", ""):
            return True

        elif response == "a" or response == "abort":
            raise AgentAbortError()

        elif response == "!" :
            self._permission_manager.always_allow_category(category)
            label = {
                PermissionCategory.BASH: "all bash commands",
                PermissionCategory.WRITE: "all file edits/writes",
                PermissionCategory.WEB: "all web requests",
            }.get(category, f"all '{tool_call.name}' calls")
            self._console.print(f"[dim]Allowing {label} for this session.[/dim]")
            return True

        elif response in ("p", "pattern") and category == PermissionCategory.BASH:
            try:
                pattern = await self._session.prompt_async(
                    HTML("Pattern (e.g. <i>git *</i>): ")
                )
            except (EOFError, KeyboardInterrupt):
                raise AgentAbortError()
            pattern = pattern.strip()
            if pattern:
                self._permission_manager.add_bash_pattern(pattern)
                self._console.print(f"[dim]Allowing bash commands matching '{pattern}'.[/dim]")
                return True
            return False

        # "s", "skip", or anything else → deny this call, agent continues
        return False

    async def run(self) -> None:
        """Main REPL loop."""
        self._print_welcome()

        while True:
            try:
                user_input = await self._session.prompt_async(
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

            except AgentAbortError:
                self._renderer.finalize()
                self._console.print("\n[dim]Aborted.[/dim]")
            except KeyboardInterrupt:
                self._renderer.finalize()
                self._console.print("\n[dim]Interrupted. Type /exit to quit.[/dim]")
            except EOFError:
                break
            except SystemExit:
                break
