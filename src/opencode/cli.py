"""CLI entry point."""

from __future__ import annotations

import asyncio
import sys

import click

from opencode import __version__


@click.command()
@click.option(
    "--model", "-m", default=None,
    help="Model string (e.g. anthropic:claude-sonnet-4-20250514, openai:gpt-4o, ollama:llama3.1, my-model)",
)
@click.option(
    "--base-url", "-b", default=None,
    help="API base URL (default: http://localhost:8080/v1)",
)
@click.option("--api-key", "-k", default=None, help="API key")
@click.option("--plan", is_flag=True, default=False, help="Start in plan mode (read-only)")
@click.option(
    "--prompt", "-p", default=None,
    help="Run a single prompt non-interactively and exit",
)
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable verbose logging")
@click.option("--debug", is_flag=True, default=False, help="Enable debug logging")
@click.version_option(__version__, prog_name="opencode")
def main(
    model: str | None,
    base_url: str | None,
    api_key: str | None,
    plan: bool,
    prompt: str | None,
    verbose: bool,
    debug: bool,
) -> None:
    """OpenCode - Agentic coding assistant in your terminal."""
    import logging

    if debug:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s: %(message)s")
    elif verbose:
        logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")

    from opencode.app import Application

    # Check for piped stdin
    stdin_content: str | None = None
    if not sys.stdin.isatty():
        stdin_content = sys.stdin.read()

    app = Application.create(model=model, base_url=base_url, api_key=api_key, plan=plan)

    if prompt or stdin_content:
        # Non-interactive mode
        full_prompt = ""
        if stdin_content:
            full_prompt += f"<stdin>\n{stdin_content}\n</stdin>\n\n"
        if prompt:
            full_prompt += prompt
        elif stdin_content:
            full_prompt = stdin_content

        asyncio.run(app.run_once(full_prompt))
    else:
        # Interactive REPL
        asyncio.run(app.run_interactive())
