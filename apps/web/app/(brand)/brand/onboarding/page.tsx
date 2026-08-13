"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { BrandShell } from "@/components/brand/brand-shell";
import { api, ApiError } from "@/lib/api";
import {
  BASE_CATEGORIES,
  CATEGORY_LABELS,
  type Category,
} from "@/lib/categories";
import type { BrandProfile } from "@/lib/types";

export default function BrandOnboardingPage() {
  const router = useRouter();
  const [companyName, setCompanyName] = useState("");
  const [website, setWebsite] = useState("");
  const [ein, setEin] = useState("");
  const [industry, setIndustry] = useState("");
  const [categories, setCategories] = useState<Category[]>([]);
  const [hasEinOnFile, setHasEinOnFile] = useState(false);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api
      .get<BrandProfile>("/brands/me")
      .then((profile) => {
        setCompanyName(profile.company_name);
        setWebsite(profile.website ?? "");
        setIndustry(profile.industry ?? "");
        setCategories(profile.target_categories as Category[]);
        setHasEinOnFile(profile.has_ein_on_file);
      })
      .catch((err) => {
        // 404 (brand_profile_not_found) just means first-time onboarding
        // -- everything else is a real error worth surfacing.
        if (err instanceof ApiError && err.code !== "brand_profile_not_found") {
          setError(err.message);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  function toggleCategory(c: Category) {
    setCategories((prev) =>
      prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c],
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    setSaved(false);
    try {
      await api.put<BrandProfile>("/brands/me", {
        company_name: companyName,
        website: website || null,
        ein: ein || null,
        industry: industry || null,
        target_categories: categories,
      });
      setEin("");
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
      <BrandShell title="Company profile">
        <p className="text-sm text-muted-foreground">Loading...</p>
      </BrandShell>
    );
  }

  return (
    <BrandShell title="Company profile">
      <form onSubmit={handleSubmit} className="flex max-w-xl flex-col gap-5">
        <p className="text-sm text-muted-foreground">
          This information is reviewed as part of account approval, and EIN is
          encrypted at talents -- it&apos;s never shown back to you or anyone
          else after you save it.
        </p>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="companyName">Company name</Label>
          <Input
            id="companyName"
            required
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
          />
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

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="industry">Industry</Label>
          <Input
            id="industry"
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="ein">
            EIN{" "}
            {hasEinOnFile ? (
              <span className="font-normal text-muted-foreground">
                (on file)
              </span>
            ) : null}
          </Label>
          <Input
            id="ein"
            placeholder={
              hasEinOnFile ? "Enter a new EIN to replace it" : "XX-XXXXXXX"
            }
            value={ein}
            onChange={(e) => setEin(e.target.value)}
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label>Target categories</Label>
          <div className="flex flex-wrap gap-2">
            {BASE_CATEGORIES.map((c) => (
              <button key={c} type="button" onClick={() => toggleCategory(c)}>
                <Badge
                  variant={categories.includes(c) ? "default" : "outline"}
                  className="px-3 py-1.5"
                >
                  {CATEGORY_LABELS[c]}
                </Badge>
              </button>
            ))}
          </div>
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
            onClick={() => router.push("/brand")}
          >
            Back to dashboard
          </Button>
        </div>
      </form>
    </BrandShell>
  );
}
