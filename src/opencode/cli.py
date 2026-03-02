"""CLI entry point."""

from __future__ import annotations

import asyncio

import click

from opencode import __version__


@click.command()
@click.option("--model", "-m", default=None, help="Model name (e.g. qwen2.5-coder)")
@click.option(
    "--base-url", "-b", default=None,
    help="OpenAI-compatible API base URL (default: http://localhost:8080/v1)",
)
@click.option("--api-key", "-k", default=None, help="API key (default: not-needed)")
@click.version_option(__version__, prog_name="opencode")
def main(model: str | None, base_url: str | None, api_key: str | None) -> None:
    """OpenCode - Agentic coding assistant in your terminal."""
    from opencode.app import Application

    app = Application.create(model=model, base_url=base_url, api_key=api_key)
    asyncio.run(app.run_interactive())
