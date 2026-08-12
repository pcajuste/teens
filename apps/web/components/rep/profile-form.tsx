"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { CATEGORIES, SCHOOL_TYPES } from "@/lib/constants";
import { api, ApiError } from "@/lib/api";
import type { RepProfile, RepProfileUpdate } from "@/lib/types";
import { cn } from "@/lib/utils";

const currentYear = new Date().getFullYear();
const graduationYears = Array.from({ length: 12 }, (_, i) => currentYear + i).filter(
  (y) => y >= 2024 && y <= 2035,
);

export function ProfileForm({
  initial,
  mode,
}: {
  initial: Partial<RepProfile>;
  mode: "onboarding" | "edit";
}) {
  const router = useRouter();
  const [displayName, setDisplayName] = useState(initial.display_name ?? "");
  const [schoolName, setSchoolName] = useState(initial.school_name ?? "");
  const [schoolType, setSchoolType] = useState(initial.school_type ?? "");
  const [city, setCity] = useState(initial.city ?? "");
  const [state, setState] = useState(initial.state ?? "");
  const [graduationYear, setGraduationYear] = useState<number | "">(initial.graduation_year ?? "");
  const [categories, setCategories] = useState<string[]>(initial.categories ?? []);
  const [bio, setBio] = useState(initial.bio ?? "");
  const [instagram, setInstagram] = useState(initial.instagram_handle ?? "");
  const [tiktok, setTiktok] = useState(initial.tiktok_handle ?? "");
  const [recruiterVisible, setRecruiterVisible] = useState(initial.recruiter_visible ?? false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleCategory(cat: string) {
    setCategories((prev) => (prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]));
  }

  const canSubmit = displayName.trim() && schoolName.trim() && city.trim() && state.trim() && graduationYear;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) {
      setError("Please fill in name, school, city, state, and graduation year.");
      return;
    }
    setSubmitting(true);
    setError(null);
    const body: RepProfileUpdate = {
      display_name: displayName.trim(),
      school_name: schoolName.trim(),
      school_type: schoolType || null,
      city: city.trim(),
      state: state.trim(),
      graduation_year: Number(graduationYear),
      bio: bio.trim() || null,
      categories,
      instagram_handle: instagram.trim() || null,
      tiktok_handle: tiktok.trim() || null,
      recruiter_visible: recruiterVisible,
    };
    try {
      await api.updateRepProfile(body);
      router.push("/rep");
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? err.message) : "Could not save your profile.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-6 pb-8">
      <Card>
        <CardHeader>
          <CardTitle>Basics</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Field label="Full name">
            <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
          </Field>
          <Field label="School" id="school">
            <Input value={schoolName} onChange={(e) => setSchoolName(e.target.value)} required />
          </Field>
          <Field
            label="School type (optional)"
            hint="Used only in anonymized, aggregate trend reports — never attached to your individual profile."
          >
            <select
              value={schoolType}
              onChange={(e) => setSchoolType(e.target.value)}
              className="h-11 w-full rounded-md border border-border bg-background px-3 text-base sm:text-sm"
            >
              <option value="">Prefer not to say</option>
              {SCHOOL_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t[0].toUpperCase() + t.slice(1)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Graduation year" id="graduation-year">
            <select
              value={graduationYear}
              onChange={(e) => setGraduationYear(e.target.value ? Number(e.target.value) : "")}
              required
              className="h-11 w-full rounded-md border border-border bg-background px-3 text-base sm:text-sm"
            >
              <option value="">Select a year</option>
              {graduationYears.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </Field>
          <Field label="City" id="city">
            <Input value={city} onChange={(e) => setCity(e.target.value)} required />
          </Field>
          <Field label="State">
            <Input value={state} onChange={(e) => setState(e.target.value)} maxLength={2} placeholder="CA" required />
          </Field>
        </CardContent>
      </Card>

      <Card id="categories">
        <CardHeader>
          <CardTitle>Categories</CardTitle>
          <CardDescription>Pick the ones that best describe your content.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {CATEGORIES.map((cat) => {
              const active = categories.includes(cat);
              return (
                <button
                  type="button"
                  key={cat}
                  onClick={() => toggleCategory(cat)}
                  className={cn(
                    "min-h-11 rounded-full border px-4 py-2 text-sm capitalize",
                    active ? "border-primary bg-primary text-primary-foreground" : "border-border",
                  )}
                >
                  {cat}
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <Card id="bio">
        <CardHeader>
          <CardTitle>Bio</CardTitle>
        </CardHeader>
        <CardContent>
          <Textarea
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            placeholder="Tell brands and recruiters about yourself…"
            rows={4}
          />
        </CardContent>
      </Card>

      <Card id="social">
        <CardHeader>
          <CardTitle>Social handles</CardTitle>
          <CardDescription>Display-only — shown on your profile, not verified or linked.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Field label="Instagram handle">
            <Input value={instagram} onChange={(e) => setInstagram(e.target.value)} placeholder="@yourhandle" />
          </Field>
          <Field label="TikTok handle">
            <Input value={tiktok} onChange={(e) => setTiktok(e.target.value)} placeholder="@yourhandle" />
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recruiter visibility</CardTitle>
        </CardHeader>
        <CardContent>
          <label className="flex min-h-11 cursor-pointer items-start gap-3">
            <Checkbox checked={recruiterVisible} onChange={(e) => setRecruiterVisible(e.target.checked)} />
            <span className="text-sm text-muted-foreground">
              <strong className="block text-foreground">Let recruiters find my profile</strong>
              This defaults to OFF. Turning it on lets college and employer recruiters discover and view your
              verified profile (the same preview you can see below). It does not let anyone message other reps or
              browse outside your own profile.
            </span>
          </label>
        </CardContent>
      </Card>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <Button type="submit" size="lg" disabled={submitting} className="w-full">
        {submitting ? "Saving…" : mode === "onboarding" ? "Finish setup" : "Save changes"}
      </Button>
    </form>
  );
}

function Field({
  label,
  hint,
  id,
  children,
}: {
  label: string;
  hint?: string;
  id?: string;
  children: React.ReactNode;
}) {
  return (
    <div id={id} className="space-y-1 scroll-mt-20">
      <label className="text-sm font-medium">{label}</label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
