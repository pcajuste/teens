"""Athletic track constants: supported sports and season metadata.

SUPPORTED_SPORTS is derived from app/core/sport_stats_schemas.py's
SPORT_STATS_SCHEMAS keys (minus the 'other' catch-all bucket, which is
a valid *stats schema* selector but not itself a sport a talent picks --
'other' is what validate_sport_stats falls back to for an
unenumerated sport, so it is deliberately excluded from the list of
sports a talent can actually select at the router/schema validation
layer).

SEASON_TYPES / SEASON_LEVELS mirror the CHECK constraints on
public.athletic_seasons from Migration C (teenure_athletics_playbook.md
Part 3) exactly -- these are duplicated here (not read from the DB) so
FastAPI/Pydantic can reject an invalid value with a clean 422 before a
query ever runs, the same pattern app/core/sport_stats_schemas.py uses
for sport_stats.
"""
from __future__ import annotations

from app.core.sport_stats_schemas import SPORT_STATS_SCHEMAS

# 'other' is a stats-schema fallback, not a selectable sport.
SUPPORTED_SPORTS: frozenset[str] = frozenset(SPORT_STATS_SCHEMAS.keys()) - {"other"}

# Matches public.athletic_seasons.season_type CHECK constraint (Migration C).
SEASON_TYPES: frozenset[str] = frozenset({"high_school", "travel", "club", "aau", "other"})

# Matches public.athletic_seasons.level CHECK constraint (Migration C).
SEASON_LEVELS: frozenset[str] = frozenset({"varsity", "jv", "freshman", "travel", "other"})
