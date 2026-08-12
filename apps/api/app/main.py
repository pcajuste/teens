"""App-factory entrypoint for the Teenure FastAPI backend.

Deliberately not a bare module-level `FastAPI()` instance — using a
factory (`create_app`) lets tests and future environments inject
different config (Prompt 3's typed settings) without import-time
side effects.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import get_settings
from app.routers import health


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)

    return app


app = create_app()
