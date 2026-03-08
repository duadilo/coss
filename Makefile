.PHONY: test test-v test-cov lint fmt check run install

install:
	uv sync --extra dev

test:
	uv run --with "pytest>=8.0" --with "pytest-asyncio>=0.24" pytest tests/ -q

test-v:
	uv run --with "pytest>=8.0" --with "pytest-asyncio>=0.24" pytest tests/ -v

test-cov:
	uv run --with "pytest>=8.0" --with "pytest-asyncio>=0.24" --with pytest-cov pytest tests/ -q --cov=src/opencode --cov-report=term-missing

lint:
	uv run --with ruff ruff check src/ tests/

fmt:
	uv run --with ruff ruff format src/ tests/

check: lint test

run:
	uv run opencode
