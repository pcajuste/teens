"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AthleticsGate } from "@/components/talent/athletics-gate";
import { SeasonStatusChip } from "@/components/talent/season-status-chip";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { SEASON_TYPE_LABELS, SPORT_LABELS, type SupportedSport } from "@/lib/sports";
import type { AthleticSeason } from "@/lib/types";

export default function SeasonsListPage() {
  return <AthleticsGate title="Seasons" backHref="/talent/athletics" render={() => <SeasonsList />} />;
}

function SeasonsList() {
  const [seasons, setSeasons] = useState<AthleticSeason[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<AthleticSeason[]>("/talents/athletics/seasons")
      .then((list) => setSeasons([...list].sort((a, b) => b.season_year - a.season_year)))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load your seasons."));
  }, []);

  if (error) {
    return <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>;
  }

  if (seasons === null) {
    return <Skeleton className="h-32 w-full" />;
  }

  return (
    <div className="flex flex-col gap-4">
      {seasons.length === 0 ? (
        <EmptyState title="No seasons yet" description="Add your first season to start building your athletic record." />
      ) : (
        <div className="flex flex-col gap-2">
          {seasons.map((s) => (
            <Link key={s.id} href={`/talent/athletics/seasons/${s.id}`}>
              <Card className="flex flex-row items-center justify-between gap-2 p-4">
                <div>
                  <p className="text-sm font-semibold">
                    {SPORT_LABELS[s.sport as SupportedSport] ?? s.sport} · {s.season_year}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {s.team_name} ·{" "}
                    {SEASON_TYPE_LABELS[s.season_type as keyof typeof SEASON_TYPE_LABELS] ?? s.season_type}
                  </p>
                </div>
                <SeasonStatusChip season={s} />
              </Card>
            </Link>
          ))}
        </div>
      )}
      <Link href="/talent/athletics/seasons/new">
        <Button size="lg" className="w-full">
          Add a season
        </Button>
      </Link>
    </div>
  );
}
