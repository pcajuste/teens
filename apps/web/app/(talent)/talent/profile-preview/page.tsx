"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ProfileView } from "@/components/talent/profile-view";
import { AchievementLinkShare } from "@/components/talent/achievement-link-share";
import { api, ApiError } from "@/lib/api";
import type { TalentProfilePreview } from "@/lib/types";

// Deliberately fetches GET /talents/me/profile-preview, not /talents/me --
// this must render exactly what a brand/recruiter sees, via the same
// ProfileView component the real profile screen uses.
export default function ProfilePreviewPage() {
  const [preview, setPreview] = useState<TalentProfilePreview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<TalentProfilePreview>("/talents/me/profile-preview")
      .then(setPreview)
      .catch((err) =>
        setError(
          err instanceof ApiError ? err.message : "Could not load preview.",
        ),
      );
  }, []);

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">
          How brands & recruiters see you
        </h1>
        <Link href="/talent" className="text-sm font-medium underline">
          Back
        </Link>
      </div>
      <p className="text-sm text-muted-foreground">
        This is a live preview from the same data a brand or recruiter would see
        -- it can never drift from the real thing.
      </p>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {preview ? <ProfileView profile={preview} /> : null}
      {preview ? <AchievementLinkShare /> : null}
      {preview ? (
        <Link
          href="/talent/achievement-record"
          className="text-center text-sm font-medium underline underline-offset-2"
        >
          Download Achievement Record
        </Link>
      ) : null}
    </main>
  );
}
