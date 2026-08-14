"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AthleticsGate } from "@/components/talent/athletics-gate";
import { SportStatsForm } from "@/components/talent/sport-stats-form";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import {
  SEASON_LEVELS,
  SEASON_LEVEL_LABELS,
  SEASON_TYPES,
  SEASON_TYPE_LABELS,
  SPORT_LABELS,
  SUPPORTED_SPORTS,
  type SupportedSport,
} from "@/lib/sports";
import type { AthleticSeason, CreateAthleticSeasonRequest } from "@/lib/types";

const CURRENT_YEAR = new Date().getFullYear();

export default function NewSeasonPage() {
  const searchParams = useSearchParams();
  const editId = searchParams.get("edit");
  return (
    <AthleticsGate
      title={editId ? "Edit season" : "Add a season"}
      backHref="/talent/athletics/seasons"
      render={() => <NewSeasonForm editId={editId} />}
    />
  );
}

function NewSeasonForm({ editId }: { editId: string | null }) {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [loadingExisting, setLoadingExisting] = useState(!!editId);

  const [sport, setSport] = useState<SupportedSport>("football");
  const [seasonYear, setSeasonYear] = useState(CURRENT_YEAR);
  const [seasonType, setSeasonType] = useState<(typeof SEASON_TYPES)[number]>("high_school");
  const [teamName, setTeamName] = useState("");
  const [level, setLevel] = useState<(typeof SEASON_LEVELS)[number]>("varsity");

  const [stats, setStats] = useState<Record<string, unknown>>({});
  const [statsServerError, setStatsServerError] = useState<string | null>(null);

  const [coachName, setCoachName] = useState("");
  const [coachEmail, setCoachEmail] = useState("");

  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const step1Valid = teamName.trim().length > 0;

  useEffect(() => {
    if (!editId) return;
    api
      .get<AthleticSeason>(`/talents/athletics/seasons/${editId}`)
      .then((s) => {
        setSport(s.sport as SupportedSport);
        setSeasonYear(s.season_year);
        setSeasonType(s.season_type as (typeof SEASON_TYPES)[number]);
        setTeamName(s.team_name);
        setLevel(s.level as (typeof SEASON_LEVELS)[number]);
        setStats(s.sport_stats);
        setCoachName(s.coach_name ?? "");
        setCoachEmail(s.coach_email ?? "");
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load this season."))
      .finally(() => setLoadingExisting(false));
  }, [editId]);

  async function handleSubmit() {
    setPending(true);
    setError(null);
    setStatsServerError(null);
    const body: CreateAthleticSeasonRequest = {
      sport,
      season_year: seasonYear,
      season_type: seasonType,
      team_name: teamName.trim(),
      level,
      sport_stats: stats,
      coach_name: coachName.trim() || null,
      coach_email: coachEmail.trim() || null,
    };
    try {
      const saved = editId
        ? await api.put<AthleticSeason>(`/talents/athletics/seasons/${editId}`, body)
        : await api.post<AthleticSeason>("/talents/athletics/seasons", body);
      router.push(`/talent/athletics/seasons/${saved.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.code === "invalid_sport_stats") {
        setStatsServerError(err.message);
        setStep(2);
      } else if (err instanceof ApiError && err.code === "season_not_editable") {
        setError("This season can no longer be edited (it's left draft status).");
      } else {
        setError(err instanceof ApiError ? err.message : "Could not save this season.");
      }
    } finally {
      setPending(false);
    }
  }

  if (loadingExisting) {
    return <Skeleton className="h-64 w-full" />;
  }

  return (
    <div className="flex flex-col gap-6 pb-8">
      <p className="text-xs font-medium text-muted-foreground">Step {step} of 3</p>

      {error ? (
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      ) : null}

      {step === 1 ? (
        <Card className="flex flex-col gap-4 p-5">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="sport">Sport</Label>
            <select
              id="sport"
              value={sport}
              onChange={(e) => setSport(e.target.value as SupportedSport)}
              className="h-9 w-full rounded-lg border border-input bg-white/4 px-3 text-sm"
            >
              {SUPPORTED_SPORTS.map((s) => (
                <option key={s} value={s}>
                  {SPORT_LABELS[s]}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="season_year">Season year</Label>
            <Input
              id="season_year"
              type="number"
              min={2015}
              max={2035}
              value={seasonYear}
              onChange={(e) => setSeasonYear(Number(e.target.value))}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="season_type">Season type</Label>
            <select
              id="season_type"
              value={seasonType}
              onChange={(e) => setSeasonType(e.target.value as (typeof SEASON_TYPES)[number])}
              className="h-9 w-full rounded-lg border border-input bg-white/4 px-3 text-sm"
            >
              {SEASON_TYPES.map((t) => (
                <option key={t} value={t}>
                  {SEASON_TYPE_LABELS[t]}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="team_name">Team name</Label>
            <Input id="team_name" value={teamName} onChange={(e) => setTeamName(e.target.value)} required />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="level">Level</Label>
            <select
              id="level"
              value={level}
              onChange={(e) => setLevel(e.target.value as (typeof SEASON_LEVELS)[number])}
              className="h-9 w-full rounded-lg border border-input bg-white/4 px-3 text-sm"
            >
              {SEASON_LEVELS.map((l) => (
                <option key={l} value={l}>
                  {SEASON_LEVEL_LABELS[l]}
                </option>
              ))}
            </select>
          </div>
        </Card>
      ) : null}

      {step === 2 ? (
        <Card className="flex flex-col gap-4 p-5">
          <p className="text-sm font-semibold">Season stats</p>
          <SportStatsForm sport={sport} value={stats} onChange={setStats} serverError={statsServerError} />
        </Card>
      ) : null}

      {step === 3 ? (
        <Card className="flex flex-col gap-4 p-5">
          <div>
            <p className="text-sm font-semibold">Coach info</p>
            <p className="text-xs text-muted-foreground">
              Optional but required to request attestation later.
            </p>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="coach_name">Coach name</Label>
            <Input id="coach_name" value={coachName} onChange={(e) => setCoachName(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="coach_email">Coach email</Label>
            <Input
              id="coach_email"
              type="email"
              value={coachEmail}
              onChange={(e) => setCoachEmail(e.target.value)}
            />
          </div>
        </Card>
      ) : null}

      {/* Sticky footer keeps the submit button reachable above the phone
         keyboard -- ATHLETICS-6 acceptance criterion: "no submit button
         hidden below the fold when the keyboard is up." */}
      <div className="sticky bottom-0 flex gap-2 bg-background pt-2">
        {step > 1 ? (
          <Button type="button" variant="outline" className="flex-1" onClick={() => setStep(step - 1)}>
            Back
          </Button>
        ) : null}
        {step < 3 ? (
          <Button
            type="button"
            className="flex-1"
            disabled={step === 1 && !step1Valid}
            onClick={() => setStep(step + 1)}
          >
            Next
          </Button>
        ) : (
          <Button type="button" className="flex-1" disabled={pending} onClick={handleSubmit}>
            {pending ? "Saving…" : editId ? "Save changes" : "Create season"}
          </Button>
        )}
      </div>
    </div>
  );
}
