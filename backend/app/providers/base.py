"""Provider-agnostic LLM interface (§3).

No intelligence subsystem imports a vendor SDK. Every provider adapter
normalizes to ``ProviderResult``. Substituting the model must not require
rewriting causal, probability, simulation or graph engines.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class ProviderMessage(BaseModel):
    role: str  # "system" | "user" | "assistant"
    content: str


class ProviderCapabilities(BaseModel):
    name: str
    model: str
    structured_output: bool = True
    streaming: bool = False
    json_schema: bool = True
    max_context_tokens: int = 8192
    notes: str = ""


class ProviderUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_estimate_usd: float | None = None


class ProviderResult(BaseModel):
    """Normalized internal result — the only shape subsystems consume."""

    content: str = ""
    structured: dict[str, Any] | None = None
    model: str = ""
    provider: str = ""
    latency_ms: int = 0
    usage: ProviderUsage = Field(default_factory=ProviderUsage)
    finish_reason: str = "stop"


class LLMProvider(ABC):
    """Common internal interface every provider adapter implements."""

    name: str = "abstract"

    @abstractmethod
    async def generate(
        self,
        messages: list[ProviderMessage],
        response_schema: dict | None = None,
        model_config: dict | None = None,
    ) -> ProviderResult:
        ...

    async def stream(self, messages: list[ProviderMessage], model_config: dict | None = None):
        """Default streaming fallback: chunk the completed generation."""
        result = await self.generate(messages, model_config=model_config)
        step = max(1, len(result.content) // 12)
        for i in range(0, len(result.content), step):
            yield result.content[i : i + step]

    @abstractmethod
    async def health_check(self) -> bool:
        ...

    @abstractmethod
    async def get_capabilities(self) -> ProviderCapabilities:
        ...


class ProviderError(Exception):
    pass


class StructuredGenerationError(ProviderError):
    """Model failed to satisfy the requested schema — caller decides fallback."""
