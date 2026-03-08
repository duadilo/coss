"""Tests for ConfigLoader."""
import os
import pytest
from pathlib import Path
from unittest.mock import patch
from opencode.config.loader import ConfigLoader
from opencode.config.settings import Settings


class TestDeepMerge:
    def setup_method(self):
        self.loader = ConfigLoader()

    def test_simple_override(self):
        result = self.loader._deep_merge({"a": 1}, {"a": 2})
        assert result["a"] == 2

    def test_new_key_added(self):
        result = self.loader._deep_merge({"a": 1}, {"b": 2})
        assert result["a"] == 1
        assert result["b"] == 2

    def test_nested_merge(self):
        base = {"provider": {"model": "default", "max_tokens": 4096}}
        override = {"provider": {"model": "gpt-4o"}}
        result = self.loader._deep_merge(base, override)
        assert result["provider"]["model"] == "gpt-4o"
        assert result["provider"]["max_tokens"] == 4096  # preserved

    def test_none_value_skipped(self):
        result = self.loader._deep_merge({"a": 1}, {"a": None})
        assert result["a"] == 1  # None does not override

    def test_nested_none_skipped(self):
        base = {"provider": {"model": "default"}}
        override = {"provider": {"api_key": None}}
        result = self.loader._deep_merge(base, override)
        assert "api_key" not in result["provider"]

    def test_non_dict_override_replaces_dict(self):
        result = self.loader._deep_merge({"a": {"nested": 1}}, {"a": "scalar"})
        assert result["a"] == "scalar"

    def test_empty_override(self):
        base = {"a": 1, "b": 2}
        result = self.loader._deep_merge(base, {})
        assert result == {"a": 1, "b": 2}

    def test_empty_base(self):
        result = self.loader._deep_merge({}, {"a": 1})
        assert result == {"a": 1}

    def test_does_not_mutate_base(self):
        base = {"a": 1}
        self.loader._deep_merge(base, {"b": 2})
        assert "b" not in base


class TestLoadEnvVars:
    def setup_method(self):
        self.loader = ConfigLoader()

    def test_no_env_vars_returns_empty(self):
        clean_env = {k: v for k, v in os.environ.items()
                     if not k.startswith("OPENCODE_")}
        with patch.dict("os.environ", clean_env, clear=True):
            result = self.loader._load_env_vars()
        assert result == {}

    def test_model_env_var(self):
        with patch.dict("os.environ", {"OPENCODE_MODEL": "anthropic:claude-opus"}, clear=False):
            result = self.loader._load_env_vars()
        assert result["provider"]["model"] == "anthropic:claude-opus"

    def test_api_key_env_var(self):
        with patch.dict("os.environ", {"OPENCODE_API_KEY": "sk-test"}, clear=False):
            result = self.loader._load_env_vars()
        assert result["provider"]["api_key"] == "sk-test"

    def test_max_tokens_env_var(self):
        with patch.dict("os.environ", {"OPENCODE_MAX_TOKENS": "2048"}, clear=False):
            result = self.loader._load_env_vars()
        assert result["provider"]["max_tokens"] == 2048
        assert isinstance(result["provider"]["max_tokens"], int)

    def test_temperature_env_var(self):
        with patch.dict("os.environ", {"OPENCODE_TEMPERATURE": "0.7"}, clear=False):
            result = self.loader._load_env_vars()
        assert result["provider"]["temperature"] == pytest.approx(0.7)
        assert isinstance(result["provider"]["temperature"], float)

    def test_base_url_env_var(self):
        with patch.dict("os.environ", {"OPENCODE_BASE_URL": "http://proxy:8080"}, clear=False):
            result = self.loader._load_env_vars()
        assert result["provider"]["base_url"] == "http://proxy:8080"

    def test_max_context_tokens_env_var(self):
        with patch.dict("os.environ", {"OPENCODE_MAX_CONTEXT_TOKENS": "64000"}, clear=False):
            result = self.loader._load_env_vars()
        assert result["provider"]["max_context_tokens"] == 64000


class TestLoadYaml:
    def setup_method(self):
        self.loader = ConfigLoader()

    def test_missing_file_returns_empty(self, tmp_path):
        result = self.loader._load_yaml(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_valid_yaml(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text("provider:\n  model: gpt-4o\n  max_tokens: 2048\n")
        result = self.loader._load_yaml(f)
        assert result["provider"]["model"] == "gpt-4o"
        assert result["provider"]["max_tokens"] == 2048

    def test_invalid_yaml_returns_empty(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text("{invalid yaml: [}")
        result = self.loader._load_yaml(f)
        assert result == {}

    def test_non_dict_yaml_returns_empty(self, tmp_path):
        f = tmp_path / "list.yaml"
        f.write_text("- item1\n- item2\n")
        result = self.loader._load_yaml(f)
        assert result == {}


class TestConfigLoaderLoad:
    def test_load_returns_settings(self):
        loader = ConfigLoader()
        # With no config files and clean env, should return defaults
        clean_env = {k: v for k, v in os.environ.items()
                     if not k.startswith("OPENCODE_")}
        with patch.dict("os.environ", clean_env, clear=True):
            with patch.object(loader, "_load_yaml", return_value={}):
                settings = loader.load()
        assert isinstance(settings, Settings)

    def test_cli_overrides_applied(self):
        loader = ConfigLoader()
        clean_env = {k: v for k, v in os.environ.items()
                     if not k.startswith("OPENCODE_")}
        with patch.dict("os.environ", clean_env, clear=True):
            with patch.object(loader, "_load_yaml", return_value={}):
                settings = loader.load(cli_overrides={"provider": {"model": "openai:gpt-4o"}})
        assert settings.provider.model == "openai:gpt-4o"
