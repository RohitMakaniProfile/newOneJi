from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.api.devops_routes import router as devops_router
from app.core.event_bus import EventBus
from app.core.tools import ToolRegistry
from app.storage.store import Store
from app.routes.llm_test import router as llm_test_router


def _get_db_path() -> str:
    # Allow overriding DB location via env, default local file
    return os.getenv("STAKPAK_DB_PATH", "./data.db")


def _get_cors_origins() -> list[str]:
    """
    Comma-separated origins:
      STAKPAK_CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000"
    """
    raw = os.getenv("STAKPAK_CORS_ORIGINS", "")
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return origins


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan is the right place to initialize and clean up app-wide resources.
    """
    # --- startup ---
    app.state.store = Store(path=_get_db_path())
    app.state.bus = EventBus()
    app.state.registry = ToolRegistry()
    app.state.runners: Dict[str, Any] = {}  # session_id -> SessionRunner

    yield

    # --- shutdown ---
    # If your Store has a close() (sqlite connections etc), call it.
    store = getattr(app.state, "store", None)
    close_fn = getattr(store, "close", None)
    if callable(close_fn):
        close_fn()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Stakpak Python Agent",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS – allow all origins so the frontend (different port) can connect
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routers
    # IMPORTANT:
    # Keep these prefixes consistent with your frontend calls.
    # Your log indicates frontend calls /api/... and /healthz, so no prefix here.
    app.include_router(api_router)
    app.include_router(llm_test_router)
    app.include_router(devops_router)

    # Root endpoint so GET / doesn't 404 (your log shows GET / -> 404)
    @app.get("/")
    async def root():
        return {
            "name": "Stakpak Python Agent",
            "status": "ok",
            "docs": "/docs",
            "health": "/healthz",
        }

    return app


app = create_app()
