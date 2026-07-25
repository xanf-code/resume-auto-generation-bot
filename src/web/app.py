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

from src.web.config import WebSettings, load_settings, _optional_db_settings
from src.web.job_manager import JobManager
from src.web.routers import compile as compile_router
from src.web.routers import jobs as jobs_router
from src.web.routers import models as models_router


def _build_repo():
    """Build a ``ResumeRepository`` from env, or return ``None`` if unconfigured."""
    db_settings = _optional_db_settings()
    if db_settings is None:
        return None
    try:
        from src.db.client import get_client
        from src.db.repository import ResumeRepository
        return ResumeRepository(get_client(db_settings), db_settings)
    except Exception:
        return None


def _rehydrate_registry(manager: JobManager, repo) -> None:
    """Populate the in-memory registry from persisted DB records on startup."""
    try:
        from src.web.job import Job
        from src.web.schemas import JobStatus
        records = repo.list()
        for rec in records:
            job = Job(
                job_id=rec.job_id,
                label=rec.label,
                status=JobStatus(rec.status),
                created_at=rec.created_at,
                started_at=rec.started_at,
                finished_at=rec.finished_at,
                error=rec.error,
                resume_tex_raw=rec.resume_tex_raw,
                jd_raw=rec.jd_raw,
                jd_name=rec.jd_name,
                enable_scoring=rec.enable_scoring,
                best_latex=rec.best_latex,
                aggregate_score=rec.aggregate_score,
                passed=rec.passed,
                score_report=rec.score_report,
                output_skills=rec.output_skills,
                pdf_object_key=rec.pdf_object_key,
            )
            manager._registry[job.job_id] = job
    except Exception:
        pass  # Rehydration failure must never crash the app


def create_app(repo=None) -> FastAPI:
    """Application factory - called by uvicorn --factory and test fixtures.

    ``repo`` allows tests to inject a mock ``ResumeRepository`` without env vars.
    When ``None`` (the default), the repo is auto-built from env if configured.
    """
    settings: WebSettings = load_settings()
    if repo is None:
        repo = _build_repo()
    manager: JobManager = JobManager(settings, repo=repo)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # Bind the running event loop so worker threads can fan out SSE events.
        manager.bind_loop(asyncio.get_running_loop())
        # On startup: sweep interrupted runs to failed, then rehydrate registry.
        if repo is not None:
            try:
                repo.mark_interrupted_running()
                _rehydrate_registry(manager, repo)
            except Exception:
                pass
        yield
        # Graceful shutdown: don't wait for in-flight pipeline jobs.
        manager._executor.shutdown(wait=False)

    app = FastAPI(
        title="resume-bot API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS - configurable via RESUMEBOT_CORS_ORIGINS (comma-separated).
    # Defaults to the Vite dev origin; set the env var for split-host deploys.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
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
    app.include_router(models_router.router, prefix="/api")

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
