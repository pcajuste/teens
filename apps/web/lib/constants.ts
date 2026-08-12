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
