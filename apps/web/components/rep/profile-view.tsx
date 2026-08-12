import { Badge } from "@/components/ui/badge";
import { CATEGORY_LABELS, type Category } from "@/lib/categories";
import type { RepProfile, RepProfilePreview } from "@/lib/types";

function money(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

// Renders identically whether fed GET /reps/me or GET
// /reps/me/profile-preview data, so the "what a recruiter sees" screen
// can never drift from the real profile display.
export function ProfileView({ profile }: { profile: RepProfile | RepProfilePreview }) {
  const earnings = "total_earnings_cents" in profile ? profile.total_earnings_cents : null;

  return (
    <div className="flex flex-col gap-3">
      <div>
        <h2 className="text-lg font-semibold">{profile.display_name || "Unnamed rep"}</h2>
        <p className="text-sm text-muted-foreground">
          {profile.school_name || "No school listed"}
          {profile.graduation_year ? ` · Class of ${profile.graduation_year}` : ""}
        </p>
        <p className="text-sm text-muted-foreground">
          {profile.city}
          {profile.state ? `, ${profile.state}` : ""}
        </p>
      </div>

      {profile.bio ? <p className="text-sm">{profile.bio}</p> : null}

      {profile.categories.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {profile.categories.map((c) => (
            <Badge key={c} variant="secondary">
              {CATEGORY_LABELS[c as Category] ?? c}
            </Badge>
          ))}
        </div>
      ) : null}

      <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
        {profile.instagram_handle ? <span>Instagram: @{profile.instagram_handle}</span> : null}
        {profile.tiktok_handle ? <span>TikTok: @{profile.tiktok_handle}</span> : null}
      </div>

      <div className="grid grid-cols-2 gap-3 pt-1">
        <div className="rounded-lg border border-border p-2.5">
          <p className="text-xs text-muted-foreground">Campaigns completed</p>
          <p className="text-lg font-semibold">{profile.total_campaigns_completed}</p>
        </div>
        <div className="rounded-lg border border-border p-2.5">
          <p className="text-xs text-muted-foreground">Average rating</p>
          <p className="text-lg font-semibold">{profile.average_rating?.toFixed(1) ?? "—"}</p>
        </div>
        {earnings !== null ? (
          <div className="col-span-2 rounded-lg border border-border p-2.5">
            <p className="text-xs text-muted-foreground">Lifetime earnings</p>
            <p className="text-lg font-semibold">{money(earnings)}</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
