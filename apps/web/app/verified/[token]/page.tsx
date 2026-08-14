"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Badge as UiBadge } from "@/components/ui/badge";
import { LogoStacked, LOGO_SIZES } from "@/components/logo";
import { api, ApiError } from "@/lib/api";
import type { PublicVerifiedProfile } from "@/lib/types";
import { CATEGORY_LABELS } from "@/lib/categories";
import { SPORT_LABELS, SPORT_STATS_FIELDS, SEASON_LEVEL_LABELS, type SupportedSport } from "@/lib/sports";

// Build Prompt 5/6 deliverable 12/9: the public Living Achievement Link
// page. No navigation to the app, no signup CTA, no auth check --
// intentionally a credential document, not a portal screen. DS Section
// 6/11: this is the one deliberate light-mode (ink-on-white) surface in
// the product -- the .verified-light wrapper (app/globals.css) supplies
// scoped light tokens so this page still routes through tokens rather
// than hardcoding hex.
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
    <main className="verified-light min-h-screen bg-[var(--vl-bg)] text-[var(--vl-ink)]">
      <div className="mx-auto flex max-w-md flex-col items-start gap-6 p-6">
        <div className="pt-4">
          <LogoStacked darkMode={false} width={LOGO_SIZES.verifiedProfile} />
        </div>

        {error ? <p className="text-center text-sm text-[var(--vl-danger)]">{error}</p> : null}

        {profile && !profile.public ? (
          <div className="rounded-[var(--r-lg)] border border-[var(--vl-border)] bg-[var(--vl-surface)] p-8 text-center">
            <p className="text-base font-medium">This profile is not currently public.</p>
            <p className="mt-2 text-sm text-[var(--vl-text-2)]">
              The person who shared this link may not have turned on public sharing yet. Ask them to enable
              &quot;Make my verified profile public&quot; from their Teenure profile.
            </p>
          </div>
        ) : null}

        {profile && profile.public ? (
          <div className="flex flex-col gap-5 rounded-[var(--r-lg)] border border-[var(--vl-border)] bg-[var(--vl-bg)] p-6 shadow-sm">
            <div className="flex flex-col items-start gap-1">
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold tracking-tight">{profile.display_name}</h1>
                <UiBadge variant="verified">VERIFIED ✓</UiBadge>
              </div>
              <p className="text-sm text-[var(--vl-text-2)]">
                {profile.school_name} &middot; Class of {profile.graduation_year}
              </p>
              <p className="text-sm text-[var(--vl-text-2)]">{profile.city}</p>
            </div>

            <div className="flex flex-wrap gap-1.5">
              {(profile.categories ?? []).map((c) => (
                <span
                  key={c}
                  className="rounded-md border border-[var(--vl-border)] bg-[var(--vl-chip-bg)] px-2 py-0.5 text-xs font-medium text-[var(--vl-chip-text)]"
                >
                  {CATEGORY_LABELS[c as keyof typeof CATEGORY_LABELS] ?? c}
                </span>
              ))}
            </div>

            <div className="grid grid-cols-2 gap-3 rounded-[var(--r-md)] bg-[var(--vl-surface)] p-4 text-center sm:grid-cols-3">
              <div>
                <p className="text-xl font-semibold">{profile.brand_campaigns_completed}</p>
                <p className="text-xs text-[var(--vl-text-2)]">Campaigns completed</p>
              </div>
              <div>
                <p className="text-xl font-semibold">
                  {profile.brand_average_rating != null ? profile.brand_average_rating.toFixed(1) : "—"}
                </p>
                <p className="text-xs text-[var(--vl-text-2)]">Average rating</p>
              </div>
              {profile.total_earnings_cents != null ? (
                <div>
                  {/* DS number rule: an earned dollar amount is the credential
                      accent, even on the light-mode page -- a darkened gold
                      tone so it holds contrast against a white background. */}
                  <p className="text-xl font-bold text-[var(--vl-gold-earned)]">
                    ${(profile.total_earnings_cents / 100).toFixed(2)}
                  </p>
                  <p className="text-xs text-[var(--vl-text-2)]">Total earnings</p>
                </div>
              ) : null}
            </div>

            {profile.badges && profile.badges.length > 0 ? (
              <div className="flex flex-col gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-[var(--vl-text-2)]">Badges earned</p>
                <div className="flex flex-wrap gap-1.5">
                  {profile.badges.map((b) => (
                    <span
                      key={b.module_id}
                      className="rounded-md border border-[var(--vl-border)] px-2 py-0.5 text-xs font-medium text-[var(--vl-chip-text)]"
                    >
                      {b.badge_title}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            {profile.athletic_tracks_enabled && profile.attested_seasons && profile.attested_seasons.length > 0 ? (
              <div className="flex flex-col gap-3 border-t border-[var(--vl-border)] pt-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-[var(--vl-text-2)]">
                  Athletic Record
                </p>
                {profile.attested_seasons.map((s, i) => (
                  <div
                    key={i}
                    className="flex flex-col gap-2 rounded-[var(--r-md)] border border-[var(--vl-border)] bg-[var(--vl-surface)] p-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="rounded-md border border-[var(--vl-border)] bg-[var(--vl-chip-bg)] px-2 py-0.5 text-xs font-medium text-[var(--vl-chip-text)]">
                          {SPORT_LABELS[s.sport as SupportedSport] ?? s.sport}
                        </span>
                        <span className="text-sm text-[var(--vl-text-2)]">
                          {s.season_year} · {s.team_name}
                          {s.level ? ` · ${SEASON_LEVEL_LABELS[s.level as keyof typeof SEASON_LEVEL_LABELS] ?? s.level}` : ""}
                        </span>
                      </div>
                      <div className="flex gap-1.5">
                        {s.coach_verified ? (
                          <UiBadge variant="earned">Coach Verified</UiBadge>
                        ) : null}
                        {s.admin_verified ? (
                          <UiBadge variant="success">Platform Verified</UiBadge>
                        ) : null}
                      </div>
                    </div>

                    {Object.keys(s.selected_stats).length > 0 ? (
                      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-3">
                        {(SPORT_STATS_FIELDS[s.sport as SupportedSport] ?? [])
                          .filter((f) => s.selected_stats[f.key] !== undefined)
                          .map((f) => (
                            <div key={f.key} className="flex flex-col">
                              <span className="text-xs text-[var(--vl-text-2)]">{f.label}</span>
                              <span className="text-sm font-medium">{String(s.selected_stats[f.key])}</span>
                            </div>
                          ))}
                      </div>
                    ) : null}

                    {s.achievements && s.achievements.length > 0 ? (
                      <div className="flex flex-col gap-1">
                        {s.achievements.map((a, j) => (
                          <p key={j} className="text-sm">
                            {String(a.title)}{" "}
                            <span className="text-[var(--vl-text-2)]">({String(a.type)})</span>
                          </p>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : null}

            <div className="flex flex-col gap-1 border-t border-[var(--vl-border)] pt-4">
              {profile.last_updated ? (
                <p className="text-xs text-[var(--vl-text-3)]">
                  Last updated {new Date(profile.last_updated).toLocaleDateString()}
                </p>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>
    </main>
  );
}
