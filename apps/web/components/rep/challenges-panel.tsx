"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import type { RepAvailableChallenge, RepSubmittedChallenge } from "@/lib/types";

function money(cents: number | null): string {
  if (cents === null) return "—";
  return `$${(cents / 100).toFixed(2)}`;
}

/** Discovery panel on the rep dashboard (Build Prompt 8G frontend
 * deliverable). Visually distinct from the Campaigns panel -- a
 * different header treatment and an explicit "unpaid" label -- so a
 * rep never confuses a challenge for a guaranteed-pay campaign. */
export function ChallengesDiscoveryPanel({ challenges }: { challenges: RepAvailableChallenge[] }) {
  return (
    <section className="flex flex-col gap-3 rounded-xl border border-dashed border-border bg-card/60 p-4">
      <div>
        <h2 className="text-sm font-semibold text-muted-foreground">Brand Challenges — Unpaid Discovery</h2>
        <p className="text-xs text-muted-foreground">
          Submit your creative work. Brands may invite you to a paid campaign based on what you submit.
        </p>
      </div>
      {challenges.length === 0 ? (
        <EmptyState title="No open challenges right now" description="Check back soon for new brand challenges." />
      ) : (
        <div className="flex flex-col gap-3">
          {challenges.map((c) => (
            <Link key={c.id} href={`/rep/challenges/${c.id}`} className="block">
              <Card className="min-h-11 hover:border-primary/30 hover:shadow-md">
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle>{c.title}</CardTitle>
                    <Badge variant="outline">{c.category}</Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="line-clamp-2 text-sm text-muted-foreground">{c.brief}</p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

/** Submitted challenges panel -- status copy per spec. No declined
 * state is ever rendered: the backend already excludes declined rows
 * from the list this reads. */
export function SubmittedChallengesPanel({ submissions }: { submissions: RepSubmittedChallenge[] }) {
  if (submissions.length === 0) return null;
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold text-muted-foreground">Your challenge submissions</h2>
      <div className="flex flex-col gap-2">
        {submissions.map((s) => (
          <Card key={s.challenge_id} className="p-4">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-sm font-medium">{s.challenge_title}</p>
                {s.status === "converted" ? (
                  <p className="text-sm text-muted-foreground">
                    Brand invited you to {s.campaign_title ?? "a campaign"}. +{money(s.bonus_cents)} bonus added to
                    your earnings.
                  </p>
                ) : (
                  <p className="text-sm text-muted-foreground">Submitted — brand is reviewing</p>
                )}
              </div>
              <Badge variant={s.status === "converted" ? "success" : "secondary"}>
                {s.status === "converted" ? "Converted" : "Submitted"}
              </Badge>
            </div>
          </Card>
        ))}
      </div>
    </section>
  );
}
