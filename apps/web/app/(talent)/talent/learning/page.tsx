"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { TalentShell } from "@/components/talent/talent-shell";
import { BadgeChipRow } from "@/components/talent/badge-chip";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import type { ModuleAvailable, ModuleCompleted, TalentProfile } from "@/lib/types";

/** Learning Hub (Build Prompt 8H frontend spec) -- reachable from main
 * nav, not buried in settings/profile. A talent with zero campaigns lands
 * here by default per the spec's purpose #1; that dashboard-level
 * routing decision lives in app/(talent)/talent/page.tsx, this page is the
 * hub itself. */
export default function LearningHubPage() {
  const [available, setAvailable] = useState<ModuleAvailable[]>([]);
  const [completed, setCompleted] = useState<ModuleCompleted[]>([]);
  const [profile, setProfile] = useState<TalentProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<ModuleAvailable[]>("/talents/modules/available"),
      api.get<ModuleCompleted[]>("/talents/modules/completed"),
      api.get<TalentProfile>("/talents/me"),
    ])
      .then(([a, c, p]) => {
        setAvailable(a);
        setCompleted(c);
        setProfile(p);
      })
      .catch((err) =>
        setError(
          err instanceof ApiError
            ? err.message
            : "Could not load the Learning Hub.",
        ),
      )
      .finally(() => setLoading(false));
  }, []);

  return (
    <TalentShell title="Learning Hub" backHref="/talent">
      <div className="flex flex-col gap-8">
        {error ? (
          <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        ) : null}

        {loading ? (
          <div className="flex flex-col gap-4">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : (
          <>
            {profile && profile.badges.length > 0 ? (
              <section className="flex flex-col gap-2">
                <h2 className="text-sm font-semibold text-muted-foreground">
                  Your badges
                </h2>
                <BadgeChipRow badges={profile.badges} />
              </section>
            ) : null}

            <section className="flex flex-col gap-3">
              <h2 className="text-sm font-semibold text-muted-foreground">
                Available modules
              </h2>
              {available.length === 0 ? (
                <EmptyState
                  title="You're caught up"
                  description="No modules available right now. Check back soon for new content."
                />
              ) : (
                <div className="flex flex-col gap-3">
                  {available.map((m) => (
                    <ModuleCard key={m.id} module={m} />
                  ))}
                </div>
              )}
            </section>

            {completed.length > 0 ? (
              <section className="flex flex-col gap-3">
                <h2 className="text-sm font-semibold text-muted-foreground">
                  Completed modules
                </h2>
                <div className="flex flex-col gap-2">
                  {completed.map((m) => (
                    <Card
                      key={m.module_id}
                      className="flex items-center justify-between gap-3 p-4"
                    >
                      <div>
                        <p
                          className="inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold text-white"
                          style={{ backgroundColor: m.badge_color }}
                        >
                          {m.badge_title}
                        </p>
                        <p className="mt-1 text-sm font-medium">{m.title}</p>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {m.passed_at
                          ? new Date(m.passed_at).toLocaleDateString()
                          : ""}
                      </p>
                    </Card>
                  ))}
                </div>
              </section>
            ) : null}
          </>
        )}
      </div>
    </TalentShell>
  );
}

function ModuleCard({ module }: { module: ModuleAvailable }) {
  const isFtc = module.title === "FTC Disclosure Essentials";
  const progress = module.talent_progress;
  return (
    <Link href={`/talent/learning/${module.id}`} className="block">
      <Card className="min-h-11 hover:border-primary/30 hover:shadow-md">
        <div className="flex flex-col gap-2 p-4">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span
                className="inline-block size-3 shrink-0 rounded-full"
                style={{ backgroundColor: module.badge_color }}
                aria-hidden="true"
              />
              <p className="text-sm font-semibold">{module.title}</p>
            </div>
            {isFtc ? (
              <Badge variant="destructive">Required before campaigns</Badge>
            ) : null}
          </div>
          <p className="line-clamp-2 text-sm text-muted-foreground">
            {module.description}
          </p>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>{module.estimated_minutes} min</span>
            {progress?.status === "in_progress" ? (
              <Badge variant="secondary">In progress</Badge>
            ) : null}
            {progress?.status === "failed" ? (
              <Badge variant="outline">Retake available</Badge>
            ) : null}
          </div>
        </div>
      </Card>
    </Link>
  );
}
