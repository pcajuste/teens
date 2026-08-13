"""Data access for public.brand_profiles.

The `ein` column stores Fernet ciphertext, not plaintext -- encryption/
decryption happens at the router layer (app/core/crypto.py), which is
the only layer that has both a Settings object and a reason to see the
plaintext value. This module never encrypts or decrypts; it just moves
whatever string it's given in or out of the `ein` column.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg

_COLUMNS = (
    "id, user_id, company_name, website, ein, industry, target_categories, "
    "verified, verified_at, verified_by, stripe_customer_id, "
    "logo_url, brand_color_primary, about_text, why_on_teenure_text, created_at, updated_at"
)


@dataclass(frozen=True, slots=True)
class BrandProfile:
    id: str
    user_id: str
    company_name: str
    website: str | None
    ein: str | None
    industry: str | None
    target_categories: list[str]
    verified: bool
    verified_at: datetime | None
    verified_by: str | None
    stripe_customer_id: str | None
    logo_url: str | None
    brand_color_primary: str | None
    about_text: str | None
    why_on_teenure_text: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "BrandProfile":
        return cls(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            company_name=row["company_name"],
            website=row["website"],
            ein=row["ein"],
            industry=row["industry"],
            target_categories=list(row["target_categories"] or []),
            verified=row["verified"],
            verified_at=row["verified_at"],
            verified_by=str(row["verified_by"]) if row["verified_by"] else None,
            stripe_customer_id=row["stripe_customer_id"],
            logo_url=row["logo_url"],
            brand_color_primary=row["brand_color_primary"],
            about_text=row["about_text"],
            why_on_teenure_text=row["why_on_teenure_text"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @property
    def company_profile_complete(self) -> bool:
        """Build Prompt 8I: the Company Profile template is "required
        before any campaign goes live" -- the gate other templates'
        activation routes check (logo + both required text fields)."""
        return bool(self.logo_url and self.about_text and self.why_on_teenure_text)


async def get_by_id(conn: asyncpg.Connection, brand_id: str) -> BrandProfile | None:
    row = await conn.fetchrow(f"SELECT {_COLUMNS} FROM public.brand_profiles WHERE id = $1", brand_id)
    return BrandProfile.from_row(row) if row else None


async def get_by_user_id(conn: asyncpg.Connection, user_id: str) -> BrandProfile | None:
    row = await conn.fetchrow(f"SELECT {_COLUMNS} FROM public.brand_profiles WHERE user_id = $1", user_id)
    return BrandProfile.from_row(row) if row else None


async def create_brand_profile(
    conn: asyncpg.Connection,
    *,
    user_id: str,
    company_name: str,
    website: str | None,
    ein_encrypted: str | None,
    industry: str | None,
    target_categories: list[str],
) -> BrandProfile:
    row = await conn.fetchrow(
        f"""
        INSERT INTO public.brand_profiles (user_id, company_name, website, ein, industry, target_categories)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING {_COLUMNS}
        """,
        user_id,
        company_name,
        website,
        ein_encrypted,
        industry,
        target_categories,
    )
    return BrandProfile.from_row(row)


async def update_brand_profile(
    conn: asyncpg.Connection,
    brand_id: str,
    *,
    company_name: str,
    website: str | None,
    ein_encrypted: str | None,
    industry: str | None,
    target_categories: list[str],
) -> BrandProfile:
    """Full-record update, mirroring talent_profiles_repository.update_talent_profile's
    shape. `verified`/`verified_at`/`verified_by`/`stripe_customer_id` are
    deliberately absent -- never writable from this function, only from
    the admin-approval flow (Prompt 13) and Stripe customer creation."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.brand_profiles
        SET company_name = $2, website = $3, ein = $4, industry = $5,
            target_categories = $6, updated_at = now()
        WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        brand_id,
        company_name,
        website,
        ein_encrypted,
        industry,
        target_categories,
    )
    return BrandProfile.from_row(row)


async def update_company_profile(
    conn: asyncpg.Connection,
    brand_id: str,
    *,
    logo_url: str | None,
    brand_color_primary: str | None,
    about_text: str | None,
    why_on_teenure_text: str | None,
) -> BrandProfile:
    """PUT /brands/me/company-profile (Build Prompt 8I template 1) --
    deliberately separate from update_brand_profile above, which owns
    the Prompt 8 onboarding fields. Word-count validation on
    about_text/why_on_teenure_text happens at the schema layer
    (schemas/brands.py's CompanyProfileUpdateRequest validators)."""
    row = await conn.fetchrow(
        f"""
        UPDATE public.brand_profiles
        SET logo_url = $2, brand_color_primary = $3, about_text = $4,
            why_on_teenure_text = $5, updated_at = now()
        WHERE id = $1
        RETURNING {_COLUMNS}
        """,
        brand_id,
        logo_url,
        brand_color_primary,
        about_text,
        why_on_teenure_text,
    )
    return BrandProfile.from_row(row)


async def set_stripe_customer_id(conn: asyncpg.Connection, brand_id: str, stripe_customer_id: str) -> None:
    await conn.execute(
        "UPDATE public.brand_profiles SET stripe_customer_id = $2, updated_at = now() WHERE id = $1",
        brand_id,
        stripe_customer_id,
    )
