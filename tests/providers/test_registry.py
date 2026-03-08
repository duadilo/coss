"""Tests for ProviderRegistry model string parsing."""
import pytest
from unittest.mock import patch
from opencode.providers.registry import ProviderRegistry


class TestProviderRegistryParse:
    def test_anthropic_provider(self):
        provider, model, url = ProviderRegistry._parse("anthropic:claude-sonnet-4-20250514", None)
        assert provider == "anthropic"
        assert model == "claude-sonnet-4-20250514"
        assert url is None

    def test_openai_provider(self):
        provider, model, url = ProviderRegistry._parse("openai:gpt-4o", None)
        assert provider == "openai"
        assert model == "gpt-4o"
        assert url is None

    def test_google_provider(self):
        provider, model, url = ProviderRegistry._parse("google:gemini-2.5-flash", None)
        assert provider == "google"
        assert model == "gemini-2.5-flash"
        assert url is None

    def test_ollama_provider(self):
        provider, model, url = ProviderRegistry._parse("ollama:llama3.1", None)
        assert provider == "ollama"
        assert model == "llama3.1"
        assert url is None

    def test_openai_compatible_with_url(self):
        provider, model, url = ProviderRegistry._parse(
            "openai-compatible:http://localhost:8080/v1:my-model", None
        )
        assert provider == "openai-compatible"
        assert model == "my-model"
        assert url == "http://localhost:8080/v1"

    def test_bare_model_uses_default_provider(self):
        with patch.dict("os.environ", {"OPENCODE_PROVIDER": "openai"}, clear=False):
            provider, model, url = ProviderRegistry._parse("gpt-4o", None)
        assert provider == "openai"
        assert model == "gpt-4o"

    def test_bare_model_default_fallback(self):
        with patch.dict("os.environ", {}, clear=True):
            # Remove OPENCODE_PROVIDER if set
            import os
            os.environ.pop("OPENCODE_PROVIDER", None)
            provider, model, url = ProviderRegistry._parse("some-model", None)
        assert provider == "openai-compatible"
        assert model == "some-model"

    def test_base_url_passthrough(self):
        provider, model, url = ProviderRegistry._parse("anthropic:claude-opus", "http://proxy:8080")
        assert url == "http://proxy:8080"

    def test_list_providers(self):
        providers = ProviderRegistry.list_providers()
        assert "anthropic" in providers
        assert "openai" in providers
        assert "google" in providers
        assert "ollama" in providers
        assert "openai-compatible" in providers

    def test_provider_key_env_mapping(self):
        assert ProviderRegistry.PROVIDER_KEY_ENV["anthropic"] == "ANTHROPIC_API_KEY"
        assert ProviderRegistry.PROVIDER_KEY_ENV["openai"] == "OPENAI_API_KEY"
        assert ProviderRegistry.PROVIDER_KEY_ENV["google"] == "GOOGLE_API_KEY"
        assert ProviderRegistry.PROVIDER_KEY_ENV["ollama"] == ""


class TestProviderRegistryCreate:
    def test_creates_anthropic_provider(self):
        from opencode.providers.anthropic import AnthropicProvider
        provider = ProviderRegistry.create("anthropic:claude-sonnet-4-20250514", api_key="test-key")
        assert isinstance(provider, AnthropicProvider)

    def test_creates_openai_compatible_for_openai(self):
        from opencode.providers.openai_compatible import OpenAICompatibleProvider
        provider = ProviderRegistry.create("openai:gpt-4o", api_key="test-key")
        assert isinstance(provider, OpenAICompatibleProvider)

    def test_creates_openai_compatible_for_ollama(self):
        from opencode.providers.openai_compatible import OpenAICompatibleProvider
        provider = ProviderRegistry.create("ollama:llama3.1")
        assert isinstance(provider, OpenAICompatibleProvider)

    def test_creates_google_provider(self):
        from opencode.providers.google import GoogleProvider
        provider = ProviderRegistry.create("google:gemini-2.5-flash", api_key="test-key")
        assert isinstance(provider, GoogleProvider)
