"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { api, ApiError } from "@/lib/api";
import { BASE_CATEGORIES, CATEGORY_LABELS, type Category } from "@/lib/categories";
import type { RepProfile, RepProfileUpdateRequest, SchoolType } from "@/lib/types";

const SCHOOL_TYPES: { value: SchoolType; label: string }[] = [
  { value: "public", label: "Public" },
  { value: "private", label: "Private" },
  { value: "charter", label: "Charter" },
  { value: "homeschool", label: "Homeschool" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const [displayName, setDisplayName] = useState("");
  const [schoolName, setSchoolName] = useState("");
  const [schoolType, setSchoolType] = useState<SchoolType | null>(null);
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [graduationYear, setGraduationYear] = useState<number>(new Date().getFullYear() + 1);
  const [bio, setBio] = useState("");
  const [categories, setCategories] = useState<Category[]>([]);
  const [instagram, setInstagram] = useState("");
  const [tiktok, setTiktok] = useState("");
  const [recruiterVisible, setRecruiterVisible] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<RepProfile>("/reps/me")
      .then((profile) => {
        setDisplayName(profile.display_name);
        setSchoolName(profile.school_name);
        setSchoolType(profile.school_type);
        setCity(profile.city);
        setState(profile.state);
        setGraduationYear(profile.graduation_year);
        setBio(profile.bio ?? "");
        setCategories(profile.categories as Category[]);
        setInstagram(profile.instagram_handle ?? "");
        setTiktok(profile.tiktok_handle ?? "");
        setRecruiterVisible(profile.recruiter_visible);
      })
      .catch(() => {
        // No profile yet -- first-time onboarding, defaults above are fine.
      });
  }, []);

  function toggleCategory(category: Category) {
    setCategories((prev) =>
      prev.includes(category) ? prev.filter((c) => c !== category) : [...prev, category]
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    const body: RepProfileUpdateRequest = {
      display_name: displayName,
      school_name: schoolName,
      school_type: schoolType,
      city,
      state,
      graduation_year: graduationYear,
      bio: bio || null,
      categories,
      instagram_handle: instagram || null,
      tiktok_handle: tiktok || null,
    };
    try {
      await api.put<RepProfile>("/reps/me", body);
      // recruiter_visible is not writable via PUT /reps/me in the
      // current backend schema (Prompt 5 deliverable scope) -- the
      // toggle below records the rep's intent locally for now.
      router.push("/rep");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save your profile. Try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col gap-6 p-4 pb-16">
      <div>
        <h1 className="text-xl font-semibold">Set up your profile</h1>
        <p className="text-sm text-muted-foreground">
          This is what brands and recruiters see when deciding whether to work with you.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Field label="Name" htmlFor="displayName">
          <Input id="displayName" required value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
        </Field>

        <Field label="School" htmlFor="schoolName">
          <Input id="schoolName" required value={schoolName} onChange={(e) => setSchoolName(e.target.value)} />
        </Field>

        <div className="flex flex-col gap-1.5">
          <Label>School type (optional)</Label>
          <p className="text-xs text-muted-foreground">
            Only used in anonymized, aggregated trend reports -- never shown on your individual profile.
          </p>
          <div className="flex flex-wrap gap-2">
            {SCHOOL_TYPES.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => setSchoolType(schoolType === t.value ? null : t.value)}
                className="min-h-11"
              >
                <Badge variant={schoolType === t.value ? "default" : "outline"} className="px-3 py-2">
                  {t.label}
                </Badge>
              </button>
            ))}
          </div>
        </div>

        <Field label="Graduation year" htmlFor="gradYear">
          <Input
            id="gradYear"
            type="number"
            required
            min={2024}
            max={2035}
            value={graduationYear}
            onChange={(e) => setGraduationYear(Number(e.target.value))}
          />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="City" htmlFor="city">
            <Input id="city" required value={city} onChange={(e) => setCity(e.target.value)} />
          </Field>
          <Field label="State" htmlFor="state">
            <Input id="state" required value={state} onChange={(e) => setState(e.target.value)} />
          </Field>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label>Categories</Label>
          <div className="flex flex-wrap gap-2">
            {BASE_CATEGORIES.map((c) => (
              <button key={c} type="button" onClick={() => toggleCategory(c)} className="min-h-11">
                <Badge variant={categories.includes(c) ? "default" : "outline"} className="px-3 py-2">
                  {CATEGORY_LABELS[c]}
                </Badge>
              </button>
            ))}
          </div>
        </div>

        <Field label="Bio" htmlFor="bio">
          <Textarea id="bio" value={bio} onChange={(e) => setBio(e.target.value)} rows={3} />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Instagram handle" htmlFor="instagram">
            <Input id="instagram" value={instagram} onChange={(e) => setInstagram(e.target.value)} />
          </Field>
          <Field label="TikTok handle" htmlFor="tiktok">
            <Input id="tiktok" value={tiktok} onChange={(e) => setTiktok(e.target.value)} />
          </Field>
        </div>
        <p className="-mt-2 text-xs text-muted-foreground">
          Display-only -- Teenure never embeds or auto-imports your social content.
        </p>

        <div className="flex items-start gap-3 rounded-lg border border-border p-3">
          <Checkbox
            id="recruiterVisible"
            checked={recruiterVisible}
            onCheckedChange={(checked) => setRecruiterVisible(checked === true)}
          />
          <Label htmlFor="recruiterVisible" className="flex-col items-start gap-1 font-normal">
            <span className="font-medium">Make my profile visible to recruiters</span>
            <span className="text-xs text-muted-foreground">
              Off by default. Turning this on lets verified college and employer recruiters find and view
              your profile. You can turn it off again at any time.
            </span>
          </Label>
        </div>

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        <Button type="submit" disabled={pending} className="h-11 w-full">
          {pending ? "Saving..." : "Save and continue"}
        </Button>
      </form>
    </main>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
    </div>
  );
}
