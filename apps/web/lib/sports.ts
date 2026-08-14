// Must stay in sync with apps/api/app/core/sports.py and
// apps/api/app/core/sport_stats_schemas.py -- the backend is the source
// of truth for validation (422s win on any drift); this file exists so
// the sport-profile and season forms can render the right fields
// without a round trip, per ATHLETICS-6.

export const SUPPORTED_SPORTS = [
  "football",
  "basketball",
  "soccer",
  "baseball",
  "softball",
  "volleyball",
  "track_and_field",
  "cross_country",
  "swimming",
  "tennis",
  "lacrosse",
  "wrestling",
] as const;

export type SupportedSport = (typeof SUPPORTED_SPORTS)[number];

export const SPORT_LABELS: Record<SupportedSport, string> = {
  football: "Football",
  basketball: "Basketball",
  soccer: "Soccer",
  baseball: "Baseball",
  softball: "Softball",
  volleyball: "Volleyball",
  track_and_field: "Track & Field",
  cross_country: "Cross Country",
  swimming: "Swimming",
  tennis: "Tennis",
  lacrosse: "Lacrosse",
  wrestling: "Wrestling",
};

export const SEASON_TYPES = ["high_school", "travel", "club", "aau", "other"] as const;
export const SEASON_TYPE_LABELS: Record<(typeof SEASON_TYPES)[number], string> = {
  high_school: "High School",
  travel: "Travel",
  club: "Club",
  aau: "AAU",
  other: "Other",
};

export const SEASON_LEVELS = ["varsity", "jv", "freshman", "travel", "other"] as const;
export const SEASON_LEVEL_LABELS: Record<(typeof SEASON_LEVELS)[number], string> = {
  varsity: "Varsity",
  jv: "JV",
  freshman: "Freshman",
  travel: "Travel",
  other: "Other",
};

