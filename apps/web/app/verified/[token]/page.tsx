"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Badge as UiBadge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import type { PublicVerifiedProfile } from "@/lib/types";
import { CATEGORY_LABELS } from "@/lib/categories";

// Build Prompt 5/6 deliverable 12/9: the public Living Achievement Link
// page. No navigation to the app, no signup CTA, no auth check --
// intentionally a credential document, not a marketing surface. Renders
// from GET /verified/:token, which is itself unauthenticated.
export default function VerifiedProfilePage() {
  const params = useParams<{ token: string }>();
  const [profile, setProfile] = useState<PublicVerifiedProfile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<PublicVerifiedProfile>(`/verified/${encodeURIComponent(params.token)}`)
      .then(setProfile)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load this profile."));
  }, [params.token]);

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col gap-6 p-6">
      <div className="flex items-center justify-center gap-2 pt-4">
        <span className="text-lg font-semibold tracking-tight">Teenure</span>
      </div>

      {error ? <p className="text-center text-sm text-destructive">{error}</p> : null}

      {profile && !profile.public ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-8 text-center">
            <p className="text-base font-medium">This profile is not currently public.</p>
            <p className="text-sm text-muted-foreground">
              The person who shared this link may not have turned on public sharing yet. Ask them to enable
              &quot;Make my verified profile public&quot; from their Teenure profile.
            </p>
          </CardContent>
        </Card>
      ) : null}

      {profile && profile.public ? (
        <Card>
          <CardContent className="flex flex-col gap-5 pt-4">
            <div className="flex flex-col items-center gap-1 text-center">
              <h1 className="text-2xl font-semibold tracking-tight">{profile.display_name}</h1>
              <p className="text-sm text-muted-foreground">
                {profile.school_name} &middot; Class of {profile.graduation_year}
              </p>
              <p className="text-sm text-muted-foreground">{profile.city}</p>
            </div>

            <div className="flex flex-wrap justify-center gap-1.5">
              {(profile.categories ?? []).map((c) => (
                <UiBadge key={c} variant="secondary">
                  {CATEGORY_LABELS[c as keyof typeof CATEGORY_LABELS] ?? c}
                </UiBadge>
              ))}
            </div>

            <div className="grid grid-cols-2 gap-3 rounded-lg bg-muted p-4 text-center sm:grid-cols-3">
              <div>
                <p className="text-xl font-semibold">{profile.total_campaigns_completed}</p>
                <p className="text-xs text-muted-foreground">Campaigns completed</p>
              </div>
              <div>
                <p className="text-xl font-semibold">
                  {profile.average_rating != null ? profile.average_rating.toFixed(1) : "—"}
                </p>
                <p className="text-xs text-muted-foreground">Average rating</p>
              </div>
              {profile.total_earnings_cents != null ? (
                <div>
                  <p className="text-xl font-semibold">${(profile.total_earnings_cents / 100).toFixed(2)}</p>
                  <p className="text-xs text-muted-foreground">Total earnings</p>
                </div>
              ) : null}
            </div>

            {profile.badges && profile.badges.length > 0 ? (
              <div className="flex flex-col gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Badges earned</p>
                <div className="flex flex-wrap gap-1.5">
                  {profile.badges.map((b) => (
                    <UiBadge key={b.module_id} variant="outline">
                      {b.badge_title}
                    </UiBadge>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="flex flex-col items-center gap-1 border-t border-border pt-4 text-center">
              <p className="text-sm font-medium text-success">Verified by Teenure</p>
              {profile.last_updated ? (
                <p className="text-xs text-muted-foreground">
                  Last updated {new Date(profile.last_updated).toLocaleDateString()}
                </p>
              ) : null}
            </div>
          </CardContent>
        </Card>
      ) : null}
    </main>
  );
}
