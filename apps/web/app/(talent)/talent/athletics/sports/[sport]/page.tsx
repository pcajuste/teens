"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AthleticsGate } from "@/components/talent/athletics-gate";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { SPORT_LABELS, SPORT_POSITIONS, SUPPORTED_SPORTS, type SupportedSport } from "@/lib/sports";
import type { SportProfile, SportProfileUpdateRequest } from "@/lib/types";

/**
 * Doubles as both the "add a sport" and "edit a sport" screen. Route
 * deliverable list (ATHLETICS-6) has a single dynamic file here, so the
 * literal segment "new" is handled as a sport-picker step rather than a
 * separate sports/new/page.tsx -- once a sport is chosen this renders
 * the same form a returning edit would, just with sport writable
 * instead of locked.
 */
export default function SportProfileFormPage() {
  const params = useParams<{ sport: string }>();
  const router = useRouter();

  if (params.sport === "new") {
    return <SportPicker />;
  }

  return (
    <AthleticsGate
      title={SPORT_LABELS[params.sport as SupportedSport] ?? params.sport}
      backHref="/talent/athletics/sports"
      render={() => <SportForm sport={params.sport} router={router} />}
    />
  );
}

function SportPicker() {
  const router = useRouter();
  return (
    <AthleticsGate
      title="Add a sport"
      backHref="/talent/athletics/sports"
      render={() => (
        <div className="grid grid-cols-2 gap-3">
          {SUPPORTED_SPORTS.map((sport) => (
            <Button
              key={sport}
              variant="outline"
              className="h-auto min-h-[44px] justify-start py-3"
              onClick={() => router.push(`/talent/athletics/sports/${sport}`)}
            >
              {SPORT_LABELS[sport]}
            </Button>
          ))}
        </div>
      )}
    />
  );
}

function SportForm({ sport, router }: { sport: string; router: ReturnType<typeof useRouter> }) {
  const isSupported = SUPPORTED_SPORTS.includes(sport as SupportedSport);
  const [existing, setExisting] = useState<SportProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [positions, setPositions] = useState<string[]>([]);
  const [gpa, setGpa] = useState("");
  const [hudlUrl, setHudlUrl] = useState("");
  const [maxprepsUrl, setMaxprepsUrl] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api
      .get<SportProfile[]>("/talents/athletics/sports")
      .then((list) => {
        const found = list.find((sp) => sp.sport === sport) ?? null;
        setExisting(found);
        if (found) {
          setPositions(found.positions);
          setGpa(found.gpa !== null ? String(found.gpa) : "");
          setHudlUrl(found.hudl_url ?? "");
          setMaxprepsUrl(found.maxpreps_url ?? "");
        }
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load this sport."))
      .finally(() => setLoading(false));
  }, [sport]);

  function togglePosition(pos: string) {
    setPositions((prev) => (prev.includes(pos) ? prev.filter((p) => p !== pos) : [...prev, pos]));
  }

  async function handleSave() {
    setPending(true);
    setError(null);
    const gpaNum = gpa.trim() ? parseFloat(gpa) : null;
    if (gpaNum !== null && (Number.isNaN(gpaNum) || gpaNum < 0 || gpaNum > 4)) {
      setError("GPA must be between 0.0 and 4.0.");
      setPending(false);
      return;
    }
    // Interpreted gap: the ATHLETICS-6 prompt describes a per-sport
    // "sport_stats section" on this page, but the sport_profiles table
    // and SportProfileUpdateRequest schema built in ATHLETICS-1 (see
    // apps/api/app/schemas/athletics.py and
    // apps/api/app/repositories/sport_profiles_repository.py) have no
    // sport_stats column -- only athletic_seasons rows carry sport_stats.
    // Sending it here would be silently dropped by the API, so this
    // form omits it; the season creation/edit form is the only place
    // sport_stats is actually collected and persisted.
    const body: SportProfileUpdateRequest = {
      sport,
      positions,
      gpa: gpaNum,
      hudl_url: hudlUrl.trim() || null,
      maxpreps_url: maxprepsUrl.trim() || null,
    };
    try {
      await api.put<SportProfile>(`/talents/athletics/sports/${sport}`, body);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save this sport profile.");
    } finally {
      setPending(false);
    }
  }

  if (!isSupported) {
    return (
      <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
        &quot;{sport}&quot; isn&apos;t a supported sport. Go back and pick from the list.
      </p>
    );
  }

  if (loading) {
    return <Skeleton className="h-64 w-full" />;
  }

  const positionChoices = SPORT_POSITIONS[sport as SupportedSport] ?? [];

  return (
    <div className="flex flex-col gap-6">
      {error ? (
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      ) : null}
      {saved ? (
        <p className="rounded-lg bg-green-dim px-3 py-2 text-sm text-green">Saved.</p>
      ) : null}

      <Card className="flex flex-col gap-4 p-5">
        <div>
          <Label>Sport</Label>
          {/* Locked after first save, per spec. */}
          <p className="mt-1 text-sm font-medium">{SPORT_LABELS[sport as SupportedSport]}</p>
        </div>

        {positionChoices.length > 0 ? (
          <div className="flex flex-col gap-1.5">
            <Label>Positions</Label>
            <div className="flex flex-wrap gap-2">
              {positionChoices.map((pos) => (
                <button
                  key={pos}
                  type="button"
                  onClick={() => togglePosition(pos)}
                  className={`min-h-[44px] rounded-full border px-3 py-2 text-sm font-medium ${
                    positions.includes(pos)
                      ? "border-teal-border bg-teal-dim text-teal"
                      : "border-border-muted text-text-2"
                  }`}
                >
                  {pos}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="gpa">GPA (optional)</Label>
          <Input
            id="gpa"
            type="number"
            inputMode="decimal"
            step="0.01"
            min={0}
            max={4}
            placeholder="0.0 – 4.0"
            value={gpa}
            onChange={(e) => setGpa(e.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="hudl">Hudl URL (optional)</Label>
          <Input id="hudl" placeholder="https://hudl.com/..." value={hudlUrl} onChange={(e) => setHudlUrl(e.target.value)} />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="maxpreps">MaxPreps URL (optional)</Label>
          <Input
            id="maxpreps"
            placeholder="https://maxpreps.com/..."
            value={maxprepsUrl}
            onChange={(e) => setMaxprepsUrl(e.target.value)}
          />
        </div>
      </Card>

      <Button size="lg" disabled={pending} onClick={handleSave}>
        {pending ? "Saving…" : existing ? "Save changes" : "Save sport profile"}
      </Button>
    </div>
  );
}
