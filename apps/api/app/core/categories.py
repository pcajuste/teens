"""Campaign/rep category vocabulary (Section 3.1 lists the base set;
Build Prompt 4A deliverable 4 adds the parent-only, blockable-only
categories). Stored as TEXT[] in Postgres, not a DB enum -- Section 7's
"same centrally-defined enum" language refers to this app-level set,
validated here rather than at the DB layer.
"""
from __future__ import annotations

BASE_CATEGORIES = frozenset(
    {"athletics", "gaming", "fashion", "music", "academics", "food", "beauty", "tech"}
)

# Can appear in a campaign's target_categories and be blocked via a
# parent's values_filters, but are never a rep's own self-selected
# interest category.
PARENT_ONLY_BLOCKABLE_CATEGORIES = frozenset(
    {
        "alcohol_adjacent",
        "political",
        "dating_romantic",
        "gambling",
        "dietary_supplements",
        "in_person_travel_required",
    }
)

ALL_VALUES_FILTER_CATEGORIES = BASE_CATEGORIES | PARENT_ONLY_BLOCKABLE_CATEGORIES
