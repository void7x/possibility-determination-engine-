"""Adapter for any OpenAI-compatible endpoint (OpenAI, Azure, vLLM, Ollama…).

Activated via environment configuration only — no subsystem imports it
directly. Model substitution triggers the same structured-output contract as
every other provider; regression tests cover provider swaps (§3.3, §16.7).
"""

from __future__ import annotations

import json
import time

import httpx

from app.providers.base import (
    LLMProvider,
    ProviderCapabilities,
    ProviderMessage,
    ProviderResult,
    StructuredGenerationError,
)


class OpenAICompatProvider(LLMProvider):
    name = "openai_compat"

    def __init__(
        self,
        api_key: str | None,
        base_url: str | None = None,
        model: str = "gpt-4o-mini",
        timeout: float = 45.0,
        max_retries: int = 2,
    ) -> None:
        self._api_key = api_key
        self._base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self._model = model
        self._timeout = timeout
        self._max_retries = max_retries

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    async def generate(
        self,
        messages: list[ProviderMessage],
        response_schema: dict | None = None,
        model_config: dict | None = None,
    ) -> ProviderResult:
        if not self._api_key:
            raise StructuredGenerationError("OPENAI_API_KEY is not configured")
        body: dict = {
            "model": self._model,
            "messages": [m.model_dump() for m in messages],
            "temperature": (model_config or {}).get("temperature", 0.2),
            "response_format": {"type": "json_object"},
        }
        last_error: Exception | None = None
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(self._max_retries + 1):
                try:
                    response = await client.post(
                        f"{self._base_url}/chat/completions",
                        headers=self._headers(),
                        json=body,
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"] or ""
                    try:
                        structured = json.loads(content)
                    except json.JSONDecodeError as exc:
                        raise StructuredGenerationError(
                            f"model returned non-JSON content: {exc}"
                        ) from exc
                    usage = data.get("usage", {}) or {}
                    return ProviderResult(
                        content=content,
                        structured=structured,
                        model=self._model,
                        provider=self.name,
                        latency_ms=int((time.perf_counter() - started) * 1000),
                        usage={
                            "prompt_tokens": usage.get("prompt_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0),
                        },
                        finish_reason=data["choices"][0].get("finish_reason", "stop"),
                    )
                except (httpx.HTTPError, KeyError) as exc:  # retry transient failures
                    last_error = exc
                    if attempt < self._max_retries:
                        await _backoff(attempt)
        raise StructuredGenerationError(f"provider call failed: {last_error}")

    async def health_check(self) -> bool:
        if not self._api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self._base_url}/models", headers=self._headers())
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name=self.name,
            model=self._model,
            structured_output=True,
            streaming=True,
            json_schema=False,
            notes="OpenAI-compatible chat completions with JSON-object response format.",
        )


async def _backoff(attempt: int) -> None:
    import asyncio

    await asyncio.sleep(min(2**attempt * 0.5, 4.0))
