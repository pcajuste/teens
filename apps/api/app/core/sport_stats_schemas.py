"""Per-sport stat field definitions and acceptable ranges.

Industry reference: MaxPreps uses sport-specific structured schemas.
Validation at the API layer (not DB layer) allows JSONB storage
flexibility while preventing garbage ingest.

Each sport schema is a dict of {field_name: (type, min, max | None)}.
'achievements' is a reserved key on every schema -- a list of
{"title": str, "type": str, "season_year": int} dicts (D9 decision,
teenure_athletics_playbook.md Part 0).
"""
from __future__ import annotations

from typing import Any

SportStatsSchema = dict[str, tuple[type, float | None, float | None]]

SPORT_STATS_SCHEMAS: dict[str, SportStatsSchema] = {
    "football": {
        # Passing
        "passing_yards":        (int,   0,    10000),
        "pass_completions":     (int,   0,    1000),
        "pass_attempts":        (int,   0,    1000),
        "passing_touchdowns":   (int,   0,    200),
        "interceptions_thrown": (int,   0,    100),
        # Rushing
        "rushing_yards":        (int,   0,    5000),
        "rushing_touchdowns":   (int,   0,    100),
        "carries":              (int,   0,    500),
        # Receiving
        "receptions":           (int,   0,    300),
        "receiving_yards":      (int,   0,    5000),
        "receiving_touchdowns": (int,   0,    100),
        # Defense
        "tackles":              (int,   0,    500),
        "sacks":                (float, 0,    50),
        "interceptions":        (int,   0,    50),
        # Kicking
        "field_goals_made":     (int,   0,    50),
        "field_goals_attempted":(int,   0,    50),
    },
    "basketball": {
        "points_per_game":      (float, 0,    60),
        "rebounds_per_game":    (float, 0,    30),
        "assists_per_game":     (float, 0,    20),
        "steals_per_game":      (float, 0,    10),
        "blocks_per_game":      (float, 0,    10),
        "field_goal_pct":       (float, 0,    1),
        "three_point_pct":      (float, 0,    1),
        "free_throw_pct":       (float, 0,    1),
        "games_played":         (int,   0,    40),
    },
    "soccer": {
        "goals":                (int,   0,    100),
        "assists":              (int,   0,    100),
        "games_played":         (int,   0,    50),
        "minutes_played":       (int,   0,    5000),
        "shots_on_goal":        (int,   0,    300),
        "save_percentage":      (float, 0,    1),    # goalkeeper
        "clean_sheets":         (int,   0,    50),   # goalkeeper
    },
    "baseball": {
        # Batting
        "batting_average":      (float, 0,    1),
        "home_runs":            (int,   0,    100),
        "rbi":                  (int,   0,    200),
        "runs":                 (int,   0,    200),
        "stolen_bases":         (int,   0,    100),
        "on_base_pct":          (float, 0,    1),
        # Pitching
        "era":                  (float, 0,    20),
        "wins":                 (int,   0,    30),
        "strikeouts":           (int,   0,    300),
        "innings_pitched":      (float, 0,    200),
        "whip":                 (float, 0,    5),
    },
    "softball": {
        "batting_average":      (float, 0,    1),
        "home_runs":            (int,   0,    100),
        "rbi":                  (int,   0,    200),
        "era":                  (float, 0,    20),
        "strikeouts":           (int,   0,    300),
        "wins":                 (int,   0,    30),
    },
    "volleyball": {
        "kills_per_set":        (float, 0,    20),
        "aces_per_set":         (float, 0,    10),
        "digs_per_set":         (float, 0,    20),
        "blocks_per_set":       (float, 0,    10),
        "hitting_percentage":   (float, -1,   1),
        "sets_played":          (int,   0,    300),
    },
    "track_and_field": {
        "event":                (str,   None, None),  # "100m", "long jump", etc.
        "personal_best":        (str,   None, None),  # "10.82s", "7.23m"
        "season_best":          (str,   None, None),
        "meets_competed":       (int,   0,    50),
        "state_qualifier":      (bool,  None, None),
    },
    "cross_country": {
        "personal_best_5k":     (str,   None, None),  # "16:42"
        "season_best_5k":       (str,   None, None),
        "meets_competed":       (int,   0,    30),
        "varsity_letter":       (bool,  None, None),
    },
    "swimming": {
        "events":               (list,  None, None),  # ["100 freestyle", "200 IM"]
        "personal_bests":       (dict,  None, None),  # {"100 freestyle": "48.3s"}
        "meets_competed":       (int,   0,    50),
        "state_qualifier":      (bool,  None, None),
    },
    "tennis": {
        "singles_record":       (str,   None, None),  # "18-4"
        "doubles_record":       (str,   None, None),
        "varsity_letter":       (bool,  None, None),
        "ranking":              (int,   1,    1000),
    },
    "lacrosse": {
        "goals":                (int,   0,    200),
        "assists":              (int,   0,    200),
        "ground_balls":         (int,   0,    200),
        "caused_turnovers":     (int,   0,    100),
        "save_percentage":      (float, 0,    1),    # goalie
        "games_played":         (int,   0,    40),
    },
    "wrestling": {
        "record_wins":          (int,   0,    100),
        "record_losses":        (int,   0,    100),
        "pins":                 (int,   0,    100),
        "weight_class":         (int,   90,   400),
        "state_qualifier":      (bool,  None, None),
    },
    # Catch-all for any sport not explicitly defined above
    "other": {},
}


