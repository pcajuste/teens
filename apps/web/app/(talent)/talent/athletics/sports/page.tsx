"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AthleticsGate } from "@/components/talent/athletics-gate";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { SPORT_LABELS, type SupportedSport } from "@/lib/sports";
import type { SportProfile } from "@/lib/types";

export default function SportProfilesPage() {
  return (
    <AthleticsGate title="Sport profiles" backHref="/talent/athletics" render={() => <SportsList />} />
  );
}

function SportsList() {
  const [sports, setSports] = useState<SportProfile[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<SportProfile[]>("/talents/athletics/sports")
      .then(setSports)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load your sport profiles."));
  }, []);

  if (error) {
    return <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>;
  }

  if (sports === null) {
    return <Skeleton className="h-32 w-full" />;
  }

  return (
    <div className="flex flex-col gap-4">
      {sports.length === 0 ? (
        <EmptyState title="No sports set up yet" description="Add a sport to start tracking your stats." />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {sports.map((sp) => (
            <Link key={sp.id} href={`/talent/athletics/sports/${sp.sport}`}>
              <Card className="flex h-full flex-col gap-2 p-4">
                <p className="text-sm font-semibold">{SPORT_LABELS[sp.sport as SupportedSport] ?? sp.sport}</p>
                {sp.positions.length > 0 ? (
                  <p className="text-xs text-muted-foreground">{sp.positions.join(", ")}</p>
                ) : (
                  <p className="text-xs text-muted-foreground">No positions set</p>
                )}
                <div className="flex flex-wrap gap-1.5">
                  <Badge variant={sp.gpa !== null ? "done" : "pending"}>
                    {sp.gpa !== null ? `GPA ${sp.gpa.toFixed(2)}` : "No GPA"}
                  </Badge>
                  <Badge variant={sp.hudl_url || sp.maxpreps_url ? "done" : "pending"}>
                    {sp.hudl_url || sp.maxpreps_url ? "Film linked" : "No film"}
                  </Badge>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
      <Link href="/talent/athletics/sports/new">
        <Button size="lg" className="w-full">
          Add a sport
        </Button>
      </Link>
    </div>
  );
}
