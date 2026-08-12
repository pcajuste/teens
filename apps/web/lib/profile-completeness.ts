import type { RepProfile } from "./types";

export interface MissingField {
  label: string;
  href: string;
}

/**
 * Client-side-only heuristic for WHICH fields are missing, so dashboard
 * prompts can deep-link to the specific field. The authoritative numeric
 * score itself comes from the backend
 * (RepProfile.profile_completeness_score) — this never overrides that
 * number, it only explains it.
 */
export function missingFields(profile: RepProfile): MissingField[] {
  const missing: MissingField[] = [];
  if (!profile.bio) missing.push({ label: "Add a bio", href: "/rep/profile/edit#bio" });
  if (!profile.categories || profile.categories.length === 0)
    missing.push({ label: "Pick your categories", href: "/rep/profile/edit#categories" });
  if (!profile.school_name) missing.push({ label: "Add your school", href: "/rep/profile/edit#school" });
  if (!profile.city || !profile.state) missing.push({ label: "Add your city", href: "/rep/profile/edit#city" });
  if (!profile.instagram_handle && !profile.tiktok_handle)
    missing.push({ label: "Add a social handle", href: "/rep/profile/edit#social" });
  if (!profile.graduation_year)
    missing.push({ label: "Add your graduation year", href: "/rep/profile/edit#graduation-year" });
  return missing;
}
