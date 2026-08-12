"""Typed application settings.

Loads every variable listed in the repo-root `.env.example`. Required
variables (no default in `.env.example`) cause a startup failure via
pydantic-settings' normal validation if missing — there is no silent
fallback for secrets or connection strings, per Section 9's "no client
trust" posture extended to config: a misconfigured deploy should fail
loudly at boot, not degrade at request time.

Supersedes Prompt 1's minimal `app/core/settings.py` placeholder.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"

    # ── Supabase ─────────────────────────────────────────────────
    next_public_supabase_url: str
    next_public_supabase_anon_key: str
    supabase_service_role_key: str
    database_url: str
    supabase_jwt_secret: str

    # ── Stripe ───────────────────────────────────────────────────
    stripe_secret_key: str
    stripe_publishable_key: str
    stripe_webhook_secret: str
    stripe_platform_fee_percent: int = 35

    # ── Resend ───────────────────────────────────────────────────
    resend_api_key: str
    resend_from_email: str = "noreply@teenure.com"
    resend_parent_consent_template_id: str
    resend_parent_magic_link_template_id: str
    resend_parent_digest_template_id: str

    # ── App ──────────────────────────────────────────────────────
    next_public_app_url: str
    api_url: str
    admin_secret_key: str
    allowed_origins_raw: str = Field(default="http://localhost:3100", alias="ALLOWED_ORIGINS")

    # ── Scheduled jobs ───────────────────────────────────────────
    jobs_runner_secret: str

    # ── Feature flags ────────────────────────────────────────────
    min_rep_age: int = 14
    parental_consent_required_under: int = 16

    # ── Parent Portal ────────────────────────────────────────────
    parent_session_secret: str

    # ── Brand Portal (Build Prompt 8) ───────────────────────────────
    # Fernet key (Fernet.generate_key()) for encrypting brand_profiles.ein
    # at the application layer -- see app/core/crypto.py.
    ein_encryption_key: str

    # ── Recruiter Portal (Build Prompt 11) ──────────────────────────
    # Contact credits granted per billing cycle on subscription
    # creation/renewal, and the price of a single top-up credit --
    # server-side only, never trusted from the client (Section 9).
    recruiter_plan_credits_allotment: int = 25
    recruiter_credit_topup_price_cents: int = 500
    # Stripe Price ids for the recruiter subscription plan (Build Prompt 12
    # deliverable 5: "Stripe checkout (monthly/annual)"). Optional with no
    # default -- an environment that hasn't created these Prices yet simply
    # can't offer that plan cadence; POST /recruiters/subscribe returns a
    # clear 500 rather than silently charging the wrong price.
    recruiter_price_id_monthly: str | None = None
    recruiter_price_id_annual: str | None = None

    # ── Category Exclusivity (Build Prompt 8C) ──────────────────────
    # Admin-set pricing for a category+city exclusivity window -- a
    # config value, not a schema value, so pricing changes never
    # require a migration (Section 8C: "these are config values, not
    # schema values").
    exclusivity_base_rate_cents_per_day: int = 5000
    exclusivity_max_days: int = 90

    # ── Skill Challenges (Build Prompt 8G) ──────────────────────────
    # Platform-funded bonus paid to a rep when their challenge
    # submission converts to a campaign invitation. Funded from
    # platform margin, not charged to brand.
    challenge_conversion_bonus_cents: int = 750

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins_raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
