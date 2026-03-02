"""The central agentic loop."""

from __future__ import annotations

import json
from typing import Any, Callable

from opencode.core.context import ContextManager
from opencode.core.conversation import Conversation
from opencode.core.cost import CostTracker
from opencode.core.message import Message, Role, ToolCall, ToolResult, Usage
from opencode.core.permissions import PermissionDecision, PermissionManager
from opencode.core.plan_mode import PlanMode
from opencode.hooks.manager import HookManager
from opencode.providers.base import LLMProvider, StreamChunk
from opencode.tools.base import ToolDefinition
from opencode.tools.registry import ToolRegistry


class AgentLoop:
    """
    Central agentic loop. Takes user input, calls the LLM, executes tool
    calls, feeds results back, and repeats until the LLM produces a final
    text response with no further tool calls.
    """

    def __init__(
        self,
        provider: LLMProvider,
        tool_registry: ToolRegistry,
        permission_manager: PermissionManager,
        cost_tracker: CostTracker,
        conversation: Conversation,
        plan_mode: PlanMode | None = None,
        context_manager: ContextManager | None = None,
        hook_manager: HookManager | None = None,
        max_iterations: int = 50,
    ) -> None:
        self.provider = provider
        self.tool_registry = tool_registry
        self.permission_manager = permission_manager
        self.cost_tracker = cost_tracker
        self.conversation = conversation
        self.plan_mode = plan_mode or PlanMode()
        self.context_manager = context_manager
        self.hook_manager = hook_manager or HookManager()
        self.max_iterations = max_iterations

    async def run(
        self,
        user_message: str,
        *,
        on_stream_chunk: Callable[[StreamChunk], None] | None = None,
        on_tool_start: Callable[[ToolCall, ToolDefinition | None], None] | None = None,
        on_tool_end: Callable[[ToolCall, ToolResult], None] | None = None,
        on_permission_request: Callable[[ToolCall, ToolDefinition | None], bool] | None = None,
    ) -> Message:
        """Execute the agent loop for a single user turn."""
        self.conversation.add_user_message(user_message)

        for _iteration in range(self.max_iterations):
            # Check if context window needs compaction
            if self.context_manager and self.context_manager.should_compact(self.conversation):
                await self.context_manager.compact(self.conversation, self.provider)

            # Get available tools, filtered by plan mode
            tool_defs = self._get_available_tools()

            # Stream LLM response
            assistant_msg = await self._stream_response(
                tool_defs, on_stream_chunk
            )

            # Record usage
            self.cost_tracker.record(assistant_msg.usage)

            # Add assistant message to conversation
            self.conversation.add_assistant_message(assistant_msg)

            # If no tool calls, we're done
            if not assistant_msg.has_tool_calls:
                return assistant_msg

            # Execute tool calls
            tool_result_messages = await self._execute_tool_calls(
                assistant_msg.tool_calls,
                on_tool_start=on_tool_start,
                on_tool_end=on_tool_end,
                on_permission_request=on_permission_request,
            )

            # Add tool results to conversation
            self.conversation.add_tool_results(tool_result_messages)

        # Safety limit
        return Message(
            role=Role.ASSISTANT,
            content="[Reached maximum iteration limit. Please continue with a new message.]",
        )

    def _get_available_tools(self) -> list[ToolDefinition]:
        """Get tool definitions, filtered by plan mode if active."""
        all_tools = self.tool_registry.list_definitions()
        if self.plan_mode.is_active:
            return [t for t in all_tools if t.is_read_only]
        return all_tools

    async def _stream_response(
        self,
        tool_defs: list[ToolDefinition],
        on_chunk: Callable[[StreamChunk], None] | None,
    ) -> Message:
        """Call the LLM with streaming and accumulate the response."""
        accumulated_text = ""
        tool_calls: list[ToolCall] = []
        usage = Usage()

        # Track in-progress tool calls by index
        tc_builders: dict[int, dict[str, Any]] = {}
        current_tc_index = 0

        async for chunk in self.provider.stream(
            self.conversation.messages,
            self.conversation.system_prompt,
            tool_defs,
        ):
            if on_chunk and chunk.text:
                on_chunk(chunk)

            if chunk.text:
                accumulated_text += chunk.text

            # Handle tool call deltas
            if chunk.tool_call_id or chunk.tool_call_name or chunk.tool_call_arguments_delta:
                if chunk.tool_call_id:
                    # New tool call starting
                    tc_builders[current_tc_index] = {
                        "id": chunk.tool_call_id,
                        "name": chunk.tool_call_name or "",
                        "arguments": "",
                    }
                if chunk.tool_call_name and current_tc_index in tc_builders:
                    tc_builders[current_tc_index]["name"] = chunk.tool_call_name
                if chunk.tool_call_arguments_delta and current_tc_index in tc_builders:
                    tc_builders[current_tc_index]["arguments"] += chunk.tool_call_arguments_delta

                # Check if this tool call is done (next one starts or finish)
                if chunk.finish_reason or (
                    chunk.tool_call_id
                    and current_tc_index in tc_builders
                    and tc_builders[current_tc_index]["id"] != chunk.tool_call_id
                ):
                    current_tc_index += 1

            if chunk.usage:
                usage = chunk.usage

        # Finalize tool calls
        for _idx, builder in sorted(tc_builders.items()):
            try:
                arguments = json.loads(builder["arguments"]) if builder["arguments"] else {}
            except json.JSONDecodeError:
                arguments = {"_raw": builder["arguments"]}

            tool_calls.append(ToolCall(
                id=builder["id"],
                name=builder["name"],
                arguments=arguments,
            ))

        return Message(
            role=Role.ASSISTANT,
            content=accumulated_text,
            tool_calls=tool_calls,
            usage=usage,
        )

    async def _execute_tool_calls(
        self,
        tool_calls: list[ToolCall],
        *,
        on_tool_start: Callable[[ToolCall, ToolDefinition | None], None] | None,
        on_tool_end: Callable[[ToolCall, ToolResult], None] | None,
        on_permission_request: Callable[[ToolCall, ToolDefinition | None], bool] | None,
    ) -> list[Message]:
        """Execute tool calls and return tool result messages."""
        result_messages: list[Message] = []

        for tc in tool_calls:
            tool = self.tool_registry.get(tc.name)
            tool_def = tool.definition() if tool else None

            # Check permissions
            if tool_def:
                decision = self.permission_manager.check(tc, tool_def)
                if decision == PermissionDecision.PROMPT:
                    if on_permission_request:
                        allowed = on_permission_request(tc, tool_def)
                        if not allowed:
                            tr = ToolResult(
                                tool_call_id=tc.id,
                                name=tc.name,
                                content="Permission denied by user.",
                                is_error=True,
                            )
                            result_messages.append(Message(
                                role=Role.TOOL,
                                tool_results=[tr],
                            ))
                            if on_tool_end:
                                on_tool_end(tc, tr)
                            continue
                    # If no permission handler, auto-allow
                elif decision == PermissionDecision.DENY:
                    tr = ToolResult(
                        tool_call_id=tc.id,
                        name=tc.name,
                        content="Tool call denied by policy.",
                        is_error=True,
                    )
                    result_messages.append(Message(role=Role.TOOL, tool_results=[tr]))
                    continue

            # Run pre-hooks
            pre_results = await self.hook_manager.run_pre_hooks(tc)
            block_msg = self.hook_manager.has_blocking_failure(pre_results)
            if block_msg:
                tr = ToolResult(
                    tool_call_id=tc.id,
                    name=tc.name,
                    content=block_msg,
                    is_error=True,
                )
                result_messages.append(Message(role=Role.TOOL, tool_results=[tr]))
                if on_tool_end:
                    on_tool_end(tc, tr)
                continue

            if on_tool_start:
                on_tool_start(tc, tool_def)

            if tool is None:
                tr = ToolResult(
                    tool_call_id=tc.id,
                    name=tc.name,
                    content=f"Unknown tool: {tc.name}",
                    is_error=True,
                )
            else:
                try:
                    tool_result = await tool.execute(**tc.arguments)
                    tr = ToolResult(
                        tool_call_id=tc.id,
                        name=tc.name,
                        content=tool_result.content,
                        is_error=tool_result.is_error,
                    )
                except Exception as e:
                    tr = ToolResult(
                        tool_call_id=tc.id,
                        name=tc.name,
                        content=f"Tool execution error: {e}",
                        is_error=True,
                    )

            result_messages.append(Message(role=Role.TOOL, tool_results=[tr]))

            # Run post-hooks
            await self.hook_manager.run_post_hooks(tc)

            if on_tool_end:
                on_tool_end(tc, tr)

        return result_messages
