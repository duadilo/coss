"""Provider registry with model string parsing."""

from __future__ import annotations

import os
from typing import Any

from opencode.providers.base import LLMProvider


class ProviderRegistry:
    """
    Discover and instantiate providers by model string.

    Model string formats:
      - "anthropic:claude-sonnet-4-20250514"
      - "openai:gpt-4o"
      - "google:gemini-2.5-flash"
      - "ollama:llama3.1"          (shorthand, uses OpenAI-compatible at localhost:11434)
      - "openai-compatible:http://localhost:8080/v1:my-model"
      - "my-model"                 (bare model name, uses default provider)
    """

    # Known provider prefixes and their env var for API keys
    PROVIDER_KEY_ENV: dict[str, str] = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
        "ollama": "",
        "openai-compatible": "OPENCODE_API_KEY",
    }

    @classmethod
    def create(
        cls,
        model_string: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> LLMProvider:
        """
        Parse a model string and return an instantiated provider.
        """
        provider_name, model_name, resolved_base_url = cls._parse(model_string, base_url)

        if provider_name == "anthropic":
            from opencode.providers.anthropic import AnthropicProvider

            key = api_key or os.environ.get("ANTHROPIC_API_KEY")
            return AnthropicProvider(model=model_name, api_key=key)

        elif provider_name == "google":
            from opencode.providers.google import GoogleProvider

            key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
            return GoogleProvider(model=model_name, api_key=key)

        elif provider_name == "ollama":
            from opencode.providers.openai_compatible import OpenAICompatibleProvider

            url = resolved_base_url or "http://localhost:11434/v1"
            return OpenAICompatibleProvider(
                model=model_name, base_url=url, api_key="ollama"
            )

        elif provider_name in ("openai", "openai-compatible"):
            from opencode.providers.openai_compatible import OpenAICompatibleProvider

            key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENCODE_API_KEY", "not-needed")
            url = resolved_base_url or (
                "https://api.openai.com/v1" if provider_name == "openai"
                else "http://localhost:8080/v1"
            )
            return OpenAICompatibleProvider(model=model_name, base_url=url, api_key=key)

        else:
            # Unknown provider prefix — treat as openai-compatible
            from opencode.providers.openai_compatible import OpenAICompatibleProvider

            key = api_key or os.environ.get("OPENCODE_API_KEY", "not-needed")
            url = resolved_base_url or os.environ.get("OPENCODE_BASE_URL", "http://localhost:8080/v1")
            return OpenAICompatibleProvider(model=model_string, base_url=url, api_key=key)

    @classmethod
    def _parse(
        cls, model_string: str, base_url: str | None
    ) -> tuple[str, str, str | None]:
        """
        Parse model string into (provider_name, model_name, base_url).

        Formats:
          "provider:model"
          "openai-compatible:http://host/v1:model"
          "bare-model"
        """
        if ":" not in model_string:
            # Bare model name — infer provider from env or default to openai-compatible
            default_provider = os.environ.get("OPENCODE_PROVIDER", "openai-compatible")
            return default_provider, model_string, base_url

        parts = model_string.split(":", maxsplit=1)
        provider_name = parts[0].lower()

        if provider_name == "openai-compatible" and parts[1].startswith("http"):
            # openai-compatible:http://host/v1:model
            url_and_model = parts[1].rsplit(":", maxsplit=1)
            if len(url_and_model) == 2:
                return provider_name, url_and_model[1], url_and_model[0]
            return provider_name, "default", parts[1]

        return provider_name, parts[1], base_url

    @classmethod
    def list_providers(cls) -> list[str]:
        return list(cls.PROVIDER_KEY_ENV.keys())
