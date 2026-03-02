"""Config loading from YAML files, environment variables, and CLI args."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from opencode.config.constants import (
    GLOBAL_CONFIG_FILE,
    PROJECT_CONFIG_DIR_NAME,
    PROJECT_CONFIG_FILE_NAME,
)
from opencode.config.settings import Settings


class ConfigLoader:
    """
    Load and merge configuration from all sources.

    Precedence (later overrides earlier):
    1. Built-in defaults (Settings model)
    2. Global config: ~/.opencode/config.yaml
    3. Project config: .opencode/config.yaml (walked up from cwd)
    4. Environment variables
    5. CLI arguments
    """

    def load(self, cli_overrides: dict[str, Any] | None = None) -> Settings:
        base: dict[str, Any] = {}

        # Global config
        global_cfg = self._load_yaml(GLOBAL_CONFIG_FILE)
        base = self._deep_merge(base, global_cfg)

        # Project config
        project_cfg_path = self._find_project_config()
        if project_cfg_path:
            project_cfg = self._load_yaml(project_cfg_path)
            base = self._deep_merge(base, project_cfg)

        # Environment variables
        env_cfg = self._load_env_vars()
        base = self._deep_merge(base, env_cfg)

        # CLI overrides
        if cli_overrides:
            base = self._deep_merge(base, cli_overrides)

        return Settings(**base)

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _find_project_config(self) -> Path | None:
        """Walk up from cwd looking for .opencode/config.yaml."""
        current = Path.cwd()
        while True:
            candidate = current / PROJECT_CONFIG_DIR_NAME / PROJECT_CONFIG_FILE_NAME
            if candidate.exists():
                return candidate
            parent = current.parent
            if parent == current:
                break
            current = parent
        return None

    def _load_env_vars(self) -> dict[str, Any]:
        """Map environment variables to config dict."""
        result: dict[str, Any] = {}
        provider: dict[str, Any] = {}

        if model := os.environ.get("OPENCODE_MODEL"):
            provider["model"] = model
        if base_url := os.environ.get("OPENCODE_BASE_URL"):
            provider["base_url"] = base_url
        if api_key := os.environ.get("OPENCODE_API_KEY"):
            provider["api_key"] = api_key
        if max_tokens := os.environ.get("OPENCODE_MAX_TOKENS"):
            provider["max_tokens"] = int(max_tokens)
        if temperature := os.environ.get("OPENCODE_TEMPERATURE"):
            provider["temperature"] = float(temperature)

        if provider:
            result["provider"] = provider

        return result

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Recursively merge override into base."""
        result = base.copy()
        for key, value in override.items():
            if value is None:
                continue
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
