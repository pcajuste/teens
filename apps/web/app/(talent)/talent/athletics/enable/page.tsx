"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { TalentShell } from "@/components/talent/talent-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import type { EnableAthleticTrackResponse } from "@/lib/types";

export default function EnableAthleticsPage() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleEnable() {
    setPending(true);
    setError(null);
    try {
      await api.post<EnableAthleticTrackResponse>("/talents/athletics/enable");
      // First setup step per the spec.
      router.push("/talent/athletics/sports");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not enable your athletic profile. Try again.");
      setPending(false);
    }
  }

  return (
    <TalentShell title="Set up Athletics" backHref="/talent">
      <div className="flex flex-col gap-6">
        <Card className="flex flex-col gap-3 p-5">
          <h1 className="text-lg font-semibold">Your athletic profile</h1>
          <p className="text-sm text-muted-foreground">
            The athletic track is a separate, verified record of your seasons -- built for college
            program recruiters, not brands. It&apos;s optional and doesn&apos;t change anything about
            your existing brand profile.
          </p>

          <div className="flex flex-col gap-3">
            <div>
              <p className="text-sm font-semibold">What you&apos;ll add</p>
              <p className="text-sm text-muted-foreground">
                Sport profiles (positions, GPA, film links) and season-by-season stats -- football,
                basketball, track, and more.
              </p>
            </div>
            <div>
              <p className="text-sm font-semibold">Coach attestation</p>
              <p className="text-sm text-muted-foreground">
                You can ask your coach to confirm a season&apos;s stats by email. Coach-verified
                seasons carry a gold &quot;Coach Verified&quot; badge.
              </p>
            </div>
            <div>
              <p className="text-sm font-semibold">Who sees it</p>
              <p className="text-sm text-muted-foreground">
                College program recruiters on Teenure. Your athletic profile is never shown to
                brands, and brands never see your athletic stats.
              </p>
            </div>
          </div>

          <p className="text-xs text-muted-foreground">
            No account changes are required -- this just turns on a new section of your profile.
          </p>
        </Card>

        {error ? (
          <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
        ) : null}

        <Button size="lg" disabled={pending} onClick={handleEnable}>
          {pending ? "Enabling…" : "Enable my athletic profile"}
        </Button>
      </div>
    </TalentShell>
  );
}
