"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RecruiterShell } from "@/components/recruiter/recruiter-shell";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { InstitutionType, RecruiterProfile } from "@/lib/types";

const INSTITUTION_TYPES: { value: InstitutionType; label: string }[] = [
  { value: "college", label: "College / University" },
  { value: "employer", label: "Employer" },
];

export default function RecruiterProfilePage() {
  const router = useRouter();
  const { me } = useAuth();
  const [institutionName, setInstitutionName] = useState("");
  const [institutionType, setInstitutionType] =
    useState<InstitutionType>("college");
  const [website, setWebsite] = useState("");
  const [verified, setVerified] = useState(false);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api
      .get<RecruiterProfile>("/recruiters/me")
      .then((profile) => {
        setInstitutionName(profile.institution_name);
        setInstitutionType(profile.institution_type);
        setWebsite(profile.website ?? "");
        setVerified(profile.verified);
      })
      .catch((err) => {
        if (
          err instanceof ApiError &&
          err.code !== "recruiter_profile_not_found"
        ) {
          setError(err.message);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    setSaved(false);
    try {
      await api.put<RecruiterProfile>("/recruiters/me", {
        institution_name: institutionName,
        institution_type: institutionType,
        website: website || null,
      });
      setSaved(true);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not save your profile.",
      );
    } finally {
      setPending(false);
    }
  }

  if (loading) {
    return (
      <RecruiterShell title="Institution profile">
        <p className="text-sm text-text-2">Loading...</p>
      </RecruiterShell>
    );
  }

  return (
    <RecruiterShell title="Institution profile">
      <form onSubmit={handleSubmit} className="flex max-w-xl flex-col gap-5">
        <div className="flex items-center gap-2">
          {/* DS: an admin-verified institution is an earned credential
              moment (gold), consistent with every other "VERIFIED" badge
              on the platform -- not a generic green completion state. */}
          <Badge variant={verified ? "earned" : "pending"}>
            {verified ? "Verified" : "Pending verification"}
          </Badge>
          {me?.account_status === "pending" ? (
            <span className="text-xs text-text-2">
              Approval and an active subscription are both required before you
              can search or contact talents.
            </span>
          ) : null}
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="institutionName">Institution name</Label>
          <Input
            id="institutionName"
            required
            value={institutionName}
            onChange={(e) => setInstitutionName(e.target.value)}
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label>Institution type</Label>
          <div className="flex gap-2">
            {INSTITUTION_TYPES.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => setInstitutionType(t.value)}
              >
                <Badge
                  variant={institutionType === t.value ? "default" : "outline"}
                  className="px-3 py-1.5"
                >
                  {t.label}
                </Badge>
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="website">Website</Label>
          <Input
            id="website"
            type="url"
            placeholder="https://"
            value={website}
            onChange={(e) => setWebsite(e.target.value)}
          />
        </div>

        {error ? (
          <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        ) : null}
        {saved ? (
          <p className="rounded-lg bg-success/10 px-3 py-2 text-sm text-success">
            Saved.
          </p>
        ) : null}

        <div className="flex gap-3">
          <Button type="submit" disabled={pending} size="lg">
            {pending ? "Saving..." : "Save"}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="lg"
            onClick={() => router.push("/recruiter")}
          >
            Back to search
          </Button>
        </div>
      </form>
    </RecruiterShell>
  );
}
