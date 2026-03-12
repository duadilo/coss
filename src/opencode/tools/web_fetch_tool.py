"""Web fetch tool — retrieves and converts web pages to markdown."""

from __future__ import annotations

import re
from typing import Any

import httpx

from opencode.tools.base import Tool, ToolDefinition, ToolParameter, ToolResult, fence_untrusted


def _html_to_markdown(html: str) -> str:
    """Simple HTML to markdown conversion without external dependencies."""
    text = html

    # Remove script and style blocks
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Convert headers
    for i in range(6, 0, -1):
        text = re.sub(
            rf"<h{i}[^>]*>(.*?)</h{i}>",
            lambda m, level=i: f"\n{'#' * level} {m.group(1).strip()}\n",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )

    # Convert links
    text = re.sub(
        r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        r"[\2](\1)",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Convert bold/strong
    text = re.sub(r"<(strong|b)[^>]*>(.*?)</\1>", r"**\2**", text, flags=re.DOTALL | re.IGNORECASE)

    # Convert italic/em
    text = re.sub(r"<(em|i)[^>]*>(.*?)</\1>", r"*\2*", text, flags=re.DOTALL | re.IGNORECASE)

    # Convert code blocks
    text = re.sub(
        r"<pre[^>]*><code[^>]*>(.*?)</code></pre>",
        r"\n```\n\1\n```\n",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", text, flags=re.DOTALL | re.IGNORECASE)

    # Convert list items
    text = re.sub(r"<li[^>]*>(.*?)</li>", r"\n- \1", text, flags=re.DOTALL | re.IGNORECASE)

    # Convert paragraphs and line breaks
    text = re.sub(r"<p[^>]*>(.*?)</p>", r"\n\1\n", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<hr\s*/?>", "\n---\n", text, flags=re.IGNORECASE)

    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Decode common HTML entities
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    text = text.replace("&nbsp;", " ")

    # Clean up whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return text


class WebFetchTool(Tool):
    def __init__(self, timeout: int = 30) -> None:
        self._timeout = timeout

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="web_fetch",
            description=(
                "Fetch a web page and return its content as markdown. "
                "Useful for reading documentation, blog posts, API references, etc."
            ),
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="The URL to fetch",
                ),
                ToolParameter(
                    name="extract_text_only",
                    type="boolean",
                    description="If true, strip all HTML and return plain text (default true)",
                    required=False,
                    default=True,
                ),
            ],
            is_read_only=True,
            requires_permission=True,
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        url: str = kwargs["url"]
        extract_text: bool = kwargs.get("extract_text_only", True)

        # Upgrade http to https
        if url.startswith("http://"):
            url = "https://" + url[7:]

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=self._timeout,
            ) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 "
                            "(Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/605.1.15 "
                            "(KHTML, like Gecko) "
                            "Version/17.10 Safari/605.1.1"
                        )
                    },
                )
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")

                if "text/html" in content_type and extract_text:
                    text = _html_to_markdown(response.text)
                else:
                    text = response.text

                # Truncate very long content
                if len(text) > 50_000:
                    text = text[:50_000] + "\n\n... (content truncated at 50,000 chars)"

                return ToolResult(content=fence_untrusted(text, url))

        except httpx.HTTPStatusError as e:
            return ToolResult(
                content=f"HTTP {e.response.status_code} error fetching {url}",
                is_error=True,
            )
        except httpx.TimeoutException:
            return ToolResult(
                content=f"Request timed out after {self._timeout}s: {url}",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(content=f"Error fetching URL: {e}", is_error=True)
