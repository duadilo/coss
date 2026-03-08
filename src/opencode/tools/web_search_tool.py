"""Web search tool — searches the web via a configurable backend."""

from __future__ import annotations

import os
from typing import Any

import httpx

from opencode.tools.base import Tool, ToolDefinition, ToolParameter, ToolResult


class WebSearchTool(Tool):
    """
    Web search using a configurable search API.

    Supported backends (set via OPENCODE_SEARCH_API env var):
    - "ddgs"     : DuckDuckGo Search (default, no API key needed)
    - "searxng"  : SearXNG instance (needs SEARXNG_URL)
    - "brave"    : Brave Search API (needs BRAVE_API_KEY)

    Falls back to a message suggesting the user configure a search API
    if no backend is available.
    """

    def __init__(self) -> None:
        self._backend = os.environ.get("OPENCODE_SEARCH_API", "ddgs").lower()

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="web_search",
            description=(
                "Search the web for information. Returns search results with "
                "titles, URLs, and snippets. Useful for finding documentation, "
                "current information, or answers to questions."
            ),
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="The search query",
                ),
                ToolParameter(
                    name="num_results",
                    type="integer",
                    description="Number of results to return (default 5)",
                    required=False,
                    default=5,
                ),
            ],
            is_read_only=True,
            requires_permission=True,
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        query: str = kwargs["query"]
        num_results: int = kwargs.get("num_results", 5)

        if self._backend == "ddgs":
            return await self._search_ddgs(query, num_results)
        elif self._backend == "searxng":
            return await self._search_searxng(query, num_results)
        elif self._backend == "brave":
            return await self._search_brave(query, num_results)
        else:
            return ToolResult(
                content=(
                    f"Unknown search backend: {self._backend}. "
                    "Set OPENCODE_SEARCH_API to 'ddgs', 'searxng', or 'brave'."
                ),
                is_error=True,
            )

    async def _search_ddgs(self, query: str, num_results: int) -> ToolResult:
        try:
            from ddgs import DDGS

            data = DDGS().text(query, max_results=num_results)

            results: list[str] = []
            for r in data:
                title = r.get("title", "")
                url = r.get("href", "")
                snippet = r.get("body", "")[:300]
                results.append(f"### [{title}]({url})\n{snippet}\n")

            return ToolResult(
                content="\n".join(results) if results else "No results found."
            )
        except Exception as e:
            return ToolResult(content=f"DuckDuckGo search error: {e}", is_error=True)

    async def _search_searxng(self, query: str, num_results: int) -> ToolResult:
        base_url = os.environ.get("SEARXNG_URL")
        if not base_url:
            return ToolResult(
                content="SEARXNG_URL not set. Set it to your SearXNG instance URL.",
                is_error=True,
            )

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(
                    f"{base_url.rstrip('/')}/search",
                    params={
                        "q": query,
                        "format": "json",
                        "number_of_results": num_results,
                    },
                )
                response.raise_for_status()
                data = response.json()

            results: list[str] = []
            for r in data.get("results", [])[:num_results]:
                title = r.get("title", "")
                url = r.get("url", "")
                snippet = r.get("content", "")[:300]
                results.append(f"### [{title}]({url})\n{snippet}\n")

            return ToolResult(
                content="\n".join(results) if results else "No results found."
            )
        except Exception as e:
            return ToolResult(content=f"SearXNG search error: {e}", is_error=True)

    async def _search_brave(self, query: str, num_results: int) -> ToolResult:
        api_key = os.environ.get("BRAVE_API_KEY")
        if not api_key:
            return ToolResult(
                content="BRAVE_API_KEY not set. Get one at https://brave.com/search/api/",
                is_error=True,
            )

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": num_results},
                    headers={
                        "X-Subscription-Token": api_key,
                        "Accept": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()

            results: list[str] = []
            for r in data.get("web", {}).get("results", [])[:num_results]:
                title = r.get("title", "")
                url = r.get("url", "")
                snippet = r.get("description", "")[:300]
                results.append(f"### [{title}]({url})\n{snippet}\n")

            return ToolResult(
                content="\n".join(results) if results else "No results found."
            )
        except Exception as e:
            return ToolResult(content=f"Brave search error: {e}", is_error=True)
