"""App-factory entrypoint for the Teenure FastAPI backend.

Deliberately not a bare module-level `FastAPI()` instance — using a
factory (`create_app`) lets tests inject different config via
dependency overrides on `get_settings` without import-time side
effects.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.db.pool import close_pool, init_pool
from app.jobs.runner import router as jobs_router
from app.routers import auth, health, parent, parent_auth


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await init_pool(settings)
        try:
            yield
        finally:
            await close_pool()

    app = FastAPI(title="Teenure API", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(jobs_router)
    app.include_router(auth.router)
    app.include_router(parent_auth.router)
    app.include_router(parent.router)

    return app


app = create_app()
