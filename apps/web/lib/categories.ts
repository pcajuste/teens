// Must stay in sync with apps/api/app/core/categories.py BASE_CATEGORIES.
// Reps self-select only from this set -- the parent-only-blockable
// categories (alcohol_adjacent, political, etc.) never appear here.
export const BASE_CATEGORIES = [
  "athletics",
  "gaming",
  "fashion",
  "music",
  "academics",
  "food",
  "beauty",
  "tech",
] as const;

export type Category = (typeof BASE_CATEGORIES)[number];

export const CATEGORY_LABELS: Record<Category, string> = {
  athletics: "Athletics",
  gaming: "Gaming",
  fashion: "Fashion",
  music: "Music",
  academics: "Academics",
  food: "Food",
  beauty: "Beauty",
  tech: "Tech",
};
