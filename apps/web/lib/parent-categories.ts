// Mirrors app/core/categories.py's BASE_CATEGORIES +
// PARENT_ONLY_BLOCKABLE_CATEGORIES (ALL_VALUES_FILTER_CATEGORIES).
// Plain-language descriptions are UX copy for the values-filter
// screen (Build Prompt 4A deliverable 4 / frontend deliverable 5).
export interface ParentFilterCategory {
  value: string;
  label: string;
  description: string;
}

export const PARENT_FILTER_CATEGORIES: ParentFilterCategory[] = [
  { value: "athletics", label: "Athletics", description: "Campaigns from sports, fitness, and athletic-gear brands." },
  { value: "gaming", label: "Gaming", description: "Campaigns from video game and gaming-hardware brands." },
  { value: "fashion", label: "Fashion", description: "Campaigns from clothing, accessories, and style brands." },
  { value: "music", label: "Music", description: "Campaigns from music, artists, and audio-gear brands." },
  { value: "academics", label: "Academics", description: "Campaigns from tutoring, test-prep, and education brands." },
  { value: "food", label: "Food", description: "Campaigns from food and beverage brands." },
  { value: "beauty", label: "Beauty", description: "Campaigns from cosmetics and skincare brands." },
  { value: "tech", label: "Tech", description: "Campaigns from electronics and software brands." },
  {
    value: "alcohol_adjacent",
    label: "Alcohol-adjacent",
    description: "Campaigns that reference alcohol brands or drinking culture, even indirectly.",
  },
  {
    value: "political",
    label: "Political",
    description: "Campaigns tied to political candidates, causes, or advocacy organizations.",
  },
  {
    value: "dating_romantic",
    label: "Dating & romantic",
    description: "Campaigns from dating apps or brands built around romantic relationships.",
  },
  {
    value: "gambling",
    label: "Gambling",
    description: "Campaigns from betting, lottery, or gambling-related brands.",
  },
  {
    value: "dietary_supplements",
    label: "Dietary supplements",
    description: "Campaigns promoting vitamins, supplements, or weight-management products.",
  },
  {
    value: "in_person_travel_required",
    label: "In-person travel required",
    description: "Campaigns that require your teen to travel to an in-person event or activation.",
  },
];
