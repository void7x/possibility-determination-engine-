"""Event bus with persistence-before-publication semantics (§9).

Every analysis has an append-only, sequenced event log. Live subscribers get
events through per-subscriber queues; late subscribers replay from the log
using a Last-Event-ID style cursor. The frontend never invents events.
"""

from __future__ import annotations

import asyncio
import fnmatch
import uuid
from typing import AsyncIterator

from app.graph.models import AnalysisEvent, EventType


class EventLog:
    """Persisted, ordered event history for a single analysis."""

    def __init__(self, retention: int = 2000) -> None:
        self._events: list[AnalysisEvent] = []
        self._retention = retention

    @property
    def latest_sequence(self) -> int:
        return self._events[-1].sequence if self._events else 0

    def append(self, event: AnalysisEvent) -> AnalysisEvent:
        self._events.append(event)
        if len(self._events) > self._retention:
            self._events = self._events[-self._retention:]
        return event

    def since(self, last_sequence: int) -> list[AnalysisEvent]:
        return [e for e in self._events if e.sequence > last_sequence]


class EventBus:
    """In-process fan-out bus. Persist first, then publish."""

    def __init__(self, retention: int = 2000) -> None:
        self._logs: dict[str, EventLog] = {}
        self._subscribers: dict[str, set[asyncio.Queue[AnalysisEvent | None]]] = {}
        self._retention = retention

    # -- log management ----------------------------------------------------

    def log_for(self, analysis_id: str) -> EventLog:
        if analysis_id not in self._logs:
            self._logs[analysis_id] = EventLog(self._retention)
        return self._logs[analysis_id]

    def latest_sequence(self, analysis_id: str) -> int:
        return self.log_for(analysis_id).latest_sequence

    # -- publish -----------------------------------------------------------

    async def publish(
        self,
        *,
        analysis_id: str,
        event_type: EventType,
        node_id: str | None = None,
        parent_ids: list[str] | None = None,
        payload: dict | None = None,
    ) -> AnalysisEvent:
        log = self.log_for(analysis_id)
        event = AnalysisEvent(
            event_id=f"evt_{uuid.uuid4().hex[:10]}",
            sequence=log.latest_sequence + 1,
            event_type=event_type,  # type: ignore[arg-type]
            analysis_id=analysis_id,
            node_id=node_id,
            parent_ids=parent_ids or [],
            payload=payload or {},
        )
        # Persist before publication (§9.1)
        log.append(event)
        for queue in list(self._subscribers.get(analysis_id, ())):
            await queue.put(event)
        return event

    # -- subscribe ---------------------------------------------------------

    async def subscribe(
        self, analysis_id: str, last_event_id: int = 0
    ) -> AsyncIterator[AnalysisEvent]:
        """Yield historical events then live events until cancelled."""
        queue: asyncio.Queue[AnalysisEvent | None] = asyncio.Queue()
        self._subscribers.setdefault(analysis_id, set()).add(queue)
        try:
            for event in self.log_for(analysis_id).since(last_event_id):
                yield event
            while True:
                event = await queue.get()
                if event is None:
                    return
                if event.sequence > last_event_id:
                    yield event
        finally:
            self._subscribers.get(analysis_id, set()).discard(queue)

    async def close_analysis(self, analysis_id: str) -> None:
        for queue in list(self._subscribers.get(analysis_id, ())):
            await queue.put(None)


def sse_frame(event: AnalysisEvent) -> str:
    """Render an AnalysisEvent as an SSE frame with id: for replay."""
    data = event.model_dump_json()
    return (
        f"id: {event.sequence}\n"
        f"event: {event.event_type}\n"
        f"data: {data}\n\n"
    )
