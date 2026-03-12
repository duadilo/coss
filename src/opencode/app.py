"""Application orchestrator — wires all components together."""

from __future__ import annotations

import logging
import os
from typing import Any

from rich.console import Console
from rich.markdown import Markdown

from opencode.config.loader import ConfigLoader
from opencode.config.settings import Settings
from opencode.core.agent import AgentLoop
from opencode.core.context import ContextManager
from opencode.core.conversation import Conversation
from opencode.core.cost import CostTracker
from opencode.core.permissions import PermissionManager
from opencode.core.plan_mode import PlanMode
from opencode.hooks.manager import HookManager
from opencode.memory.store import MemoryStore
from opencode.memory.system_prompt import SystemPromptBuilder
from opencode.providers.base import LLMProvider
from opencode.providers.registry import ProviderRegistry
from opencode.tools.agent_tool import AgentTool
from opencode.tools.bash_tool import BashTool
from opencode.tools.edit_tool import EditTool
from opencode.tools.glob_tool import GlobTool
from opencode.tools.grep_tool import GrepTool
from opencode.tools.read_tool import ReadTool
from opencode.tools.registry import ToolRegistry
from opencode.tools.web_fetch_tool import WebFetchTool
from opencode.tools.web_search_tool import WebSearchTool
from opencode.tools.write_tool import WriteTool
from opencode.ui.renderer import StreamRenderer
from opencode.ui.repl import REPL
from opencode.ui.slash_commands import SlashCommandRegistry

logger = logging.getLogger(__name__)


class Application:
    """Top-level application. Creates and wires all components."""

    def __init__(
        self,
        repl: REPL,
        agent: AgentLoop,
        settings: Settings,
        console: Console,
        mcp_manager: Any | None = None,
    ) -> None:
        self.repl = repl
        self.agent = agent
        self.settings = settings
        self.console = console
        self._mcp_manager = mcp_manager

    @classmethod
    def create(
        cls,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        plan: bool = False,
        extra_params: dict[str, Any] | None = None,
    ) -> Application:
        cwd = os.getcwd()

        # Load config
        cli_overrides: dict[str, Any] = {}
        provider_overrides: dict[str, Any] = {}
        if model:
            provider_overrides["model"] = model
        if base_url:
            provider_overrides["base_url"] = base_url
        if api_key:
            provider_overrides["api_key"] = api_key
        if extra_params:
            provider_overrides["extra_params"] = extra_params
        if provider_overrides:
            cli_overrides["provider"] = provider_overrides

        settings = ConfigLoader().load(cli_overrides)

        # Provider
        provider = ProviderRegistry.create(
            settings.provider.model,
            api_key=settings.provider.api_key,
            base_url=settings.provider.base_url,
            extra_params=settings.provider.extra_params,
        )

        # Tools
        tool_registry = ToolRegistry()
        tool_registry.register(GlobTool(cwd))
        tool_registry.register(GrepTool(cwd))
        tool_registry.register(ReadTool())
        tool_registry.register(EditTool())
        tool_registry.register(WriteTool())
        tool_registry.register(BashTool(cwd))
        tool_registry.register(WebFetchTool())
        tool_registry.register(WebSearchTool())

        # Core components
        permission_manager = PermissionManager(
            auto_allow_reads=settings.permissions.auto_allow_read_tools,
            auto_allow_writes=settings.permissions.auto_allow_write_tools,
            auto_allow_bash=settings.permissions.auto_allow_bash,
            bash_patterns=settings.permissions.allowed_bash_commands,
        )
        cost_tracker = CostTracker()
        plan_mode = PlanMode()
        if plan:
            plan_mode.activate()

        context_manager = ContextManager(
            max_tokens=settings.provider.max_context_tokens,
            compact_threshold=settings.compact_threshold,
        )

        hook_manager = HookManager(settings.hooks)

        # Memory and system prompt
        memory_store = MemoryStore(project_root=cwd)

        # Build system prompt from memory + tools + plan mode
        system_prompt = SystemPromptBuilder().build(
            memory_store=memory_store,
            plan_mode=plan_mode,
            tools=tool_registry.list_definitions(),
            extra=settings.system_prompt_extra,
        )
        conversation = Conversation(system_prompt=system_prompt)

        # Agent loop
        agent = AgentLoop(
            provider=provider,
            tool_registry=tool_registry,
            permission_manager=permission_manager,
            cost_tracker=cost_tracker,
            conversation=conversation,
            plan_mode=plan_mode,
            context_manager=context_manager,
            hook_manager=hook_manager,
        )

        # Register agent tool (needs reference to provider and registry)
        tool_registry.register(AgentTool(
            provider=provider,
            tool_registry=tool_registry,
            cost_tracker=cost_tracker,
            permission_manager=permission_manager,
            system_prompt=system_prompt,
        ))

        # MCP (connect asynchronously later if configured)
        mcp_manager = None
        if settings.mcp_servers:
            from opencode.mcp.client import MCPClientManager
            mcp_manager = MCPClientManager(tool_registry)

        # UI
        console = Console()
        renderer = StreamRenderer(console)
        slash_commands = SlashCommandRegistry(
            console, conversation, cost_tracker, agent, settings,
            plan_mode=plan_mode,
            context_manager=context_manager,
            memory_store=memory_store,
        )
        repl = REPL(agent, renderer, slash_commands, permission_manager, console)

        return cls(
            repl=repl, agent=agent, settings=settings,
            console=console, mcp_manager=mcp_manager,
        )

    async def _connect_mcp(self) -> None:
        """Connect to configured MCP servers."""
        if self._mcp_manager and self.settings.mcp_servers:
            connected = await self._mcp_manager.connect_all(self.settings.mcp_servers)
            if connected:
                self.console.print(
                    f"[dim]MCP servers connected: {', '.join(connected)}[/dim]"
                )

    async def _disconnect_mcp(self) -> None:
        """Disconnect from all MCP servers."""
        if self._mcp_manager:
            await self._mcp_manager.disconnect_all()

    async def run_interactive(self) -> None:
        """Run the interactive REPL."""
        await self._connect_mcp()
        try:
            await self.repl.run()
        finally:
            await self._disconnect_mcp()

    async def run_once(self, prompt: str) -> None:
        """Run a single prompt non-interactively and exit."""
        await self._connect_mcp()
        try:
            renderer = StreamRenderer(self.console)

            result = await self.agent.run(
                prompt,
                on_stream_chunk=renderer.on_chunk,
                on_tool_start=renderer.on_tool_start,
                on_tool_end=renderer.on_tool_end,
                # Auto-allow all tools in non-interactive mode
                on_permission_request=lambda tc, td: True,
            )
            renderer.finalize()

            # Print cost summary to stderr so stdout stays clean for piping
            import sys
            print(f"\n{self.agent.cost_tracker.summary()}", file=sys.stderr)
        finally:
            await self._disconnect_mcp()
