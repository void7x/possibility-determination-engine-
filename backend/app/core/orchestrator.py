"""Analysis orchestrator (§2 core pipeline, §6 recursive exploration workflow).

Runs each analysis as a background task:

    understand → resolve domain → discover → validate → build graph →
    attach evidence/assumptions → estimate/simulate where defensible →
    complete with explicit unexplored markers.

Every transition emits a real event to the event bus. Pacing pauses make the
exploration space watchable; they never fabricate results.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.config import settings
from app.core.events import EventBus
from app.domains.resolver import display_name, resolve_domains
from app.graph.models import (
    Analysis,
    AnalysisStatus,
    Assumption,
    EvidenceRef,
    GraphEdge,
    InitialState,
    Possibility,
    ProbabilityObject,
    ScenarioStatus,
    new_id,
)
from app.graph.store import GraphStore
from app.providers.base import LLMProvider, ProviderMessage
from app.simulation.engine import simulate_cash_runway

logger = logging.getLogger("pie.orchestrator")


class Orchestrator:
    def __init__(self, store: GraphStore, bus: EventBus, provider: LLMProvider) -> None:
        self.store = store
        self.bus = bus
        self.provider = provider
        self._tasks: dict[str, asyncio.Task] = {}
        self._cancel_flags: set[str] = set()

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------

    async def start_analysis(
        self, initial_state: InitialState, idempotency_key: str | None = None, auto_run: bool = True
    ) -> Analysis:
        analysis = Analysis(id=new_id("analysis"), initial_state=initial_state)
        self.store.create_analysis(analysis, idempotency_key=idempotency_key)
        if auto_run:
            task = asyncio.create_task(self._run(analysis.id))
            self._tasks[analysis.id] = task
        return analysis

    def request_cancel(self, analysis_id: str) -> bool:
        analysis = self.store.get_analysis(analysis_id)
        if not analysis or analysis.status in {
            AnalysisStatus.completed,
            AnalysisStatus.cancelled,
            AnalysisStatus.failed,
        }:
            return False
        self._cancel_flags.add(analysis_id)
        return True

    async def expand_branch(self, analysis_id: str, node_id: str) -> Possibility:
        analysis = self._require_analysis(analysis_id)
        parent = self.store.get_node(analysis_id, node_id)
        if parent is None:
            raise KeyError(f"scenario {node_id} not found")
        if parent.depth + 1 >= settings.max_graph_depth:
            raise ValueError(
                f"maximum exploration depth ({settings.max_graph_depth}) reached for this branch"
            )
        if self.store.node_count(analysis_id) >= settings.max_nodes_per_analysis:
            raise ValueError("analysis node limit reached; start a new analysis to go deeper")

        await self.bus.publish(
            analysis_id=analysis_id,
            event_type="branch_expanded",
            node_id=node_id,
            parent_ids=parent.parent_ids,
            payload={"title": parent.title, "depth": parent.depth},
        )
        children = await self._generate_children(analysis, parent)
        for child in children:
            await self._admit_possibility(analysis, child, parent_ids=[node_id])
        self.store.update_node(
            analysis_id,
            node_id,
            status=ScenarioStatus.validated
            if parent.status != ScenarioStatus.alternative
            else ScenarioStatus.alternative,
        )
        if not children:
            await self.bus.publish(
                analysis_id=analysis_id,
                event_type="context_required",
                node_id=node_id,
                payload={
                    "reason": "no_further_children_in_template_corpus",
                    "detail": (
                        "This branch has no deeper template coverage yet; the "
                        "branch is marked for future exploration."
                    ),
                },
            )
        await self._mark_unexplored_children(analysis_id, node_id)
        return parent

    async def create_what_if(
        self, analysis_id: str, node_id: str, modification: str, assumption_change: str | None
    ) -> Possibility:
        analysis = self._require_analysis(analysis_id)
        base = self.store.get_node(analysis_id, node_id)
        if base is None:
            raise KeyError(f"scenario {node_id} not found")

        alternative = Possibility(
            id=new_id("scenario"),
            analysis_id=analysis_id,
            parent_ids=base.parent_ids or [],
            title=f"What-if: {modification[:80]}",
            description=(
                f"Alternative to “{base.title}” under a modified assumption. "
                f"The original scenario is preserved unchanged."
            ),
            depth=base.depth + 1,
            status=ScenarioStatus.alternative,
            domain=base.domain,
            conditions=[f"User-modified condition: {modification}"],
            triggers=["What-if initiated by the user"],
            causes=[f"Counterfactual modification of assumptions around “{base.title}”"],
            dependencies=[f"Derived from scenario {base.id}"],
            consequences=["Re-evaluation of downstream outcomes under the new assumption"],
            time_horizon=base.time_horizon.model_copy(),
            probability=ProbabilityObject(status="unquantified"),
            impact=base.impact.model_copy(),
            evidence=[
                EvidenceRef(
                    kind="user_fact",
                    claim=modification,
                    provenance="user what-if input",
                )
            ],
            assumptions=[
            Assumption(
                statement=assumption_change
                or f"Assumption replaced: {modification}",
                is_blocking=True,
            ),
            Assumption(statement="All other assumptions of the base scenario hold"),
        ],
        priorities={**base.priorities},
        model_version=self.provider.name,
        )

        await self.bus.publish(
            analysis_id=analysis_id,
            event_type="branch_expanded",
            node_id=base.id,
            parent_ids=base.parent_ids,
            payload={"what_if": True, "title": base.title},
        )
        await self._admit_possibility(
            analysis, alternative, parent_ids=[base.id], edge_relationship="ALTERNATIVE_TO"
        )
        self.store.add_edge(
            analysis_id,
            GraphEdge(
                id=new_id("edge"),
                source=alternative.id,
                target=base.id,
                relationship="MODIFIES",
                label="modified assumption",
            ),
        )
        return alternative

    # ------------------------------------------------------------------
    # Main exploration loop
    # ------------------------------------------------------------------

    async def _run(self, analysis_id: str) -> None:
        analysis = self.store.get_analysis(analysis_id)
        try:
            self.store.update_analysis(analysis_id, status=AnalysisStatus.running)
            await self.bus.publish(
                analysis_id=analysis_id,
                event_type="analysis_started",
                payload={
                    "decision": analysis.initial_state.decision,
                    "goal": analysis.initial_state.goal,
                },
            )
            await self._pace()

            # --- Understand + resolve domains (§2.A, §2.C) -----------------
            scored = resolve_domains(analysis.initial_state.decision)
            domains = [d for d, _ in scored]
            self.store.update_analysis(analysis_id, domains=domains)
            await self.bus.publish(
                analysis_id=analysis_id,
                event_type="domain_identified",
                payload={
                    "primary": display_name(domains[0]),
                    "all": [
                        {"domain": display_name(d), "score": s} for d, s in scored
                    ],
                    "variables": "see discovery payload",
                },
            )
            await self._pace()

            # --- Discover initial possibilities (§2.D) ---------------------
            result = await self.provider.generate(
                [ProviderMessage(role="user", content=analysis.initial_state.decision)],
                model_config={
                    "task": "discover",
                    "decision": analysis.initial_state.decision,
                },
            )
            structured = result.structured or {}
            root = Possibility(
                id=new_id("scenario"),
                analysis_id=analysis_id,
                title=analysis.initial_state.decision.strip(),
                description="Initial decision / situation submitted by the user.",
                depth=0,
                status=ScenarioStatus.validated,
                domain=structured.get("domain", domains[0]),
                conditions=["As stated in the initial input"],
                time_horizon=analysis.initial_state.time_horizon,
                evidence=[
                    EvidenceRef(kind="user_fact", claim=analysis.initial_state.decision,
                                provenance="user input")
                ],
                model_version=result.model,
            )
            self.store.add_node(analysis_id, root)
            await self.bus.publish(
                analysis_id=analysis_id,
                event_type="possibility_discovered",
                node_id=root.id,
                payload={"title": root.title, "depth": 0, "status": root.status.value,
                         "is_root": True},
            )
            await self.bus.publish(
                analysis_id=analysis_id,
                event_type="possibility_validated",
                node_id=root.id,
                payload={"title": root.title},
            )
            await self._pace(1.1)

            # --- Admit first-level possibilities ---------------------------
            candidates = (structured.get("possibilities") or [])[: settings.beam_width]
            for candidate in candidates:
                await self._admit_possibility(
                    analysis, self._to_possibility(analysis, root, result.model, candidate),
                    parent_ids=[root.id],
                )
                await self._pace()

            # --- Completion -------------------------------------------------
            problems = self.store.validate_graph(analysis_id)
            if problems:
                logger.warning("graph validation issues: %s", problems)
            self.store.update_analysis(
                analysis_id,
                status=AnalysisStatus.completed,
                summary=(
                    f"Explored {self.store.node_count(analysis_id)} scenarios across "
                    f"{len(domains)} domain(s). Unexplored branches are marked explicitly."
                ),
            )
            await self.bus.publish(
                analysis_id=analysis_id,
                event_type="analysis_completed",
                payload={
                    "node_count": self.store.node_count(analysis_id),
                    "unexplored_branches": self._unexplored(analysis_id),
                    "validation_problems": problems,
                },
            )
        except asyncio.CancelledError:
            self.store.update_analysis(analysis_id, status=AnalysisStatus.cancelled)
            await self.bus.publish(
                analysis_id=analysis_id,
                event_type="analysis_cancelled",
                payload={"reason": "user_cancelled"},
            )
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("analysis %s failed", analysis_id)
            self.store.update_analysis(
                analysis_id, status=AnalysisStatus.failed, error=str(exc)
            )
            await self.bus.publish(
                analysis_id=analysis_id,
                event_type="analysis_failed",
                payload={"error": str(exc)},
            )
        finally:
            self._cancel_flags.discard(analysis_id)
            self._tasks.pop(analysis_id, None)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _admit_possibility(
        self,
        analysis: Analysis,
        node: Possibility,
        parent_ids: list[str],
        edge_relationship: str = "MAY_CAUSE",
    ) -> Possibility:
        analysis_id = analysis.id
        node.parent_ids = parent_ids

        if self._is_duplicate(analysis_id, node):
            return node
        if node.depth >= settings.max_graph_depth:
            node.status = ScenarioStatus.unexplored
        if self.store.node_count(analysis_id) >= settings.max_nodes_per_analysis:
            node.status = ScenarioStatus.unexplored

        self.store.add_node(analysis_id, node)
        for parent_id in parent_ids:
            self.store.add_edge(
                analysis_id,
                GraphEdge(
                    id=new_id("edge"),
                    source=parent_id,
                    target=node.id,
                    relationship=edge_relationship,  # type: ignore[arg-type]
                    label="",
                ),
            )
        await self.bus.publish(
            analysis_id=analysis_id,
            event_type="possibility_discovered",
            node_id=node.id,
            parent_ids=parent_ids,
            payload={
                "title": node.title,
                "description": node.description,
                "depth": node.depth,
                "status": node.status.value,
                "impact": node.impact.level.value,
                "time_horizon": node.time_horizon.label(),
            },
        )
        await self._pace(0.25)

        # Evidence + assumptions (§2.H)
        if node.evidence or node.assumptions:
            await self.bus.publish(
                analysis_id=analysis_id,
                event_type="evidence_added",
                node_id=node.id,
                payload={
                    "evidence": [e.model_dump() for e in node.evidence],
                    "assumptions": [a.model_dump() for a in node.assumptions],
                },
            )

        # Simulation where a defensible model exists (§2.G / §7.1)
        await self._maybe_simulate(analysis_id, node)

        if node.status == ScenarioStatus.exploring:
            node.status = ScenarioStatus.validated
        if node.status == ScenarioStatus.unexplored:
            self._mark_unexplored(analysis_id, node.id)
        await self.bus.publish(
            analysis_id=analysis_id,
            event_type="possibility_validated",
            node_id=node.id,
            payload={"title": node.title, "status": node.status.value},
        )

        await self.bus.publish(
            analysis_id=analysis_id,
            event_type="branch_completed",
            node_id=node.id,
            payload={"title": node.title, "depth": node.depth},
        )
        self.store.update_node(analysis_id, node.id)
        return node

    async def _maybe_simulate(self, analysis_id: str, node: Possibility) -> None:
        """Run the cash-runway Monte Carlo for business branches.

        Quantifies only when an explicit arithmetic model applies; the result
        is recorded as model_based with full disclosure of assumptions.
        """
        # Attach the runway model only to cash-critical business branches, and
        # only when an explicit arithmetic model is defensible.
        if node.domain != "business_operations" or node.depth == 0:
            return
        cash_related = any(
            "cash" in text.lower()
            for text in [node.title, node.description, *node.conditions, *node.consequences]
        )
        if not cash_related:
            return
        result = simulate_cash_runway(analysis_id, node.id)
        node.probability = ProbabilityObject(
            status="quantified",
            estimate=result.estimate,
            interval=result.interval,
            method="model_based",
            rationale=result.summary,
        )
        node.assumptions.extend(
            Assumption(statement=a, is_blocking=True) for a in result.assumptions
        )
        node.priorities["evidence_availability"] = max(
            node.priorities.get("evidence_availability", 0.5), 0.7
        )
        await self.bus.publish(
            analysis_id=analysis_id,
            event_type="simulation_completed",
            node_id=node.id,
            payload={
                "kind": result.kind,
                "metrics": result.metrics,
                "samples": result.samples,
                "summary": result.summary,
            },
        )
        await self.bus.publish(
            analysis_id=analysis_id,
            event_type="estimate_updated",
            node_id=node.id,
            payload={
                "probability": node.probability.model_dump(),
                "assumption_count": len(result.assumptions),
            },
        )

    def _to_possibility(
        self, analysis: Analysis, parent: Possibility, model: str, candidate: dict
    ) -> Possibility:
        prob_raw = candidate.get("probability") or {"status": "unquantified"}
        try:
            probability = ProbabilityObject(**prob_raw)
        except Exception:
            probability = ProbabilityObject(status="unquantified")
        from app.graph.models import ImpactObject, TimeHorizon

        return Possibility(
            id=new_id("scenario"),
            analysis_id=analysis.id,
            title=candidate["title"],
            description=candidate.get("description", ""),
            depth=parent.depth + 1,
            domain=candidate.get("domain") or parent.domain,
            conditions=candidate.get("conditions", []),
            triggers=candidate.get("triggers", []),
            causes=candidate.get("causes", []),
            dependencies=candidate.get("dependencies", []),
            consequences=candidate.get("consequences", []),
            time_horizon=TimeHorizon(**candidate.get("time_horizon", {})),
            probability=probability,
            impact=ImpactObject(**candidate.get("impact", {})),
            evidence=[
                EvidenceRef(
                    kind=e.get("kind", "assumption"),
                    claim=e["claim"],
                    provenance=e.get("provenance", "domain template corpus"),
                )
                for e in candidate.get("evidence", [])
            ]
            or [
                EvidenceRef(
                    kind="assumption",
                    claim="Generated from the domain template corpus; requires "
                          "user validation against their actual situation.",
                    provenance=f"provider:{model}",
                )
            ],
            assumptions=[
                Assumption(statement=a["statement"] if isinstance(a, dict) else a)
                for a in candidate.get("assumptions", [])
            ],
            priorities={k: float(v) for k, v in (candidate.get("priorities") or {}).items()},
            model_version=model,
        )

    async def _generate_children(self, analysis: Analysis, parent: Possibility) -> list[Possibility]:
        result = await self.provider.generate(
            [ProviderMessage(role="user", content=analysis.initial_state.decision)],
            model_config={
                "task": "expand",
                "decision": analysis.initial_state.decision,
                "parent": {
                    "key": _key_from_title(parent.title),
                    "id": parent.id,
                    "title": parent.title,
                    "domain": parent.domain,
                },
            },
        )
        structured = result.structured or {}
        children = []
        for candidate in (structured.get("possibilities") or [])[: settings.beam_width]:
            child = self._to_possibility(analysis, parent, result.model, candidate)
            child.depth = parent.depth + 1
            children.append(child)
        return children

    def _is_duplicate(self, analysis_id: str, node: Possibility) -> bool:
        graph = self.store.get_graph(analysis_id)
        parent_key = node.parent_ids[0] if node.parent_ids else None
        for existing in graph.nodes.values():
            existing_parent = existing.parent_ids[0] if existing.parent_ids else None
            if existing_parent == parent_key and existing.title.strip().lower() == node.title.strip().lower():
                return True
        return False

    def _mark_unexplored(self, analysis_id: str, node_id: str) -> None:
        analysis = self.store.get_analysis(analysis_id)
        if analysis and node_id not in analysis.unexplored_branches:
            analysis.unexplored_branches.append(node_id)

    async def _mark_unexplored_children(self, analysis_id: str, node_id: str) -> None:
        node = self.store.get_node(analysis_id, node_id)
        if node and not any(
            child for child in self.store.get_graph(analysis_id).nodes.values()
            if node_id in child.parent_ids and child.status != ScenarioStatus.alternative
        ):
            self._mark_unexplored(analysis_id, node_id)

    def _unexplored(self, analysis_id: str) -> list[str]:
        analysis = self.store.get_analysis(analysis_id)
        return list(analysis.unexplored_branches) if analysis else []

    def _require_analysis(self, analysis_id: str) -> Analysis:
        analysis = self.store.get_analysis(analysis_id)
        if analysis is None:
            raise KeyError(f"analysis {analysis_id} not found")
        return analysis

    async def _pace(self, factor: float = 1.0) -> None:
        await asyncio.sleep(settings.event_pace_seconds * factor)


def _key_from_title(title: str) -> str:
    """Map a validated scenario title back to its template key for expansion."""
    mapping = {
        "migration completes": "smoother_migration",
        "cutover overruns": "extended_downtime",
        "cloud spend exceeds": "cost_overrun",
        "migration temporarily weakens": "security_regression",
        "key engineers become a bottleneck": "talent_bottleneck",
        "acquisition is slower": "slow_growth",
        "early customers convert": "strong_traction",
        "cash flow tightens": "cash_strain",
        "operations strain": "operational_strain",
        "competitor responds": "competitive_response",
        "transition lands": "smooth_transition",
        "financial pressure exceeds": "financial_pressure",
        "path not taken proves costly": "opportunity_cost",
        "new skills compound": "skill_compounding",
        "identity and social strain": "identity_social_strain",
    }
    lowered = title.lower()
    for needle, key in mapping.items():
        if needle in lowered:
            return key
    return ""
