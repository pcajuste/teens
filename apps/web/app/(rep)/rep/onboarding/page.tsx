"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { RepProfile } from "@/lib/types";
import { ProfileForm } from "@/components/rep/profile-form";

export default function OnboardingPage() {
  const [profile, setProfile] = useState<RepProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getRepProfile()
      .then(setProfile)
      .catch((err) => setError(err instanceof ApiError ? String(err.detail ?? err.message) : "Could not load your profile."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="container max-w-lg py-6">
      <h1 className="mb-1 text-xl font-semibold">Set up your profile</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        This is what brands and, if you opt in, recruiters will see.
      </p>
      {loading && <p className="text-muted-foreground">Loading…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!loading && !error && <ProfileForm initial={profile ?? {}} mode="onboarding" />}
    </main>
  );
}
