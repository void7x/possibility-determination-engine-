"""PIE FastAPI application entrypoint (vertical slice)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import AppState, router
from app.core.config import settings
from app.core.events import EventBus
from app.core.orchestrator import Orchestrator
from app.graph.store import GraphStore
from app.providers.registry import build_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        registry = build_registry()
        state = AppState()
        state.store = GraphStore()
        state.bus = EventBus(retention=settings.event_log_retention)
        state.provider = registry.get()
        state.orchestrator = Orchestrator(state.store, state.bus, state.provider)
        app.state.pie = state
        capabilities = await state.provider.get_capabilities()
        logging.getLogger("pie").info(
            "PIE %s up — provider=%s model=%s",
            settings.version, capabilities.name, capabilities.model,
        )
        yield

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        lifespan=lifespan,
        docs_url="/v1/docs",
        openapi_url="/v1/openapi.json",
    )
    # The Vite dev server proxies same-origin; CORS is opened for direct use.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True, "service": "pie-backend", "version": settings.version}

    return app


app = create_app()
