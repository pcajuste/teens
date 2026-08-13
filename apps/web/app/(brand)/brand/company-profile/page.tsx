"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { BrandShell } from "@/components/brand/brand-shell";
import { api, ApiError } from "@/lib/api";
import type { CompanyProfile } from "@/lib/types";

// Build Prompt 8I template 1: the brand's home base, required before
// any of the other templates (Scholarship, Skills Challenge, Insight &
// Feedback) can go live. Distinct from /brand/onboarding, which owns
// the Prompt 8 legal/business fields (EIN, industry, target categories).
function wordCount(text: string): number {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

export default function BrandCompanyProfilePage() {
  const [logoUrl, setLogoUrl] = useState("");
  const [brandColor, setBrandColor] = useState("");
  const [aboutText, setAboutText] = useState("");
  const [whyText, setWhyText] = useState("");
  const [complete, setComplete] = useState(false);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api
      .get<CompanyProfile>("/brands/me/company-profile")
      .then((profile) => {
        setLogoUrl(profile.logo_url ?? "");
        setBrandColor(profile.brand_color_primary ?? "");
        setAboutText(profile.about_text ?? "");
        setWhyText(profile.why_on_teenure_text ?? "");
        setComplete(profile.complete);
      })
      .catch((err) => {
        if (err instanceof ApiError) setError(err.message);
      })
      .finally(() => setLoading(false));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    setSaved(false);
    try {
      const profile = await api.put<CompanyProfile>("/brands/me/company-profile", {
        logo_url: logoUrl || null,
        brand_color_primary: brandColor || null,
        about_text: aboutText,
        why_on_teenure_text: whyText,
      });
      setComplete(profile.complete);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save your company profile.");
    } finally {
      setPending(false);
    }
  }

  if (loading) {
    return (
      <BrandShell title="Company profile">
        <p className="text-sm text-text-2">Loading...</p>
      </BrandShell>
    );
  }

  return (
    <BrandShell
      title="Company profile"
      action={complete ? <Badge variant="done">Complete</Badge> : <Badge variant="pending">Incomplete</Badge>}
    >
      <form onSubmit={handleSubmit} className="flex max-w-xl flex-col gap-5">
        <p className="text-sm text-text-2">
          This is your public home base on Teenure -- required before you can publish a
          Scholarship, Skills Challenge, or Insight &amp; Feedback campaign.
        </p>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="logoUrl">Logo URL</Label>
          <Input id="logoUrl" placeholder="https://" value={logoUrl} onChange={(e) => setLogoUrl(e.target.value)} />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="brandColor">Brand color</Label>
          <Input
            id="brandColor"
            placeholder="#0D9B7A"
            value={brandColor}
            onChange={(e) => setBrandColor(e.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="aboutText">
            Who we are <span className="font-normal text-text-2">({wordCount(aboutText)}/150 words)</span>
          </Label>
          <Textarea id="aboutText" required rows={4} value={aboutText} onChange={(e) => setAboutText(e.target.value)} />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="whyText">
            Why we&apos;re on Teenure <span className="font-normal text-text-2">({wordCount(whyText)}/100 words)</span>
          </Label>
          <Textarea id="whyText" required rows={3} value={whyText} onChange={(e) => setWhyText(e.target.value)} />
        </div>

        {error ? <p className="text-[13px] text-danger">{error}</p> : null}
        {saved ? <p className="text-[13px] text-success">Saved.</p> : null}

        <Button type="submit" disabled={pending} className="w-fit">
          {pending ? "Saving..." : "Save"}
        </Button>
      </form>
    </BrandShell>
  );
}
