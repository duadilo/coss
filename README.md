# OpenCode

Open-source agentic coding CLI with multi-provider LLM support. Built in Python.

## Installation

### Install uv

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Quick Start

```bash
# Install dependencies
uv sync

# Run with a local llama.cpp server (default: http://localhost:8080/v1)
uv run opencode

# Specify a bare model name (uses OpenAI-compatible endpoint)
uv run opencode --model qwen2.5-coder --base-url http://localhost:8080/v1
```

### Multi-Provider Support

Use `provider:model` syntax to target different LLM providers:

```bash
# Anthropic Claude
export ANTHROPIC_API_KEY=sk-ant-...
uv run opencode --model anthropic:claude-sonnet-4-20250514

# OpenAI
export OPENAI_API_KEY=sk-...
uv run opencode --model openai:gpt-4o

# Google Gemini
export GOOGLE_API_KEY=...
uv run opencode --model google:gemini-2.5-flash

# Ollama (auto-detects localhost:11434)
uv run opencode --model ollama:llama3.1

# Ollama with explicit base URL
uv run opencode --model gpt-oss:120b --base-url http://localhost:11434/v1

# Any OpenAI-compatible server
uv run opencode --model my-model --base-url http://localhost:8080/v1
```

### Non-Interactive Mode

```bash
# Run a single prompt and exit
uv run opencode -p "explain what this project does"

# Pipe stdin
cat src/main.py | uv run opencode -p "review this code"

# Combine stdin and prompt
echo "def foo(): pass" | uv run opencode -p "add type hints and docstring"
```

### Environment Variables

```bash
export OPENCODE_MODEL=ollama:llama3.1
export OPENCODE_BASE_URL=http://localhost:8080/v1
export OPENCODE_API_KEY=not-needed

# Search backends (for web_search tool)
export OPENCODE_SEARCH_API=ddgs   # or "searxng", "brave", or "google"

# SearXNG (self-hosted)
export SEARXNG_URL=http://localhost:8800

# Brave Search
export BRAVE_API_KEY=BSA...

# Google Custom Search
export GOOGLE_CSE_API_KEY=AIza...
export GOOGLE_CSE_ID=a1b2c3...
```

### Config Files

OpenCode loads YAML config with this precedence:

1. Built-in defaults
2. `~/.opencode/config.yaml` (global)
3. `.opencode/config.yaml` (project, walked up from cwd)
4. Environment variables
5. CLI arguments

Example `~/.opencode/config.yaml`:

```yaml
provider:
  model: ollama:llama3.1
  base_url: http://localhost:11434/v1
  max_tokens: 4096
  temperature: 0.0

permissions:
  auto_allow_read_tools: true
  auto_allow_write_tools: false
  auto_allow_bash: false

mcp_servers:
  filesystem:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/home/user/projects"]

hooks:
  - event: pre_tool_call
    tool_pattern: "bash"
    command: "echo Running: $OPENCODE_TOOL_ARG_COMMAND"
```

### Memory

Create an `OPENCODE.md` file in your project root (or `~/.opencode/OPENCODE.md` globally) to inject persistent instructions into every session:

```markdown
# Project Guidelines
- Use Python 3.11+ features
- Run tests with `pytest` before committing
- Follow PEP 8 style
```

## Features

- **Interactive REPL** with streaming markdown output
- **Non-interactive mode** — `opencode -p "prompt"` for scripting and CI
- **Pipe support** — `cat file | opencode -p "review"`
- **Agentic tool loop** — LLM calls tools, observes results, iterates until done
- **Multi-provider** — Anthropic, OpenAI, Google Gemini, Ollama, any OpenAI-compatible API
- **10 built-in tools**: bash, read, write, edit, glob, grep, agent, web_fetch, web_search
- **MCP support** — connect to Model Context Protocol servers for additional tools
- **Plan mode** — `/plan` toggles read-only exploration mode
- **Permission system** — prompts before write/bash operations (y/n/always)
- **Persistent memory** — OPENCODE.md files loaded into system prompt every session
- **Context management** — auto-compacts conversation when approaching window limit
- **Hooks** — configurable pre/post tool-call shell commands
- **Sub-agents** — `agent` tool spawns isolated agents for parallel research
- **Hot-swap models** — `/model ollama:llama3.1` switches mid-session
- **Token tracking** — `/cost` shows session usage
- **Config system** — YAML config with global/project/env/CLI precedence
- **Retry logic** — automatic retries on transient API errors
- **Slash commands** — `/help`, `/clear`, `/cost`, `/model`, `/config`, `/plan`, `/compact`, `/memory`, `/exit`

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- An LLM provider (local server, Ollama, or cloud API key)

## Development

```bash
# Install with dev dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Lint
uv run ruff check src/

# Type check
uv run mypy src/
```

## Project Structure

```
src/opencode/
├── cli.py                      # CLI entry point (Click)
├── app.py                      # Application wiring
├── core/
│   ├── agent.py                # Central agentic loop
│   ├── message.py              # Data models (Message, ToolCall, etc.)
│   ├── conversation.py         # Conversation history
│   ├── context.py              # Context window management + compaction
│   ├── permissions.py          # Tool call permission gating
│   ├── plan_mode.py            # Read-only planning mode
│   └── cost.py                 # Token usage tracking
├── providers/
│   ├── base.py                 # LLM provider ABC
│   ├── registry.py             # Provider discovery + model string parsing
│   ├── openai_compatible.py    # OpenAI-compatible (llama.cpp, vLLM, Ollama, OpenAI)
│   ├── anthropic.py            # Anthropic Claude
│   └── google.py               # Google Gemini
├── tools/
│   ├── base.py                 # Tool ABC and definitions
│   ├── registry.py             # Tool registry
│   ├── bash_tool.py            # Shell command execution
│   ├── read_tool.py            # File reading
│   ├── write_tool.py           # File writing
│   ├── edit_tool.py            # Find-and-replace editing
│   ├── glob_tool.py            # File search by pattern
│   ├── grep_tool.py            # Content search (ripgrep/regex)
│   ├── agent_tool.py           # Sub-agent spawner
│   ├── web_fetch_tool.py       # Fetch web pages as markdown
│   └── web_search_tool.py      # Web search (DuckDuckGo/SearXNG/Brave/Google)
├── mcp/
│   ├── client.py               # MCP server connection manager
│   ├── bridge.py               # Wraps MCP tools as native tools
│   └── config.py               # MCP server configuration
├── config/
│   ├── settings.py             # Pydantic settings model
│   ├── loader.py               # YAML + env + CLI config merge
│   └── constants.py            # Default paths and values
├── memory/
│   ├── store.py                # OPENCODE.md file read/write
│   └── system_prompt.py        # Dynamic system prompt assembly
├── hooks/
│   └── manager.py              # Pre/post tool-call hooks
└── ui/
    ├── repl.py                 # Interactive REPL (prompt_toolkit)
    ├── renderer.py             # Streaming markdown renderer (Rich)
    └── slash_commands.py       # All slash commands
```

## License

MIT
