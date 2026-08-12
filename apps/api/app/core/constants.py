"""Centrally-defined enums shared across routes/serializers (Prompt 5).

Kept here (not duplicated in frontend code) per deliverable 1's explicit
instruction not to hand-maintain two lists that can drift; the frontend
should treat this backend as the source of truth (e.g. via an
/reps/categories-style lookup, or a generated shared-types constant --
left for the frontend prompts to wire up).
"""

from __future__ import annotations

# Section 2.1: "Categories of influence"
CATEGORIES = ["athletics", "gaming", "fashion", "music", "academics", "food", "beauty", "tech"]

# Section 7: rep_profiles.graduation_year CHECK (graduation_year BETWEEN 2024 AND 2035)
GRADUATION_YEAR_MIN = 2024
GRADUATION_YEAR_MAX = 2035

INVITE_EXPIRY_HOURS = 48

# Section 9A: parent values-filter categories. Superset of CATEGORIES
# (a parent can block any rep category, e.g. "gaming") plus
# brand/product content-only categories that don't describe a rep
# themselves.
PARENT_FILTER_ONLY_CATEGORIES = [
    "alcohol_adjacent", "political", "dating_romantic",
    "gambling", "dietary_supplements", "in_person_travel_required",
]
VALUES_FILTER_CATEGORIES = CATEGORIES + PARENT_FILTER_ONLY_CATEGORIES

PARENT_SESSION_TTL_HOURS = 24
PARENT_MAGIC_LINK_TTL_MINUTES = 15
PARENT_LOGIN_RATE_LIMIT_SECONDS = 10 * 60

ALLOWED_UPLOAD_CONTENT_TYPES = {
    "image/png", "image/jpeg", "image/gif",
    "video/mp4", "video/quicktime",
    "application/pdf",
}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25MB
