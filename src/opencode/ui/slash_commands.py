"""Slash command registry and built-in commands."""

from __future__ import annotations

from typing import Any, Callable, Awaitable, TYPE_CHECKING

from rich.console import Console
from rich.table import Table

from opencode.core.conversation import Conversation
from opencode.core.cost import CostTracker

if TYPE_CHECKING:
    from opencode.core.agent import AgentLoop
    from opencode.core.context import ContextManager
    from opencode.core.plan_mode import PlanMode
    from opencode.config.settings import Settings
    from opencode.memory.store import MemoryStore


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
        agent: AgentLoop | None = None,
        settings: Settings | None = None,
        plan_mode: PlanMode | None = None,
        context_manager: ContextManager | None = None,
        memory_store: MemoryStore | None = None,
    ) -> None:
        self._console = console
        self._conversation = conversation
        self._cost_tracker = cost_tracker
        self._agent = agent
        self._settings = settings
        self._plan_mode = plan_mode
        self._context_manager = context_manager
        self._memory_store = memory_store
        self._commands: dict[str, SlashCommand] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        self.register(SlashCommand("help", "Show available commands", self._cmd_help))
        self.register(SlashCommand("clear", "Clear conversation history", self._cmd_clear))
        self.register(SlashCommand("cost", "Show token usage", self._cmd_cost))
        self.register(SlashCommand("usage", "Show context window usage", self._cmd_usage))
        self.register(SlashCommand("model", "Show/switch model (e.g. /model anthropic:claude-sonnet-4-20250514)", self._cmd_model))
        self.register(SlashCommand("config", "Show current configuration", self._cmd_config))
        self.register(SlashCommand("plan", "Toggle plan mode (read-only exploration)", self._cmd_plan))
        self.register(SlashCommand("compact", "Compress conversation history", self._cmd_compact))
        self.register(SlashCommand("memory", "Show memory file paths and contents", self._cmd_memory))
        self.register(SlashCommand("exit", "Exit opencode", self._cmd_exit))
        self.register(SlashCommand("quit", "Exit opencode", self._cmd_exit))

    def register(self, cmd: SlashCommand) -> None:
        self._commands[cmd.name] = cmd

    async def dispatch(self, raw_input: str) -> str | None:
        """Dispatch a slash command. Returns a string to send to the agent, or None."""
        parts = raw_input.strip().lstrip("/").split(maxsplit=1)
        if not parts:
            return None

        name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        cmd = self._commands.get(name)
        if cmd is None:
            self._console.print(f"[red]Unknown command: /{name}[/red]. Type /help for help.")
            return None

        result = cmd.handler(args)
        if result is not None and hasattr(result, "__await__"):
            result = await result
        return result if isinstance(result, str) else None

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

    def _cmd_usage(self, _args: str = "") -> None:
        used = self._conversation.token_estimate()
        max_tokens = self._settings.provider.max_context_tokens if self._settings else 128_000
        pct = used / max_tokens if max_tokens else 0
        filled = int(pct * 30)
        empty = 30 - filled

        if pct < 0.6:
            bar_color = "green"
        elif pct < 0.85:
            bar_color = "yellow"
        else:
            bar_color = "red"

        bar = f"[{bar_color}]{'█' * filled}[/{bar_color}][dim]{'░' * empty}[/dim]"
        self._console.print(
            f"\nContext: {bar} [bold]{pct:.0%}[/bold]  "
            f"[dim]~{used:,} / {max_tokens:,} tokens[/dim]\n"
        )

    def _cmd_model(self, args: str = "") -> None:
        if not args.strip():
            if self._agent:
                self._console.print(
                    f"[dim]Current model: [cyan]{self._agent.provider.name}[/cyan]:"
                    f"[bold]{self._agent.provider.model}[/bold][/dim]"
                )
            self._console.print("\n[dim]Usage: /model <provider:model>[/dim]")
            self._console.print("[dim]Examples: /model anthropic:claude-sonnet-4-20250514, /model ollama:llama3.1[/dim]")
            return

        from opencode.providers.registry import ProviderRegistry

        model_string = args.strip()
        try:
            api_key = self._settings.provider.api_key if self._settings else None
            base_url = self._settings.provider.base_url if self._settings else None
            new_provider = ProviderRegistry.create(
                model_string, api_key=api_key, base_url=base_url
            )
            if self._agent:
                self._agent.provider = new_provider
            self._console.print(
                f"[green]Switched to {new_provider.name}:{new_provider.model}[/green]"
            )
        except Exception as e:
            self._console.print(f"[red]Failed to switch model: {e}[/red]")

    def _cmd_config(self, _args: str = "") -> None:
        if not self._settings:
            self._console.print("[dim]No config loaded.[/dim]")
            return

        table = Table(title="Configuration", show_header=True, header_style="bold")
        table.add_column("Setting", style="cyan")
        table.add_column("Value")

        s = self._settings
        table.add_row("provider.model", s.provider.model)
        table.add_row("provider.base_url", s.provider.base_url or "(default)")
        table.add_row("provider.api_key", "***" if s.provider.api_key else "(not set)")
        table.add_row("provider.max_tokens", str(s.provider.max_tokens))
        table.add_row("provider.temperature", str(s.provider.temperature))
        if s.provider.extra_params:
            for k, v in s.provider.extra_params.items():
                table.add_row(f"provider.extra_params.{k}", str(v))
        table.add_row("permissions.auto_allow_read", str(s.permissions.auto_allow_read_tools))
        table.add_row("permissions.auto_allow_write", str(s.permissions.auto_allow_write_tools))
        table.add_row("permissions.auto_allow_bash", str(s.permissions.auto_allow_bash))
        table.add_row("provider.max_context_tokens", str(s.provider.max_context_tokens))
        if s.mcp_servers:
            table.add_row("mcp_servers", ", ".join(s.mcp_servers.keys()))
        if s.hooks:
            table.add_row("hooks", str(len(s.hooks)))

        self._console.print(table)

    def _cmd_plan(self, _args: str = "") -> None:
        if not self._plan_mode:
            self._console.print("[dim]Plan mode not available.[/dim]")
            return

        new_state = self._plan_mode.toggle()
        if new_state:
            self._console.print(
                "[yellow]Plan mode ON[/yellow] — read-only tools only. "
                "Use /plan again to switch back to execute mode."
            )
        else:
            self._console.print(
                "[green]Plan mode OFF[/green] — all tools available."
            )

    async def _cmd_compact(self, _args: str = "") -> None:
        if not self._context_manager or not self._agent:
            self._console.print("[dim]Context management not available.[/dim]")
            return

        est_tokens = self._conversation.token_estimate()
        self._console.print(f"[dim]Estimated tokens: ~{est_tokens:,}[/dim]")
        self._console.print("[dim]Compacting conversation...[/dim]")

        summary = await self._context_manager.compact(
            self._conversation, self._agent.provider
        )
        if summary:
            new_tokens = self._conversation.token_estimate()
            self._console.print(
                f"[green]Compacted.[/green] [dim]~{est_tokens:,} → ~{new_tokens:,} tokens[/dim]"
            )
        else:
            self._console.print("[dim]Nothing to compact (conversation too short).[/dim]")

    def _cmd_memory(self, _args: str = "") -> None:
        if not self._memory_store:
            self._console.print("[dim]Memory store not available.[/dim]")
            return

        self._console.print("\n[bold]Memory files:[/bold]")
        self._console.print(f"  [cyan]Global:[/cyan]  {self._memory_store.global_path}")
        if self._memory_store.project_path:
            self._console.print(f"  [cyan]Project:[/cyan] {self._memory_store.project_path}")

        global_mem = self._memory_store.read_global()
        if global_mem:
            self._console.print(f"\n[bold]Global memory[/bold] ({len(global_mem)} chars):")
            preview = global_mem[:500]
            if len(global_mem) > 500:
                preview += "..."
            self._console.print(f"[dim]{preview}[/dim]")
        else:
            self._console.print("\n[dim]No global memory file found.[/dim]")

        project_mem = self._memory_store.read_project()
        if project_mem:
            self._console.print(f"\n[bold]Project memory[/bold] ({len(project_mem)} chars):")
            preview = project_mem[:500]
            if len(project_mem) > 500:
                preview += "..."
            self._console.print(f"[dim]{preview}[/dim]")
        else:
            self._console.print("[dim]No project memory file found.[/dim]")
        self._console.print()

    def _cmd_exit(self, _args: str = "") -> None:
        raise SystemExit(0)
