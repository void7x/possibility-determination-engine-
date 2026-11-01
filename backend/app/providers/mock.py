"""Deterministic rule-based provider.

This adapter exists so the vertical slice is fully functional with zero API
keys and full reproducibility (acceptance requirement §16.5). It implements
the same interface a cloud model would, returns strictly validated structured
output, and refuses to invent probabilities — unquantified possibilities stay
unquantified unless a transparent arithmetic model applies.
"""

from __future__ import annotations

import hashlib
import json
import re
import time

from app.domains.templates import discover_possibilities, expand_possibility
from app.providers.base import (
    LLMProvider,
    ProviderCapabilities,
    ProviderMessage,
    ProviderResult,
)


def _seed_from(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)


class MockProvider(LLMProvider):
    """Rule-based 'model' — deterministic, auditable, schema-compliant."""

    name = "mock"
    model = "pie-rules-1.0"

    async def generate(
        self,
        messages: list[ProviderMessage],
        response_schema: dict | None = None,
        model_config: dict | None = None,
    ) -> ProviderResult:
        started = time.perf_counter()
        task = (model_config or {}).get("task", "discover")
        decision = (model_config or {}).get("decision", "")
        parent = (model_config or {}).get("parent")
        seed_text = f"{decision}::{json.dumps(parent, sort_keys=True) if parent else ''}"
        seed = _seed_from(seed_text)

        if task == "discover":
            structured = discover_possibilities(decision, seed)
        elif task == "expand":
            structured = expand_possibility(decision, parent or {}, seed)
        else:
            structured = {"possibilities": []}

        latency = int((time.perf_counter() - started) * 1000)
        return ProviderResult(
            content=json.dumps(structured, indent=2),
            structured=structured,
            model=self.model,
            provider=self.name,
            latency_ms=latency,
            usage={"prompt_tokens": len(str(messages)) // 4, "completion_tokens": len(str(structured)) // 4},
        )

    async def health_check(self) -> bool:
        return True

    async def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name=self.name,
            model=self.model,
            structured_output=True,
            streaming=True,
            json_schema=True,
            notes="Deterministic rule-based adapter for offline development and regression baselines.",
        )
