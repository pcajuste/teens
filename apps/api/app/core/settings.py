"""Minimal app settings for Prompt 1 scaffolding.

Full typed pydantic BaseSettings (failing fast on missing required env
vars, loading every variable from .env.example) is Prompt 3's
deliverable (app/core/config.py). This module only carries what the
app factory needs today: a name/version and the allowed CORS origins,
read permissively so `uvicorn` can boot with no .env file present.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:3100")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@dataclass
class Settings:
    app_name: str = "Teenure API"
    environment: str = os.getenv("ENVIRONMENT", "development")
    allowed_origins: list[str] = field(default_factory=_allowed_origins)


def get_settings() -> Settings:
    return Settings()
