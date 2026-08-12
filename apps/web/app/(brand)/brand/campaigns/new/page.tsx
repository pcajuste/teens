"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { BrandShell } from "@/components/brand/brand-shell";
import { CampaignBrief } from "@/components/campaigns/campaign-brief";
import {
  MAX_MILESTONES,
  MIN_MILESTONES,
  MilestoneBuilder,
  emptyMilestone,
  milestonesPercentageTotal,
} from "@/components/brand/milestone-builder";
import { api, ApiError } from "@/lib/api";
import { trackEvent } from "@/lib/analytics";
import { BASE_CATEGORIES, CATEGORY_LABELS, type Category } from "@/lib/categories";
import type { Campaign, CampaignBriefRequest, MilestoneRequest, PaymentType } from "@/lib/types";

const todayPlusDays = (days: number) => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
};

export default function NewCampaignPage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [productName, setProductName] = useState("");
  const [campaignGoal, setCampaignGoal] = useState("");
  const [keyMessaging, setKeyMessaging] = useState("");
  const [prohibitedContent, setProhibitedContent] = useState("");
  const [deliverablesDescription, setDeliverablesDescription] = useState("");
  const [categories, setCategories] = useState<Category[]>([]);
  const [targetCitiesRaw, setTargetCitiesRaw] = useState("");
  const [maxReps, setMaxReps] = useState(10);
  const [budgetDollars, setBudgetDollars] = useState(1000);
  const [startDate, setStartDate] = useState(todayPlusDays(14));
  const [endDate, setEndDate] = useState(todayPlusDays(44));
  const [paymentType, setPaymentType] = useState<PaymentType>("flat");
  const [milestones, setMilestones] = useState<MilestoneRequest[]>([
    emptyMilestone(1),
    emptyMilestone(2),
  ]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handlePaymentTypeChange(type: PaymentType) {
    setPaymentType(type);
    if (type === "milestone" && milestones.length < MIN_MILESTONES) {
      setMilestones([emptyMilestone(1), emptyMilestone(2)]);
    }
  }

  const milestonesTotal = milestonesPercentageTotal(milestones);
  const milestonesValid =
    paymentType === "flat" ||
    (milestones.length >= MIN_MILESTONES &&
      milestones.length <= MAX_MILESTONES &&
      milestonesTotal === 100 &&
      milestones.every((m) => m.title.trim().length > 0));

  function toggleCategory(c: Category) {
    setCategories((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));
  }

  const budgetCents = Math.round(budgetDollars * 100);
  const targetCities = targetCitiesRaw
    .split(",")
    .map((c) => c.trim())
    .filter(Boolean);

  const previewCampaign = {
    title: title || "Untitled campaign",
    product_name: productName || "—",
    campaign_goal: campaignGoal || "—",
    deliverables_description: deliverablesDescription || "—",
    prohibited_content: prohibitedContent || null,
    target_categories: categories,
    // A budget split evenly across max_reps is the best local estimate
    // available before the server computes the real, authoritative
    // fee-split -- this preview number is never sent anywhere, purely
    // illustrative so a brand isn't guessing blind while filling the form.
    payout_per_rep_cents: maxReps > 0 ? Math.floor((budgetCents * 0.65) / maxReps) : null,
  };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      const body: CampaignBriefRequest = {
        title,
        product_name: productName,
        campaign_goal: campaignGoal,
        key_messaging: keyMessaging,
        prohibited_content: prohibitedContent || null,
        deliverables_description: deliverablesDescription,
        target_categories: categories,
        target_cities: targetCities,
        max_reps: maxReps,
        budget_cents: budgetCents,
        start_date: startDate,
        end_date: endDate,
        payment_type: paymentType,
        milestones: paymentType === "milestone" ? milestones : [],
      };
      const campaign = await api.post<Campaign>("/brands/campaigns", body);
      trackEvent("campaign_created", { campaign_id: campaign.id, categories });
      router.push(`/brand/campaigns/${campaign.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create this campaign.");
    } finally {
      setPending(false);
    }
  }

  return (
    <BrandShell title="New campaign" backHref="/brand">
      <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="title">Campaign title</Label>
            <Input id="title" required value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="productName">Product name</Label>
            <Input id="productName" required value={productName} onChange={(e) => setProductName(e.target.value)} />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="campaignGoal">Campaign goal</Label>
            <Input id="campaignGoal" required value={campaignGoal} onChange={(e) => setCampaignGoal(e.target.value)} />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="keyMessaging">Key messaging</Label>
            <Textarea id="keyMessaging" required rows={3} value={keyMessaging} onChange={(e) => setKeyMessaging(e.target.value)} />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="deliverablesDescription">Deliverables</Label>
            <Textarea
              id="deliverablesDescription"
              required
              rows={3}
              value={deliverablesDescription}
              onChange={(e) => setDeliverablesDescription(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="prohibitedContent">Prohibited content (optional)</Label>
            <Textarea
              id="prohibitedContent"
              rows={2}
              value={prohibitedContent}
              onChange={(e) => setProhibitedContent(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label>Target categories</Label>
            <div className="flex flex-wrap gap-2">
              {BASE_CATEGORIES.map((c) => (
                <button key={c} type="button" onClick={() => toggleCategory(c)}>
                  <Badge variant={categories.includes(c) ? "default" : "outline"} className="px-3 py-1.5">
                    {CATEGORY_LABELS[c]}
                  </Badge>
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="targetCities">Target cities (comma-separated, optional)</Label>
            <Input
              id="targetCities"
              placeholder="Austin, Dallas"
              value={targetCitiesRaw}
              onChange={(e) => setTargetCitiesRaw(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">Leave blank to match reps in any city.</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="maxReps">Max reps</Label>
              <Input
                id="maxReps"
                type="number"
                min={1}
                required
                value={maxReps}
                onChange={(e) => setMaxReps(Number(e.target.value))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="budget">Budget (USD)</Label>
              <Input
                id="budget"
                type="number"
                min={1}
                step="0.01"
                required
                value={budgetDollars}
                onChange={(e) => setBudgetDollars(Number(e.target.value))}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="startDate">Start date</Label>
              <Input id="startDate" type="date" required value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="endDate">End date</Label>
              <Input id="endDate" type="date" required value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <Label>Payment type</Label>
            <div className="flex gap-2">
              <button type="button" onClick={() => handlePaymentTypeChange("flat")}>
                <Badge variant={paymentType === "flat" ? "default" : "outline"} className="px-3 py-1.5">
                  Flat payout
                </Badge>
              </button>
              <button type="button" onClick={() => handlePaymentTypeChange("milestone")}>
                <Badge variant={paymentType === "milestone" ? "default" : "outline"} className="px-3 py-1.5">
                  Performance milestones
                </Badge>
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              {paymentType === "flat"
                ? "Reps are paid in full when their submission is confirmed."
                : "Reps are paid in staged releases as each milestone is completed and confirmed."}
            </p>
          </div>

          {paymentType === "milestone" ? (
            <MilestoneBuilder milestones={milestones} onChange={setMilestones} />
          ) : null}

          {error ? (
            <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
          ) : null}

          {paymentType === "milestone" && !milestonesValid ? (
            <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
              Add 2-5 milestones with titles, and make sure payout percentages sum to exactly 100%
              before creating this campaign.
            </p>
          ) : null}

          <Button type="submit" disabled={pending || !milestonesValid} size="lg" className="w-full">
            {pending ? "Creating..." : "Create campaign"}
          </Button>
        </form>

        <div className="flex flex-col gap-3">
          <p className="text-sm font-semibold text-muted-foreground">
            Preview — exactly what a rep sees
          </p>
          <CampaignBrief campaign={previewCampaign} />
          <p className="text-xs text-muted-foreground">
            The payout shown here is an estimate. The platform fee and final per-rep payout are
            computed server-side when you create the campaign.
          </p>
        </div>
      </div>
    </BrandShell>
  );
}
