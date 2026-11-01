"""Domain models for the scenario graph (§5 of the PIE specification).

Design commitments encoded here:

* A possibility may be meaningful with ``estimate = None`` — the probability
  object explicitly supports "unquantified".
* Probability kinds distinguish data-backed, model-based, elicited and
  unquantified estimates. A model-based estimate must carry its assumptions.
* Graph edges reference node ids; relationship types come from a fixed
  vocabulary with defined semantics.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


# ---------------------------------------------------------------------------
# Enums / vocabularies
# ---------------------------------------------------------------------------

class AnalysisStatus(str, Enum):
    created = "created"
    running = "running"
    completed = "completed"
    cancelled = "cancelled"
    failed = "failed"


class ScenarioStatus(str, Enum):
    exploring = "exploring"
    validated = "validated"
    alternative = "alternative"   # created via what-if; original preserved
    unexplored = "unexplored"     # explicit marker (§6.3)
    infeasible = "infeasible"


class ImpactLevel(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"
    critical = "critical"


class ProbabilityStatus(str, Enum):
    unquantified = "unquantified"
    quantified = "quantified"


ProbabilityMethod = Literal[
    "data_backed",
    "model_based",
    "expert_elicited",
    "unquantified",
]

# §5.3 relationship vocabulary
RelationshipType = Literal[
    "MAY_CAUSE",
    "REQUIRES",
    "PREVENTS",
    "LEADS_TO",
    "DEPENDS_ON",
    "ALTERNATIVE_TO",
    "CONTRADICTS",
    "MODIFIES",
    "CONVERGES_WITH",
]


# ---------------------------------------------------------------------------
# Possibility object (§5.2)
# ---------------------------------------------------------------------------

class TimeHorizon(BaseModel):
    minimum: int | None = None
    maximum: int | None = None
    unit: str = "months"

    def label(self) -> str:
        if self.minimum is None and self.maximum is None:
            return "unspecified horizon"
        if self.minimum == self.maximum:
            return f"~{self.minimum} {self.unit}"
        return f"{self.minimum or '?'}–{self.maximum or '?'} {self.unit}"


class ProbabilityObject(BaseModel):
    """Never fabricate: unquantified possibilities keep a null estimate."""

    status: ProbabilityStatus = ProbabilityStatus.unquantified
    estimate: float | None = None
    interval: list[float] | None = None
    method: ProbabilityMethod | None = None
    rationale: str | None = None

    @model_validator(mode="after")
    def _consistency(self) -> "ProbabilityObject":
        if self.status == ProbabilityStatus.unquantified:
            if self.estimate is not None:
                raise ValueError("unquantified probability must have estimate=None")
            if self.method is not None and self.method != "unquantified":
                raise ValueError("unquantified probability cannot claim a method")
        else:
            if self.estimate is None:
                raise ValueError("quantified probability requires an estimate")
            if not 0.0 <= self.estimate <= 1.0:
                raise ValueError("probability estimate must lie in [0, 1]")
            if self.method in (None, "unquantified"):
                raise ValueError("quantified probability requires a method")
        return self


class ImpactObject(BaseModel):
    level: ImpactLevel = ImpactLevel.moderate
    explanation: str = ""


class EvidenceRef(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ev"))
    kind: Literal["user_fact", "external", "assumption", "model"] = "assumption"
    claim: str
    provenance: str = "user-provided"
    observed_at: str = Field(default_factory=utcnow)


class Assumption(BaseModel):
    id: str = Field(default_factory=lambda: new_id("as"))
    statement: str
    is_blocking: bool = False   # estimate invalid without it when True


class Possibility(BaseModel):
    id: str
    analysis_id: str
    parent_ids: list[str] = Field(default_factory=list)
    title: str
    description: str = ""
    depth: int = 0
    status: ScenarioStatus = ScenarioStatus.exploring
    domain: str = "general"
    conditions: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    causes: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    consequences: list[str] = Field(default_factory=list)
    time_horizon: TimeHorizon = Field(default_factory=TimeHorizon)
    probability: ProbabilityObject = Field(default_factory=ProbabilityObject)
    impact: ImpactObject = Field(default_factory=ImpactObject)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    # Branch-prioritization dimensions kept individually (§6.2) — never one
    # opaque blended score.
    priorities: dict[str, float] = Field(default_factory=dict)
    model_version: str = "mock-1.0"
    created_at: str = Field(default_factory=utcnow)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship: RelationshipType = "MAY_CAUSE"
    label: str = ""


class ScenarioGraph(BaseModel):
    analysis_id: str
    nodes: dict[str, Possibility] = Field(default_factory=dict)
    edges: list[GraphEdge] = Field(default_factory=list)

    def edge_ids(self) -> set[str]:
        return {e.id for e in self.edges}


# ---------------------------------------------------------------------------
# Initial state object (output of Intent Understanding, §2.A)
# ---------------------------------------------------------------------------

class InitialState(BaseModel):
    decision: str
    goal: str | None = None
    constraints: list[str] = Field(default_factory=list)
    known_facts: list[str] = Field(default_factory=list)
    time_horizon: TimeHorizon = Field(default_factory=TimeHorizon)
    requested_depth: int | None = None


class Analysis(BaseModel):
    id: str
    created_at: str = Field(default_factory=utcnow)
    status: AnalysisStatus = AnalysisStatus.created
    initial_state: InitialState
    domains: list[str] = Field(default_factory=list)
    summary: str | None = None
    error: str | None = None
    # Exploration bookkeeping
    unexplored_branches: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Events (§9)
# ---------------------------------------------------------------------------

EventType = Literal[
    "analysis_started",
    "context_required",
    "context_received",
    "domain_identified",
    "possibility_discovered",
    "possibility_validated",
    "branch_expanded",
    "estimate_updated",
    "simulation_completed",
    "evidence_added",
    "branch_completed",
    "analysis_completed",
    "analysis_failed",
    "analysis_cancelled",
]


class AnalysisEvent(BaseModel):
    event_id: str
    sequence: int
    event_type: EventType
    analysis_id: str
    node_id: str | None = None
    parent_ids: list[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=utcnow)
    payload: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# API request/response contracts
# ---------------------------------------------------------------------------

class CreateAnalysisRequest(BaseModel):
    decision: str = Field(min_length=3, max_length=4000)
    goal: str | None = None
    constraints: list[str] = Field(default_factory=list)
    known_facts: list[str] = Field(default_factory=list)
    time_horizon: TimeHorizon = Field(default_factory=TimeHorizon)
    max_depth: int | None = Field(default=None, ge=1, le=6)
    idempotency_key: str | None = None


class WhatIfRequest(BaseModel):
    modification: str = Field(min_length=2, max_length=2000)
    assumption_change: str | None = None


class GraphSnapshot(BaseModel):
    analysis: Analysis
    graph: ScenarioGraph
    latest_sequence: int
