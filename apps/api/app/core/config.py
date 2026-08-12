"""Typed application settings (Prompt 3).

Every field is required (no default) unless the variable is genuinely
optional in every environment, so a missing .env value fails app startup
immediately instead of surfacing as a confusing runtime error later.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Teenure API"
    environment: str = "development"

    # Supabase
    next_public_supabase_url: str
    next_public_supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str
    database_url: str

    # Parent Portal (Prompt 4A / Section 9A) -- parents have no Supabase
    # auth.users identity, so their session tokens are signed separately
    # from supabase_jwt_secret via this dedicated HS256 secret.
    parent_session_secret: str

    # Stripe
    stripe_secret_key: str
    stripe_publishable_key: str
    stripe_webhook_secret: str
    stripe_platform_fee_percent: int = Field(ge=1, le=100)

    # Resend
    resend_api_key: str
    resend_from_email: str
    resend_parent_consent_template_id: str
    resend_parent_magic_link_template_id: str = "placeholder-template-id"
    resend_parent_digest_template_id: str = "placeholder-template-id"

    # App
    next_public_app_url: str
    api_url: str
    admin_secret_key: str
    allowed_origins: str

    # Scheduled jobs
    jobs_runner_secret: str

    # Feature flags / compliance thresholds (Section 9 age gate)
    min_rep_age: int
    parental_consent_required_under: int

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached so the whole process shares one validated Settings instance.

    Instantiating Settings() is what triggers pydantic-settings' env
    loading/validation, so any missing required variable raises here,
    at first access (app startup), not deep inside a request handler.
    """
    return Settings()
