// Mirrors apps/api/app/core/constants.py. Hand-kept in sync per that
// file's own comment ("left for the frontend prompts to wire up") —
// there is no /reps/categories lookup endpoint yet, so this is the
// pragmatic option until one exists.
export const CATEGORIES = [
  "athletics",
  "gaming",
  "fashion",
  "music",
  "academics",
  "food",
  "beauty",
  "tech",
] as const;

export type Category = (typeof CATEGORIES)[number];

export const GRADUATION_YEAR_MIN = 2024;
export const GRADUATION_YEAR_MAX = 2035;

export const SCHOOL_TYPES = ["public", "private", "charter", "homeschool"] as const;

export const INVITE_EXPIRY_HOURS = 48;

// Mirrors apps/api/app/core/constants.py's VALUES_FILTER_CATEGORIES
// (Section 9A / Prompt 4A). Superset of CATEGORIES plus brand/product
// content-only categories a parent can block that don't describe a rep
// themselves.
export const PARENT_FILTER_ONLY_CATEGORIES = [
  "alcohol_adjacent",
  "political",
  "dating_romantic",
  "gambling",
  "dietary_supplements",
  "in_person_travel_required",
] as const;

export const VALUES_FILTER_CATEGORIES = [...CATEGORIES, ...PARENT_FILTER_ONLY_CATEGORIES];

export const VALUES_FILTER_DESCRIPTIONS: Record<string, string> = {
  athletics: "Sports and athletics-related brand campaigns",
  gaming: "Video game and gaming brand campaigns",
  fashion: "Clothing and fashion brand campaigns",
  music: "Music and music-brand campaigns",
  academics: "Academic/study-related brand campaigns",
  food: "Food and beverage brand campaigns",
  beauty: "Beauty and cosmetics brand campaigns",
  tech: "Technology and gadget brand campaigns",
  alcohol_adjacent: "Campaigns adjacent to alcohol brands (e.g. mixers, bar accessories)",
  political: "Political or advocacy-related campaigns",
  dating_romantic: "Dating or romance-app related campaigns",
  gambling: "Gambling or betting-related campaigns",
  dietary_supplements: "Dietary supplement or weight-loss product campaigns",
  in_person_travel_required: "Campaigns requiring in-person travel to an event or shoot",
};

export const PARENT_APPROVAL_WINDOW_HOURS = 48;
