"""Slash command registry and built-in commands."""

from __future__ import annotations

from typing import Any, Callable, Awaitable

from rich.console import Console

from opencode.core.conversation import Conversation
from opencode.core.cost import CostTracker


class SlashCommand:
    def __init__(
        self,
        name: str,
        description: str,
        handler: Callable[..., Awaitable[None] | None],
    ) -> None:
        self.name = name
        self.description = description
        self.handler = handler


class SlashCommandRegistry:
    """Registry of /commands."""

    def __init__(
        self,
        console: Console,
        conversation: Conversation,
        cost_tracker: CostTracker,
    ) -> None:
        self._console = console
        self._conversation = conversation
        self._cost_tracker = cost_tracker
        self._commands: dict[str, SlashCommand] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        self.register(SlashCommand("help", "Show available commands", self._cmd_help))
        self.register(SlashCommand("clear", "Clear conversation history", self._cmd_clear))
        self.register(SlashCommand("cost", "Show token usage", self._cmd_cost))
        self.register(SlashCommand("exit", "Exit opencode", self._cmd_exit))
        self.register(SlashCommand("quit", "Exit opencode", self._cmd_exit))

    def register(self, cmd: SlashCommand) -> None:
        self._commands[cmd.name] = cmd

    async def dispatch(self, raw_input: str) -> bool:
        """
        Dispatch a slash command. Returns True if handled, False otherwise.
        Raises SystemExit for /exit.
        """
        parts = raw_input.strip().lstrip("/").split(maxsplit=1)
        if not parts:
            return False

        name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        cmd = self._commands.get(name)
        if cmd is None:
            self._console.print(f"[red]Unknown command: /{name}[/red]. Type /help for help.")
            return True

        result = cmd.handler(args)
        if result is not None and hasattr(result, "__await__"):
            await result
        return True

    def _cmd_help(self, _args: str = "") -> None:
        self._console.print("\n[bold]Available commands:[/bold]")
        for name, cmd in sorted(self._commands.items()):
            self._console.print(f"  [cyan]/{name:<10}[/cyan] {cmd.description}")
        self._console.print()

    def _cmd_clear(self, _args: str = "") -> None:
        self._conversation.clear()
        self._console.print("[dim]Conversation cleared.[/dim]")

    def _cmd_cost(self, _args: str = "") -> None:
        self._console.print(f"[dim]{self._cost_tracker.summary()}[/dim]")

    def _cmd_exit(self, _args: str = "") -> None:
        raise SystemExit(0)
