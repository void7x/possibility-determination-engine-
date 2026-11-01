"""REST + SSE API surface (§10, §9).

Slice notes: authentication/authorization hooks are present as dependencies
but permissive in local single-user mode; the production Phase-8 hardening
replaces them without changing route contracts.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.core.events import EventBus, sse_frame
from app.core.orchestrator import Orchestrator
from app.graph.models import (
    Analysis,
    CreateAnalysisRequest,
    GraphSnapshot,
    InitialState,
    Possibility,
    WhatIfRequest,
)
from app.graph.store import GraphStore, GraphValidationError
from app.providers.base import LLMProvider

router = APIRouter(prefix="/v1")


# ---------------------------------------------------------------------------
# Composition (single FastAPI app owns the composition root for the slice)
# ---------------------------------------------------------------------------

class AppState:
    store: GraphStore
    bus: EventBus
    orchestrator: Orchestrator
    provider: LLMProvider


def get_state(request: Request) -> AppState:
    return request.app.state.pie


async def require_analysis(state: AppState, analysis_id: str) -> Analysis:
    analysis = state.store.get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    return analysis


# ---------------------------------------------------------------------------
# Analyses
# ---------------------------------------------------------------------------

@router.post("/analyses", status_code=202)
async def create_analysis(
    body: CreateAnalysisRequest, state: AppState = Depends(get_state)
) -> dict:
    initial = InitialState(
        decision=body.decision,
        goal=body.goal,
        constraints=body.constraints,
        known_facts=body.known_facts,
        time_horizon=body.time_horizon,
        requested_depth=body.max_depth,
    )
    analysis = await state.orchestrator.start_analysis(
        initial, idempotency_key=body.idempotency_key
    )
    return {"analysis_id": analysis.id, "status": analysis.status.value}


@router.get("/analyses")
async def list_analyses(state: AppState = Depends(get_state)) -> list[dict]:
    return [
        {
            "id": a.id,
            "status": a.status.value,
            "decision": a.initial_state.decision,
            "created_at": a.created_at,
            "domains": a.domains,
        }
        for a in sorted(state.store.analyses(), key=lambda a: a.created_at, reverse=True)
    ]


@router.get("/analyses/{analysis_id}")
async def get_analysis(analysis_id: str, state: AppState = Depends(get_state)) -> Analysis:
    try:
        return await require_analysis(state, analysis_id)
    except HTTPException:
        raise


@router.get("/analyses/{analysis_id}/graph")
async def get_graph(analysis_id: str, state: AppState = Depends(get_state)) -> GraphSnapshot:
    try:
        analysis = await require_analysis(state, analysis_id)
    except HTTPException:
        raise
    return GraphSnapshot(
        analysis=analysis,
        graph=state.store.get_graph(analysis_id),
        latest_sequence=state.bus.latest_sequence(analysis_id),
    )


@router.get("/analyses/{analysis_id}/events")
async def stream_events(
    analysis_id: str,
    request: Request,
    last_event_id: int | None = Query(default=None, alias="last_event_id"),
    state: AppState = Depends(get_state),
):
    """SSE stream. Supports Last-Event-ID header (native EventSource
    reconnects) and a last_event_id query param for initial catch-up."""
    try:
        await require_analysis(state, analysis_id)
    except HTTPException:
        raise
    header_cursor = request.headers.get("last-event-id")
    cursor = int(header_cursor) if header_cursor and header_cursor.isdigit() else (last_event_id or 0)

    async def event_generator():
        iterator = state.bus.subscribe(analysis_id, last_event_id=cursor)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(iterator.__anext__(), timeout=15.0)
                except asyncio.TimeoutError:
                    # keep-alive comment so proxies don't kill the stream
                    yield ": keep-alive\n\n"
                    continue
                yield sse_frame(event)
                # The stream stays open after terminal events so later user
                # actions (branch expansion, what-if) keep streaming into the
                # same exploration session.
        finally:
            await iterator.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/analyses/{analysis_id}/cancel")
async def cancel_analysis(analysis_id: str, state: AppState = Depends(get_state)) -> dict:
    try:
        await require_analysis(state, analysis_id)
    except HTTPException:
        raise
    accepted = state.orchestrator.request_cancel(analysis_id)
    return {"cancelled": accepted}


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

@router.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str, state: AppState = Depends(get_state)) -> Possibility:
    for analysis in state.store.analyses():
        node = state.store.get_node(analysis.id, scenario_id)
        if node is not None:
            return node
    raise HTTPException(status_code=404, detail="scenario not found")


@router.post("/scenarios/{scenario_id}/expand", status_code=202)
async def expand_scenario(
    scenario_id: str, state: AppState = Depends(get_state)
) -> dict:
    analysis_id, node = _find_scenario(state, scenario_id)
    if node.depth >= 4:
        raise HTTPException(status_code=400, detail="maximum depth reached for this branch")
    try:
        await state.orchestrator.expand_branch(analysis_id, scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"expanded": scenario_id, "analysis_id": analysis_id}


@router.post("/scenarios/{scenario_id}/what-if", status_code=202)
async def what_if(
    scenario_id: str, body: WhatIfRequest, state: AppState = Depends(get_state)
) -> dict:
    analysis_id, _ = _find_scenario(state, scenario_id)
    alternative = await state.orchestrator.create_what_if(
        analysis_id, scenario_id, body.modification, body.assumption_change
    )
    return {
        "alternative_id": alternative.id,
        "analysis_id": analysis_id,
        "based_on": scenario_id,
    }


def _find_scenario(state: AppState, scenario_id: str):
    for analysis in state.store.analyses():
        node = state.store.get_node(analysis.id, scenario_id)
        if node is not None:
            return analysis.id, node
    raise HTTPException(status_code=404, detail="scenario not found")


# ---------------------------------------------------------------------------
# System / provider introspection (§3.3)
# ---------------------------------------------------------------------------

@router.get("/system/health")
async def health(state: AppState = Depends(get_state)) -> dict:
    provider_ok = await state.provider.health_check()
    capabilities = await state.provider.get_capabilities()
    return {
        "status": "ok" if provider_ok else "degraded",
        "provider": capabilities.model_dump(),
        "analyses": len(state.store.analyses()),
    }
