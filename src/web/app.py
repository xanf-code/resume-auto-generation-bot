"""FastAPI application factory for resume-bot web layer.

Usage:
    uvicorn src.web.app:create_app --factory --reload
    uvicorn src.web.app:create_app --factory --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.web.config import WebSettings, load_settings
from src.web.job_manager import JobManager
from src.web.routers import compile as compile_router
from src.web.routers import jobs as jobs_router


def create_app() -> FastAPI:
    """Application factory - called by uvicorn --factory and test fixtures."""
    settings: WebSettings = load_settings()
    manager: JobManager = JobManager(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # Bind the running event loop so worker threads can fan out SSE events.
        manager.bind_loop(asyncio.get_running_loop())
        yield
        # Graceful shutdown: don't wait for in-flight pipeline jobs.
        manager._executor.shutdown(wait=False)

    app = FastAPI(
        title="resume-bot API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS - allow the Vite dev server during local development.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store shared state on the app so routers can reach it via request.app.state.
    app.state.manager = manager
    app.state.settings = settings

    # Routers - all mounted under /api.
    app.include_router(jobs_router.router, prefix="/api")
    app.include_router(compile_router.router, prefix="/api")

    # Health check endpoint.
    @app.get("/api/healthz", tags=["health"])
    async def healthz() -> dict:
        api_key_present = bool(os.environ.get("OPENROUTER_API_KEY", "").strip())
        active_jobs = sum(
            1
            for j in manager.list()
            if j.status.value in ("queued", "running")
        )
        return {
            "status": "ok",
            "api_key_present": api_key_present,
            "active_jobs": active_jobs,
            "max_concurrent": settings.max_concurrent_jobs,
        }

    # Mount built frontend (added after /api routes so API takes priority).
    # Conditional on dist existing so tests pass without a frontend build.
    _dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if _dist.is_dir():
        app.mount("/", StaticFiles(directory=str(_dist), html=True), name="spa")

    return app
