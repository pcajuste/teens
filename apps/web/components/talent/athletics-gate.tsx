"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Skeleton } from "@/components/ui/skeleton";
import { TalentShell } from "@/components/talent/talent-shell";
import { api, ApiError } from "@/lib/api";
import type { TalentProfile } from "@/lib/types";

/**
 * Shared track-gate for every /talent/athletics/* sub-page (except the
 * enable page itself, which intentionally renders without this gate).
 *
 * ATHLETICS-6 acceptance criterion: "Accessing /talent/athletics/seasons
 * (or any sub-page) without the athletic track enabled redirects to
 * /talent/athletics/enable. No flash of content before redirect." --
 * so this checks GET /talents/me client-side and redirects before ever
 * calling render(profile) with page content; while the check is in
 * flight it shows a skeleton, never the page body.
 */
export function AthleticsGate({
  title,
  backHref = "/talent/athletics",
  render,
}: {
  title?: string;
  backHref?: string;
  render: (profile: TalentProfile, reload: () => void) => React.ReactNode;
}) {
  const router = useRouter();
  const [profile, setProfile] = useState<TalentProfile | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api
      .get<TalentProfile>("/talents/me")
      .then((p) => {
        if (!p.enabled_tracks.includes("athletics")) {
          router.replace("/talent/athletics/enable");
          return;
        }
        setProfile(p);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.code === "talent_profile_not_found") {
          router.replace("/talent/onboarding");
          return;
        }
        setError(err instanceof ApiError ? err.message : "Could not load your profile.");
      });
  }

  useEffect(load, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (error) {
    return (
      <TalentShell title={title} backHref={backHref}>
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
      </TalentShell>
    );
  }

  if (!profile) {
    return (
      <TalentShell title={title} backHref={backHref}>
        <Skeleton className="h-40 w-full" />
      </TalentShell>
    );
  }

  return (
    <TalentShell title={title} backHref={backHref}>
      {render(profile, load)}
    </TalentShell>
  );
}
