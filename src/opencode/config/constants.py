"""Default paths, file names, and version info."""

from pathlib import Path

# Config directories
GLOBAL_CONFIG_DIR = Path.home() / ".opencode"
GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.yaml"

# Project-level config
PROJECT_CONFIG_DIR_NAME = ".opencode"
PROJECT_CONFIG_FILE_NAME = "config.yaml"
PROJECT_MEMORY_FILE_NAME = "OPENCODE.md"

# Defaults
DEFAULT_MODEL = "default"
DEFAULT_BASE_URL = "http://localhost:8080/v1"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_CONTEXT_TOKENS = 128_000
DEFAULT_COMPACT_THRESHOLD = 0.8
