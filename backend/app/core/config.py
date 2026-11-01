"""PIE core configuration.

Provider-agnostic by design: which LLM provider is active, its credentials and
the exploration limits are all configuration, never hard-coded dependencies.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # --- LLM provider selection -------------------------------------------
    # "mock"  -> deterministic rule-based provider (no network, reproducible)
    # "openai" / "openai_compat" -> any OpenAI-compatible endpoint
    provider_name: str = os.environ.get("PIE_PROVIDER", "mock")
    openai_api_key: str | None = os.environ.get("OPENAI_API_KEY")
    openai_base_url: str | None = os.environ.get("OPENAI_BASE_URL")
    openai_model: str = os.environ.get("PIE_OPENAI_MODEL", "gpt-4o-mini")
    llm_timeout_seconds: float = float(os.environ.get("PIE_LLM_TIMEOUT", "45"))
    llm_max_retries: int = _env_int("PIE_LLM_RETRIES", 2)

    # --- Exploration limits (§6.3 stopping criteria) -----------------------
    max_graph_depth: int = _env_int("PIE_MAX_DEPTH", 4)
    max_nodes_per_analysis: int = _env_int("PIE_MAX_NODES", 60)
    beam_width: int = _env_int("PIE_BEAM_WIDTH", 6)

    # --- Event pacing ------------------------------------------------------
    # Small deliberate pauses between orchestration steps so the exploration
    # space renders each real event. Events themselves are genuine; pacing
    # never fabricates intelligence, it only schedules it.
    event_pace_seconds: float = float(os.environ.get("PIE_PACE", "0.55"))

    # --- Storage -----------------------------------------------------------
    # In-memory store for the vertical slice. The Store protocol is the seam
    # where the PostgreSQL implementation (§5.4) plugs in later.
    event_log_retention: int = _env_int("PIE_EVENT_RETENTION", 2000)

    app_name: str = "Possibility Intelligence Engine"
    version: str = "0.1.0-vertical-slice"


settings = Settings()
