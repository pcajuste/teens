"use client";

import { useEffect, useState } from "react";
import { PortalShell } from "@/components/portal-shell";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { TalentProfile } from "@/lib/types";

interface TalentShellProps {
  title?: string;
  backHref?: string;
  children: React.ReactNode;
}

const BASE_NAV = [
  { href: "/talent", label: "Dashboard" },
  { href: "/talent/learning", label: "Learning Hub" },
  { href: "/talent/scholarships", label: "Scholarships" },
  { href: "/talent/internships", label: "Internships" },
  { href: "/talent/insight-feedback", label: "Insight & Feedback" },
  { href: "/talent/profile-preview", label: "Preview profile" },
];

/** Shared page shell for every authenticated /talent/* screen -- the DS
 * sidebar pattern (Section 3E/6), same shape as every other portal shell.
 *
 * ATHLETICS-6: fetches its own /talents/me so the "Athletics" nav item
 * can reflect enabled_tracks regardless of which page renders the
 * shell -- every athletics page needs the shell anyway, and pages that
 * already fetch the profile just pay one extra cheap GET rather than
 * threading enabled_tracks through props on every call site. */
export function TalentShell({ title, backHref, children }: TalentShellProps) {
  const { signOut } = useAuth();
  const [athleticsEnabled, setAthleticsEnabled] = useState<boolean | null>(null);

  useEffect(() => {
    api
      .get<TalentProfile>("/talents/me")
      .then((profile) => setAthleticsEnabled(profile.enabled_tracks.includes("athletics")))
      .catch((err) => {
        // talent_profile_not_found during onboarding, or any other
        // fetch failure -- fall back to the "not enabled" nav label
        // rather than blocking the shell from rendering.
        if (!(err instanceof ApiError)) {
          // no-op: still resolves to false below
        }
        setAthleticsEnabled(false);
      });
  }, []);

  const navItems = [
    ...BASE_NAV,
    athleticsEnabled
      ? { href: "/talent/athletics", label: "Athletics" }
      : { href: "/talent/athletics/enable", label: "Set up Athletics →" },
  ];

  return (
    <PortalShell
      portalLabel="Talent Portal"
      homeHref="/talent"
      navItems={navItems}
      title={title}
      backHref={backHref}
      onSignOut={() => signOut()}
    >
      {children}
    </PortalShell>
  );
}
