"""Application orchestrator — wires all components together."""

from __future__ import annotations

import os

from rich.console import Console

from opencode.core.agent import AgentLoop
from opencode.core.conversation import Conversation
from opencode.core.cost import CostTracker
from opencode.core.permissions import PermissionManager
from opencode.providers.openai_compatible import OpenAICompatibleProvider
from opencode.tools.bash_tool import BashTool
from opencode.tools.edit_tool import EditTool
from opencode.tools.glob_tool import GlobTool
from opencode.tools.grep_tool import GrepTool
from opencode.tools.read_tool import ReadTool
from opencode.tools.registry import ToolRegistry
from opencode.tools.write_tool import WriteTool
from opencode.ui.renderer import StreamRenderer
from opencode.ui.repl import REPL
from opencode.ui.slash_commands import SlashCommandRegistry


SYSTEM_PROMPT = """\
You are OpenCode, an agentic coding assistant running in the user's terminal.
You help with software engineering tasks: writing code, debugging, explaining \
code, running commands, searching codebases, and more.

You have access to tools for interacting with the local filesystem and running \
commands. Use them to accomplish the user's requests.

Guidelines:
- Read files before modifying them to understand existing code.
- Use the glob and grep tools to search for files and content.
- Use the bash tool for running shell commands (tests, git, builds, etc.).
- Be concise in your responses. Use markdown formatting.
- When editing files, use the edit tool for surgical changes, write tool for \
new files or complete rewrites.
- Always show your work: explain what you're doing and why.

Working directory: {cwd}
"""


class Application:
    """Top-level application. Creates and wires all components."""

    def __init__(self, repl: REPL) -> None:
        self.repl = repl

    @classmethod
    def create(
        cls,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> Application:
        cwd = os.getcwd()

        # Provider
        provider = OpenAICompatibleProvider(
            model=model or os.environ.get("OPENCODE_MODEL", "default"),
            base_url=base_url or os.environ.get("OPENCODE_BASE_URL", "http://localhost:8080/v1"),
            api_key=api_key or os.environ.get("OPENCODE_API_KEY", "not-needed"),
        )

        # Tools
        tool_registry = ToolRegistry()
        tool_registry.register(GlobTool(cwd))
        tool_registry.register(GrepTool(cwd))
        tool_registry.register(ReadTool())
        tool_registry.register(EditTool())
        tool_registry.register(WriteTool())
        tool_registry.register(BashTool(cwd))

        # Core
        permission_manager = PermissionManager()
        cost_tracker = CostTracker()
        system_prompt = SYSTEM_PROMPT.format(cwd=cwd)
        conversation = Conversation(system_prompt=system_prompt)

        # Agent loop
        agent = AgentLoop(
            provider=provider,
            tool_registry=tool_registry,
            permission_manager=permission_manager,
            cost_tracker=cost_tracker,
            conversation=conversation,
        )

        # UI
        console = Console()
        renderer = StreamRenderer(console)
        slash_commands = SlashCommandRegistry(console, conversation, cost_tracker)
        repl = REPL(agent, renderer, slash_commands, permission_manager, console)

        return cls(repl=repl)

    async def run_interactive(self) -> None:
        await self.repl.run()
