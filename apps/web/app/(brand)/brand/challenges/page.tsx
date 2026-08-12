"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { BrandShell } from "@/components/brand/brand-shell";
import { api, ApiError } from "@/lib/api";
import type { Challenge, ChallengeStatus } from "@/lib/types";

const STATUS_VARIANT: Record<ChallengeStatus, "outline" | "success" | "secondary"> = {
  draft: "outline",
  active: "success",
  closed: "secondary",
};

const STATUS_LABEL: Record<ChallengeStatus, string> = {
  draft: "Draft",
  active: "Active",
  closed: "Closed",
};

const ZERO_CONVERSION_SUBMISSIONS_THRESHOLD = 30;

export default function BrandChallengesPage() {
  const [challenges, setChallenges] = useState<Challenge[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Challenge[]>("/brands/challenges")
      .then(setChallenges)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load your challenges."));
  }, []);

  const zeroConversionWarning = (challenges ?? []).some(
    (c) => c.status === "closed" && c.submissions_count >= ZERO_CONVERSION_SUBMISSIONS_THRESHOLD && c.conversion_count === 0
  );

  return (
    <BrandShell
      title="Challenges"
      action={
        <Link href="/brand/challenges/new">
          <Button size="lg">New challenge</Button>
        </Link>
      }
    >
      {error ? <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p> : null}

      {zeroConversionWarning ? (
        <Card className="border-warning/40 bg-warning/10 p-4 text-sm">
          Consider using challenges to discover reps for active campaigns. Reps invest time in submissions --
          converting the best ones builds your brand reputation on Teenure.
        </Card>
      ) : null}

      {challenges === null ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
        </div>
      ) : challenges.length === 0 ? (
        <EmptyState
          title="No challenges yet"
          description="Post an open creative brief to discover reps before committing campaign budget."
          action={
            <Link href="/brand/challenges/new">
              <Button>Create a challenge</Button>
            </Link>
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {challenges.map((c) => (
            <Link key={c.id} href={`/brand/challenges/${c.id}`}>
              <Card className="hover:border-primary/30 hover:shadow-md">
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle>{c.title}</CardTitle>
                    <Badge variant={STATUS_VARIANT[c.status]}>{STATUS_LABEL[c.status]}</Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">{c.category}</p>
                  <div className="flex items-center justify-between pt-2 text-sm">
                    <span className="text-muted-foreground">{c.submissions_count} submissions</span>
                    <span className="font-semibold text-foreground">
                      {c.conversion_rate != null ? `${Math.round(c.conversion_rate * 100)}% converted` : "—"}
                    </span>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </BrandShell>
  );
}
