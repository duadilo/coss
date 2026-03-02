"""MCP client manager for connecting to MCP servers."""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any

from opencode.config.settings import MCPServerEntry
from opencode.mcp.bridge import MCPToolBridge
from opencode.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class MCPClientManager:
    """
    Manages connections to multiple MCP servers.
    Each server gets its own ClientSession.
    Tool lists are fetched and registered into the ToolRegistry.
    """

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._tool_registry = tool_registry
        self._sessions: dict[str, Any] = {}
        self._exit_stack = AsyncExitStack()
        self._transports: list[Any] = []

    async def connect_all(self, servers: dict[str, MCPServerEntry]) -> list[str]:
        """
        Connect to all configured MCP servers.
        Returns list of successfully connected server names.
        """
        connected: list[str] = []
        tasks = [
            self._connect_one(name, config)
            for name, config in servers.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for (name, _), result in zip(servers.items(), results):
            if isinstance(result, Exception):
                logger.warning(f"Failed to connect to MCP server '{name}': {result}")
            elif result:
                connected.append(name)

        return connected

    async def _connect_one(self, name: str, config: MCPServerEntry) -> bool:
        """Connect to a single MCP server and register its tools."""
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            logger.warning(
                "MCP SDK not installed. Install with: pip install mcp"
            )
            return False

        try:
            if config.transport == "stdio":
                params = StdioServerParameters(
                    command=config.command,
                    args=config.args,
                    env=config.env if config.env else None,
                )

                transport = await self._exit_stack.enter_async_context(
                    stdio_client(params)
                )
                read_stream, write_stream = transport
                session = await self._exit_stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )

                await session.initialize()
                self._sessions[name] = session

                # Discover and register tools
                tools_response = await session.list_tools()
                tool_count = 0
                for tool in tools_response.tools:
                    bridge = MCPToolBridge(session, tool, server_name=name)
                    self._tool_registry.register(bridge)
                    tool_count += 1

                logger.info(f"MCP server '{name}': connected, {tool_count} tools registered")
                return True

            elif config.transport == "streamable-http":
                # HTTP-based MCP transport
                try:
                    from mcp.client.streamable_http import streamablehttp_client
                except ImportError:
                    logger.warning(
                        f"MCP streamable-http transport not available for server '{name}'"
                    )
                    return False

                if not config.url:
                    logger.warning(f"MCP server '{name}': url required for streamable-http transport")
                    return False

                transport = await self._exit_stack.enter_async_context(
                    streamablehttp_client(config.url)
                )
                read_stream, write_stream, _ = transport
                session = await self._exit_stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )

                await session.initialize()
                self._sessions[name] = session

                tools_response = await session.list_tools()
                tool_count = 0
                for tool in tools_response.tools:
                    bridge = MCPToolBridge(session, tool, server_name=name)
                    self._tool_registry.register(bridge)
                    tool_count += 1

                logger.info(f"MCP server '{name}' (HTTP): connected, {tool_count} tools registered")
                return True

            else:
                logger.warning(f"MCP server '{name}': unsupported transport '{config.transport}'")
                return False

        except Exception as e:
            logger.warning(f"MCP server '{name}': connection failed: {e}")
            return False

    async def disconnect_all(self) -> None:
        """Disconnect all MCP servers."""
        await self._exit_stack.aclose()
        self._sessions.clear()

    @property
    def connected_servers(self) -> list[str]:
        return list(self._sessions.keys())