// Position vocabulary inferred from common rosters (Year 2 adds a
// dedicated positions data source per the ATHLETICS-6 spec -- this is
// an MVP stand-in, not backend-validated, so it deliberately isn't
// exhaustive/authoritative).
export const SPORT_POSITIONS: Record<SupportedSport, string[]> = {
  football: [
    "QB", "RB", "FB", "WR", "TE", "OL", "DL", "LB", "CB", "S", "K", "P", "LS",
  ],
  basketball: ["PG", "SG", "SF", "PF", "C"],
  soccer: ["GK", "CB", "FB", "CDM", "CM", "CAM", "Winger", "Forward"],
  baseball: ["P", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"],
  softball: ["P", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"],
  volleyball: ["Setter", "Outside Hitter", "Middle Blocker", "Opposite", "Libero", "DS"],
  track_and_field: ["Sprinter", "Distance", "Hurdles", "Jumps", "Throws", "Relay"],
  cross_country: ["Runner"],
  swimming: ["Freestyle", "Backstroke", "Breaststroke", "Butterfly", "IM", "Relay"],
  tennis: ["Singles", "Doubles"],
  lacrosse: ["Attack", "Midfield", "Defense", "Goalie", "FOGO"],
  wrestling: ["Wrestler"],
};

/** Field type per SPORT_STATS_SCHEMAS -- drives the form control rendered
 * for each sport_stats key (number input, text input, checkbox). Ranges
 * are advisory client-side hints; the 422 response from PUT/POST is the
 * authority on validity (D-decision: server never trusts client amounts,
 * same principle applied here to stat ranges). */
export type SportStatFieldType = "int" | "float" | "str" | "bool";

export interface SportStatFieldDef {
  key: string;
  type: SportStatFieldType;
  min: number | null;
  max: number | null;
  label: string;
}

function field(
  key: string,
  type: SportStatFieldType,
  min: number | null,
  max: number | null
): SportStatFieldDef {
  const label = key
    .split("_")
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(" ");
  return { key, type, min, max, label };
}

export const SPORT_STATS_FIELDS: Record<SupportedSport, SportStatFieldDef[]> = {
  football: [
    field("passing_yards", "int", 0, 10000),
    field("pass_completions", "int", 0, 1000),
    field("pass_attempts", "int", 0, 1000),
    field("passing_touchdowns", "int", 0, 200),
    field("interceptions_thrown", "int", 0, 100),
    field("rushing_yards", "int", 0, 5000),
    field("rushing_touchdowns", "int", 0, 100),
    field("carries", "int", 0, 500),
    field("receptions", "int", 0, 300),
    field("receiving_yards", "int", 0, 5000),
    field("receiving_touchdowns", "int", 0, 100),
    field("tackles", "int", 0, 500),
    field("sacks", "float", 0, 50),
    field("interceptions", "int", 0, 50),
    field("field_goals_made", "int", 0, 50),
    field("field_goals_attempted", "int", 0, 50),
  ],
  basketball: [
    field("points_per_game", "float", 0, 60),
    field("rebounds_per_game", "float", 0, 30),
    field("assists_per_game", "float", 0, 20),
    field("steals_per_game", "float", 0, 10),
    field("blocks_per_game", "float", 0, 10),
    field("field_goal_pct", "float", 0, 1),
    field("three_point_pct", "float", 0, 1),
    field("free_throw_pct", "float", 0, 1),
    field("games_played", "int", 0, 40),
  ],
  soccer: [
    field("goals", "int", 0, 100),
    field("assists", "int", 0, 100),
    field("games_played", "int", 0, 50),
    field("minutes_played", "int", 0, 5000),
    field("shots_on_goal", "int", 0, 300),
    field("save_percentage", "float", 0, 1),
    field("clean_sheets", "int", 0, 50),
  ],
  baseball: [
    field("batting_average", "float", 0, 1),
    field("home_runs", "int", 0, 100),
    field("rbi", "int", 0, 200),
    field("runs", "int", 0, 200),
    field("stolen_bases", "int", 0, 100),
    field("on_base_pct", "float", 0, 1),
    field("era", "float", 0, 20),
    field("wins", "int", 0, 30),
    field("strikeouts", "int", 0, 300),
    field("innings_pitched", "float", 0, 200),
    field("whip", "float", 0, 5),
  ],
  softball: [
    field("batting_average", "float", 0, 1),
    field("home_runs", "int", 0, 100),
    field("rbi", "int", 0, 200),
    field("era", "float", 0, 20),
    field("strikeouts", "int", 0, 300),
    field("wins", "int", 0, 30),
  ],
  volleyball: [
    field("kills_per_set", "float", 0, 20),
    field("aces_per_set", "float", 0, 10),
    field("digs_per_set", "float", 0, 20),
    field("blocks_per_set", "float", 0, 10),
    field("hitting_percentage", "float", -1, 1),
    field("sets_played", "int", 0, 300),
  ],
  track_and_field: [
    field("event", "str", null, null),
    field("personal_best", "str", null, null),
    field("season_best", "str", null, null),
    field("meets_competed", "int", 0, 50),
    field("state_qualifier", "bool", null, null),
  ],
  cross_country: [
    field("personal_best_5k", "str", null, null),
    field("season_best_5k", "str", null, null),
    field("meets_competed", "int", 0, 30),
    field("varsity_letter", "bool", null, null),
  ],
  swimming: [
    // events/personal_bests are list/dict types (advanced) -- omitted
    // from the MVP structured form; achievable via the raw JSON field
    // like the "other" sport bucket if a swimmer needs them.
    field("meets_competed", "int", 0, 50),
    field("state_qualifier", "bool", null, null),
  ],
  tennis: [
    field("singles_record", "str", null, null),
    field("doubles_record", "str", null, null),
    field("varsity_letter", "bool", null, null),
    field("ranking", "int", 1, 1000),
  ],
  lacrosse: [
    field("goals", "int", 0, 200),
    field("assists", "int", 0, 200),
    field("ground_balls", "int", 0, 200),
    field("caused_turnovers", "int", 0, 100),
    field("save_percentage", "float", 0, 1),
    field("games_played", "int", 0, 40),
  ],
  wrestling: [
    field("record_wins", "int", 0, 100),
    field("record_losses", "int", 0, 100),
    field("pins", "int", 0, 100),
    field("weight_class", "int", 90, 400),
    field("state_qualifier", "bool", null, null),
  ],
};

/** Season status chip display. NOTE: the backend never sets
 * season.status = "declined" -- a decline leaves status =
 * "pending_attestation" and instead sets coach_attestation_status =
 * "declined" (apps/api/app/repositories/athletic_seasons_repository.py
 * mark_attestation_declined), so both fields are needed to pick the
 * right chip. This mirrors the season-detail-page states in the
 * ATHLETICS-6 spec ("If declined: ...") without a season.status value
 * that doesn't actually exist server-side. */
export function seasonStatusDisplay(season: {
  status: string;
  coach_attestation_status: string;
}): { label: string; variant: "pending" | "active" | "earned" | "done" | "destructive" } {
  if (season.status === "pending_attestation" && season.coach_attestation_status === "declined") {
    return { label: "Coach Declined", variant: "destructive" };
  }
  switch (season.status) {
    case "draft":
      return { label: "Draft", variant: "pending" };
    case "pending_attestation":
      return { label: "Awaiting Coach", variant: "active" };
    case "attested":
      return { label: "Coach Verified", variant: "earned" };
    case "verified":
      return { label: "Platform Verified", variant: "done" };
    default:
      return { label: season.status, variant: "pending" };
  }
}
