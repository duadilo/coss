"""Agent tool — spawns sub-agents for parallel/isolated work."""

from __future__ import annotations

from typing import Any, Callable

from opencode.core.conversation import Conversation
from opencode.core.cost import CostTracker
from opencode.core.message import Message, Role
from opencode.core.permissions import PermissionManager
from opencode.providers.base import LLMProvider
from opencode.tools.base import Tool, ToolDefinition, ToolParameter, ToolResult
from opencode.tools.registry import ToolRegistry


class AgentTool(Tool):
    """
    Spawns a sub-agent with its own conversation context.
    The sub-agent has access to read-only tools and runs autonomously
    to answer a question or perform research, then returns the result.
    """

    def __init__(
        self,
        provider: LLMProvider,
        tool_registry: ToolRegistry,
        cost_tracker: CostTracker,
        system_prompt: str,
        max_turns: int = 20,
    ) -> None:
        self._provider = provider
        self._tool_registry = tool_registry
        self._cost_tracker = cost_tracker
        self._system_prompt = system_prompt
        self._max_turns = max_turns

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="agent",
            description=(
                "Launch a sub-agent to handle a task autonomously. The sub-agent "
                "has access to read-only tools (glob, grep, read) and will research "
                "the question, then return a single result. Use this for parallel "
                "research or to keep the main context window clean."
            ),
            parameters=[
                ToolParameter(
                    name="prompt",
                    type="string",
                    description="The task or question for the sub-agent to handle",
                ),
            ],
            is_read_only=True,
            requires_permission=False,
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        prompt: str = kwargs["prompt"]

        # Import here to avoid circular dependency
        from opencode.core.agent import AgentLoop

        # Create a sub-agent with only read-only tools
        sub_registry = ToolRegistry()
        for tool_def in self._tool_registry.list_definitions():
            if tool_def.is_read_only:
                tool = self._tool_registry.get(tool_def.name)
                if tool:
                    sub_registry.register(tool)

        sub_conversation = Conversation(
            system_prompt=self._system_prompt
            + "\n\nYou are a sub-agent. Answer the question concisely using the available tools. "
            "You only have read-only tools available."
        )

        sub_agent = AgentLoop(
            provider=self._provider,
            tool_registry=sub_registry,
            permission_manager=PermissionManager(),  # auto-allow read-only
            cost_tracker=self._cost_tracker,  # shared cost tracker
            conversation=sub_conversation,
            max_iterations=self._max_turns,
        )

        try:
            result_msg = await sub_agent.run(prompt)
            return ToolResult(content=result_msg.content or "(no response from sub-agent)")
        except Exception as e:
            return ToolResult(content=f"Sub-agent error: {e}", is_error=True)