class SportStatsValidationError(ValueError):
    pass


def validate_sport_stats(sport: str, stats: dict[str, Any]) -> None:
    """Validates stats against the schema for the given sport.
    Raises SportStatsValidationError with a field-level message on any violation.
    Unknown fields are allowed (schema is additive, not exclusive) so new
    fields can be submitted without a code change -- only explicitly-defined
    fields are range-checked."""
    schema = SPORT_STATS_SCHEMAS.get(sport, {})
    # 'achievements' is always a valid key (D9 decision)
    for field, (expected_type, min_val, max_val) in schema.items():
        if field not in stats:
            continue  # optional fields are not required
        value = stats[field]
        if expected_type == bool:
            if not isinstance(value, bool):
                raise SportStatsValidationError(
                    f"{sport}.{field} must be a boolean, got {type(value).__name__}"
                )
        elif expected_type in (int, float):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise SportStatsValidationError(
                    f"{sport}.{field} must be numeric, got {type(value).__name__}"
                )
            if min_val is not None and value < min_val:
                raise SportStatsValidationError(
                    f"{sport}.{field} must be >= {min_val}, got {value}"
                )
            if max_val is not None and value > max_val:
                raise SportStatsValidationError(
                    f"{sport}.{field} must be <= {max_val}, got {value}"
                )
        elif expected_type == str:
            if not isinstance(value, str):
                raise SportStatsValidationError(
                    f"{sport}.{field} must be a string, got {type(value).__name__}"
                )
        elif expected_type == list:
            if not isinstance(value, list):
                raise SportStatsValidationError(
                    f"{sport}.{field} must be a list, got {type(value).__name__}"
                )
        elif expected_type == dict:
            if not isinstance(value, dict):
                raise SportStatsValidationError(
                    f"{sport}.{field} must be an object, got {type(value).__name__}"
                )
    # Validate achievements list structure if present (D9)
    if "achievements" in stats:
        achievements = stats["achievements"]
        if not isinstance(achievements, list):
            raise SportStatsValidationError("achievements must be a list")
        for i, a in enumerate(achievements):
            if not isinstance(a, dict):
                raise SportStatsValidationError(f"achievements[{i}] must be a dict")
            if "title" not in a or not isinstance(a["title"], str):
                raise SportStatsValidationError(f"achievements[{i}].title must be a string")
            if "type" not in a or a["type"] not in ("award", "honor", "record", "milestone", "recognition"):
                raise SportStatsValidationError(
                    f"achievements[{i}].type must be one of: award, honor, record, milestone, recognition"
                )
            if "season_year" not in a or not isinstance(a["season_year"], int) or isinstance(a["season_year"], bool):
                raise SportStatsValidationError(f"achievements[{i}].season_year must be an integer")
