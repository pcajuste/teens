"use client";

import { useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { trackEvent } from "@/lib/analytics";
import type { AchievementLink } from "@/lib/types";

// Build Prompt 6 deliverable 9: sharing UI for the Living Achievement
// Link. QR code is generated client-side (the `qrcode` package renders
// straight to a <canvas>) -- no server round-trip beyond the one GET
// that already fetches the link itself.
export function AchievementLinkShare() {
  const [link, setLink] = useState<AchievementLink | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [saving, setSaving] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    api
      .get<AchievementLink>("/talents/me/achievement-link")
      .then(setLink)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load your achievement link."));
  }, []);

  useEffect(() => {
    if (link && canvasRef.current) {
      // Large enough to scan reliably on a phone screen (Prompt 6
      // deliverable 11's explicit mobile-first requirement for this
      // surface) -- 220px at this margin/error-correction level stays
      // scannable from typical arm's-length phone-to-phone distance.
      QRCode.toCanvas(canvasRef.current, link.url, { width: 220, margin: 2 }).catch(() => {
        // Non-fatal -- the copyable URL below still works without the QR code.
      });
    }
  }, [link]);

  async function updateVisibility(next: { verified_profile_public: boolean; earnings_visible_on_public_profile: boolean }) {
    if (!link) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.put<AchievementLink>("/talents/me/achievement-link/visibility", next);
      setLink(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update visibility.");
    } finally {
      setSaving(false);
    }
  }

  async function copyUrl() {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link.url);
      setCopied(true);
      trackEvent("achievement_link_copied", {});
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API can fail (permissions, non-secure context) -- the
      // URL is still selectable/copyable by hand from the text below.
    }
  }

  if (error && !link) {
    return <p className="text-sm text-destructive">{error}</p>;
  }
  if (!link) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Share your verified profile</CardTitle>
        <CardDescription>
          A permanent link a college admissions officer or employer can open without a Teenure account.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex items-start gap-3 rounded-lg border border-border p-3">
          <Checkbox
            id="verifiedProfilePublic"
            checked={link.verified_profile_public}
            disabled={saving}
            onCheckedChange={(checked) =>
              updateVisibility({
                verified_profile_public: checked === true,
                earnings_visible_on_public_profile: link.earnings_visible_on_public_profile,
              })
            }
          />
          <Label htmlFor="verifiedProfilePublic" className="flex-col items-start gap-1 font-normal">
            <span className="font-medium">Make my verified profile public</span>
            <span className="text-xs text-muted-foreground">
              Off by default. When off, your link shows a &quot;not currently public&quot; page instead of your
              profile -- so you can share it before turning this on.
            </span>
          </Label>
        </div>

        <div className="flex items-start gap-3 rounded-lg border border-border p-3">
          <Checkbox
            id="earningsVisible"
            checked={link.earnings_visible_on_public_profile}
            disabled={saving}
            onCheckedChange={(checked) =>
              updateVisibility({
                verified_profile_public: link.verified_profile_public,
                earnings_visible_on_public_profile: checked === true,
              })
            }
          />
          <Label htmlFor="earningsVisible" className="flex-col items-start gap-1 font-normal">
            <span className="font-medium">Show total earnings on my public profile</span>
            <span className="text-xs text-muted-foreground">
              Off by default. Always visible in your own dashboard either way -- this only controls what appears
              on the public link.
            </span>
          </Label>
        </div>

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        <div className="flex flex-col items-center gap-3 rounded-lg border border-border p-4 sm:flex-row sm:items-start">
          <canvas ref={canvasRef} className="shrink-0 rounded-md" aria-label="QR code linking to your verified profile" />
          <div className="flex w-full min-w-0 flex-col gap-2">
            <p className="break-all rounded-md bg-muted px-3 py-2 text-sm">{link.url}</p>
            <Button type="button" onClick={copyUrl} variant="outline" className="w-full sm:w-fit">
              {copied ? "Copied" : "Copy link"}
            </Button>
          </div>
        </div>

        {link.verified_profile_public ? (
          <a
            href={link.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-center text-sm font-medium underline underline-offset-2"
          >
            This is what a college admissions officer sees when they open your link
          </a>
        ) : (
          <p className="text-center text-sm text-muted-foreground">
            Turn on &quot;Make my verified profile public&quot; above to preview what a college admissions officer
            would see.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
