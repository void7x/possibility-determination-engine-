"""Provider registry: configuration-driven selection and health reporting."""

from __future__ import annotations

from app.core.config import settings
from app.providers.base import LLMProvider
from app.providers.mock import MockProvider
from app.providers.openai_compat import OpenAICompatProvider


def build_provider() -> LLMProvider:
    name = settings.provider_name.lower()
    if name in {"openai", "openai_compat"}:
        return OpenAICompatProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
    # Default: deterministic mock so the system always boots and stays
    # reproducible for regression baselines.
    return MockProvider()


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}

    def register(self, provider: LLMProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str | None = None) -> LLMProvider:
        if name is None:
            return self._providers["mock"] if "mock" in self._providers else next(iter(self._providers.values()))
        if name not in self._providers:
            raise KeyError(f"provider {name!r} is not registered")
        return self._providers[name]

    def names(self) -> list[str]:
        return sorted(self._providers)


def build_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(MockProvider())
    active = build_provider()
    registry.register(active)
    return registry
