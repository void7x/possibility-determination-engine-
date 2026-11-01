"""Backend slice tests: graph integrity, probability honesty, reproducibility,
event sequencing, what-if preservation (§15, §16)."""

from __future__ import annotations

import asyncio

import pytest

from app.core.events import EventBus
from app.core.orchestrator import Orchestrator
from app.graph.models import GraphEdge, InitialState, Possibility, new_id
from app.graph.store import GraphStore, GraphValidationError
from app.providers.mock import MockProvider
from app.simulation.engine import simulate_cash_runway


@pytest.fixture()
def store() -> GraphStore:
    return GraphStore()


def _node(analysis_id: str, node_id: str, title: str, parents: list[str] | None = None) -> Possibility:
    return Possibility(
        id=node_id, analysis_id=analysis_id, title=title, parent_ids=parents or []
    )


# -- Graph integrity -------------------------------------------------------

def test_missing_parent_rejected(store: GraphStore):
    analysis_id = "a1"
    store.create_analysis(
        __import__("app.graph.models", fromlist=["Analysis"]).Analysis(
            id=analysis_id, initial_state=InitialState(decision="test")
        )
    )
    with pytest.raises(GraphValidationError):
        store.add_node(analysis_id, _node(analysis_id, "n1", "orphan", ["ghost"]))


def test_edge_requires_existing_nodes(store: GraphStore):
    from app.graph.models import Analysis

    analysis_id = "a1"
    store.create_analysis(Analysis(id=analysis_id, initial_state=InitialState(decision="t")))
    store.add_node(analysis_id, _node(analysis_id, "n1", "root"))
    with pytest.raises(GraphValidationError):
        store.add_edge(
            analysis_id,
            GraphEdge(id="e1", source="n1", target="ghost", relationship="MAY_CAUSE"),
        )


def test_event_flow_cycle_rejected_but_cross_refs_allowed(store: GraphStore):
    from app.graph.models import Analysis

    analysis_id = "a1"
    store.create_analysis(Analysis(id=analysis_id, initial_state=InitialState(decision="t")))
    store.add_node(analysis_id, _node(analysis_id, "n1", "root"))
    store.add_node(analysis_id, _node(analysis_id, "n2", "child", ["n1"]))
    store.add_edge(analysis_id, GraphEdge(id="e1", source="n1", target="n2", relationship="LEADS_TO"))
    with pytest.raises(GraphValidationError):
        store.add_edge(analysis_id, GraphEdge(id="e2", source="n2", target="n1", relationship="MAY_CAUSE"))
    # cross-reference backwards edge is fine
    store.add_edge(
        analysis_id,
        GraphEdge(id="e3", source="n2", target="n1", relationship="MODIFIES"),
    )


# -- Probability honesty ---------------------------------------------------

def test_unquantified_probability_rejects_estimate():
    from app.graph.models import ProbabilityObject

    with pytest.raises(ValueError):
        ProbabilityObject(status="unquantified", estimate=0.4)


def test_quantified_probability_requires_method():
    from app.graph.models import ProbabilityObject

    with pytest.raises(ValueError):
        ProbabilityObject(status="quantified", estimate=0.4)


def test_simulation_is_deterministic_and_disclosed():
    r1 = simulate_cash_runway("a", "n")
    r2 = simulate_cash_runway("a", "n")
    assert r1.estimate == r2.estimate
    assert r1.estimate is not None and 0.0 <= r1.estimate <= 1.0
    assert len(r1.assumptions) >= 4
    assert r1.kind == "cash_runway"


# -- Orchestration end-to-end ---------------------------------------------

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.mark.asyncio
async def test_full_analysis_reproducible_and_honest():
    store, bus = GraphStore(), EventBus()
    orch = Orchestrator(store, bus, MockProvider())
    decision = "Should we migrate our production servers to a new cloud provider?"
    a1 = await orch.start_analysis(InitialState(decision=decision), auto_run=False)
    a2 = await orch.start_analysis(InitialState(decision=decision), auto_run=False)
    await asyncio.gather(orch._run(a1.id), orch._run(a2.id))

    g1, g2 = store.get_graph(a1.id), store.get_graph(a2.id)
    assert len(g1.nodes) == len(g2.nodes) >= 5
    titles1 = sorted(n.title for n in g1.nodes.values())
    titles2 = sorted(n.title for n in g2.nodes.values())
    assert titles1 == titles2  # reproducibility with fixed inputs
    for node in g1.nodes.values():
        p = node.probability
        if p.status.value == "unquantified":
            assert p.estimate is None
    # event log sequencing
    log = bus.log_for(a1.id)
    seqs = [e.sequence for e in log.since(0)]
    assert seqs == list(range(1, len(seqs) + 1))
    assert any(e.event_type == "analysis_completed" for e in log.since(0))


@pytest.mark.asyncio
async def test_what_if_preserves_original():
    store, bus = GraphStore(), EventBus()
    orch = Orchestrator(store, bus, MockProvider())
    analysis = await orch.start_analysis(
        InitialState(decision="Should I quit my job to study full-time?"),
        auto_run=False,
    )
    await orch._run(analysis.id)
    graph = store.get_graph(analysis.id)
    target = next(n for n in graph.nodes.values() if n.depth == 1)
    original_titles = {n.title for n in graph.nodes.values()}
    alt = await orch.create_what_if(
        analysis.id, target.id, "I keep my job but study part-time", None
    )
    graph_after = store.get_graph(analysis.id)
    assert original_titles <= {n.title for n in graph_after.nodes.values()}  # original intact
    assert alt.status.value == "alternative"
    assert alt.probability.estimate is None  # honest: unquantified
    assert any(e.relationship == "MODIFIES" for e in graph_after.edges)
