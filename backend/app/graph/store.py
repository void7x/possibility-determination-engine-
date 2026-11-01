"""In-memory graph store with structural validation (§5, §15 scenario tests).

This is the vertical-slice implementation of the storage seam. The public
surface (add_node, add_edge, snapshot) is what the PostgreSQL-backed store of
§5.4 will implement later — orchestration code does not change.
"""

from __future__ import annotations

import threading

from pydantic import ValidationError

from app.graph.models import (
    Analysis,
    GraphEdge,
    Possibility,
    ScenarioGraph,
    ScenarioStatus,
)


class GraphValidationError(Exception):
    pass


class GraphStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._analyses: dict[str, Analysis] = {}
        self._graphs: dict[str, ScenarioGraph] = {}
        self._idempotency: dict[str, str] = {}  # key -> analysis_id

    # -- analyses ----------------------------------------------------------

    def create_analysis(self, analysis: Analysis, idempotency_key: str | None = None) -> Analysis:
        with self._lock:
            if idempotency_key and idempotency_key in self._idempotency:
                existing_id = self._idempotency[idempotency_key]
                return self._analyses[existing_id]
            self._analyses[analysis.id] = analysis
            self._graphs[analysis.id] = ScenarioGraph(analysis_id=analysis.id)
            if idempotency_key:
                self._idempotency[idempotency_key] = analysis.id
            return analysis

    def get_analysis(self, analysis_id: str) -> Analysis | None:
        return self._analyses.get(analysis_id)

    def update_analysis(self, analysis_id: str, **fields) -> Analysis:
        with self._lock:
            analysis = self._analyses[analysis_id]
            for key, value in fields.items():
                setattr(analysis, key, value)
            return analysis

    def analyses(self) -> list[Analysis]:
        return list(self._analyses.values())

    # -- graph -------------------------------------------------------------

    def get_graph(self, analysis_id: str) -> ScenarioGraph:
        return self._graphs[analysis_id]

    def node_count(self, analysis_id: str) -> int:
        return len(self._graphs[analysis_id].nodes)

    def add_node(self, analysis_id: str, node: Possibility) -> Possibility:
        with self._lock:
            graph = self._graphs[analysis_id]
            if node.id in graph.nodes:
                raise GraphValidationError(f"duplicate node id {node.id}")
            for parent_id in node.parent_ids:
                if parent_id not in graph.nodes:
                    raise GraphValidationError(
                        f"node {node.id} references missing parent {parent_id}"
                    )
            if node.id in node.parent_ids:
                raise GraphValidationError("self-parenting is not allowed")
            graph.nodes[node.id] = node
            return node

    def add_edge(self, analysis_id: str, edge: GraphEdge) -> GraphEdge:
        with self._lock:
            graph = self._graphs[analysis_id]
            if edge.source not in graph.nodes or edge.target not in graph.nodes:
                raise GraphValidationError(
                    f"edge {edge.id} references unknown node(s): "
                    f"{edge.source} -> {edge.target}"
                )
            if edge.source == edge.target:
                raise GraphValidationError("self-edges are not allowed")
            if edge.id in graph.edge_ids():
                raise GraphValidationError(f"duplicate edge id {edge.id}")
            # Event-path acyclicity (§5.1): forbid cycles along event-flow
            # edges. Cross-reference edges (ALTERNATIVE_TO / MODIFIES /
            # CONTRADICTS) legitimately point backwards and are exempt.
            event_flow = {"MAY_CAUSE", "LEADS_TO", "REQUIRES", "DEPENDS_ON",
                          "PREVENTS", "CONVERGES_WITH"}
            if edge.relationship in event_flow and self._creates_cycle(
                graph, edge.source, edge.target
            ):
                raise GraphValidationError(
                    f"edge {edge.source} -> {edge.target} would create a cycle"
                )
            graph.edges.append(edge)
            return edge

    @staticmethod
    def _creates_cycle(graph: ScenarioGraph, source: str, target: str) -> bool:
        # A cycle exists if `source` is reachable from `target` following edges
        adjacency: dict[str, list[str]] = {}
        for e in graph.edges:
            adjacency.setdefault(e.source, []).append(e.target)
        stack = [target]
        seen: set[str] = set()
        while stack:
            current = stack.pop()
            if current == source:
                return True
            if current in seen:
                continue
            seen.add(current)
            stack.extend(adjacency.get(current, []))
        return False

    def update_node(self, analysis_id: str, node_id: str, **fields) -> Possibility:
        with self._lock:
            node = self._graphs[analysis_id].nodes[node_id]
            for key, value in fields.items():
                setattr(node, key, value)
            return node

    def get_node(self, analysis_id: str, node_id: str) -> Possibility | None:
        graph = self._graphs.get(analysis_id)
        if not graph:
            return None
        return graph.nodes.get(node_id)

    def validate_graph(self, analysis_id: str) -> list[str]:
        """Return a list of structural problems (empty list == valid)."""
        graph = self._graphs[analysis_id]
        problems: list[str] = []
        node_ids = set(graph.nodes)
        for edge in graph.edges:
            if edge.source not in node_ids:
                problems.append(f"edge {edge.id}: missing source {edge.source}")
            if edge.target not in node_ids:
                problems.append(f"edge {edge.id}: missing target {edge.target}")
        for node in graph.nodes.values():
            for parent in node.parent_ids:
                if parent not in node_ids:
                    problems.append(f"node {node.id}: missing parent {parent}")
            if node.status == ScenarioStatus.validated and not node.title.strip():
                problems.append(f"node {node.id}: validated without title")
            p = node.probability
            if p.status.value == "unquantified" and p.estimate is not None:
                problems.append(f"node {node.id}: unquantified but has estimate")
        # duplicate titles among siblings (dedup check, §2.D)
        seen: dict[tuple[str | None, str], str] = {}
        for node in graph.nodes.values():
            parent_key = (node.parent_ids[0] if node.parent_ids else None, node.title.strip().lower())
            if parent_key in seen:
                problems.append(
                    f"node {node.id}: duplicate of {seen[parent_key]} under same parent"
                )
            else:
                seen[parent_key] = node.id
        return problems
