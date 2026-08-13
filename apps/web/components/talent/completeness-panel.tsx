import type { TalentProfile } from "@/lib/types";

function missingFieldPrompts(profile: TalentProfile): string[] {
  const prompts: string[] = [];
  if (!profile.bio) prompts.push("Add a bio");
  if (profile.categories.length === 0) prompts.push("Pick at least one category");
  if (!profile.school_type) prompts.push("Add your school type");
  if (!profile.instagram_handle && !profile.tiktok_handle) prompts.push("Add an Instagram or TikTok handle");
  if (profile.total_campaigns_completed === 0) prompts.push("Complete your first campaign");
  return prompts;
}

export function CompletenessPanel({ profile }: { profile: TalentProfile }) {
  const prompts = missingFieldPrompts(profile);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">Profile completeness</p>
        <p className="text-sm font-semibold">{profile.profile_completeness_score}%</p>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-[width]"
          style={{ width: `${profile.profile_completeness_score}%` }}
        />
      </div>
      {prompts.length > 0 ? (
        <ul className="mt-1 flex flex-col gap-1 text-sm text-muted-foreground">
          {prompts.map((p) => (
            <li key={p}>· {p} to raise your score</li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">Your profile is fully filled out.</p>
      )}
    </div>
  );
}
