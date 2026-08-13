"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { BrandShell } from "@/components/brand/brand-shell";
import { api, ApiError } from "@/lib/api";
import type { InsightBrandResults, InsightCampaign, InsightEligibility, QAQuestion } from "@/lib/types";

const MODERATION_VARIANT: Record<string, "pending" | "active" | "done"> = {
  draft: "pending",
  pending_review: "pending",
  approved: "done",
  rejected: "pending",
};

const EMPTY_CAMPAIGN_FORM = {
  title: "",
  material_url: "",
  business_question: "",
  panel_size: "10",
  compensation_cents: "",
  confidentiality_terms: "",
  useStructuredQa: false,
  qaQuestionPrompts: [""] as string[],
};

export default function BrandInsightFeedbackPage() {
  const [eligibility, setEligibility] = useState<InsightEligibility | null>(null);
  const [campaigns, setCampaigns] = useState<InsightCampaign[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [campaignForm, setCampaignForm] = useState(EMPTY_CAMPAIGN_FORM);
  const [creating, setCreating] = useState(false);
  const [resultsFor, setResultsFor] = useState<string | null>(null);
  const [results, setResults] = useState<InsightBrandResults | null>(null);

  function load() {
    Promise.all([
      api.get<InsightEligibility>("/brands/insight/eligibility"),
      api.get<InsightCampaign[]>("/brands/insight/campaigns"),
    ])
      .then(([elig, list]) => {
        setEligibility(elig);
        setCampaigns(list);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load Insight & Feedback data."));
  }

  useEffect(load, []);

  async function toggleEligibilityField(field: keyof InsightEligibility, value: boolean) {
    if (!eligibility) return;
    const updated = { ...eligibility, [field]: value };
    try {
      const saved = await api.put<InsightEligibility>("/brands/insight/eligibility", {
        legal_entity_verified: updated.legal_entity_verified,
        named_contact_verified: updated.named_contact_verified,
        business_presence_verified: updated.business_presence_verified,
        funding_confirmed: updated.funding_confirmed,
        content_agreement_signed: updated.content_agreement_signed,
        is_early_stage_startup: updated.is_early_stage_startup,
        incorporated_3mo_or_backed: updated.incorporated_3mo_or_backed,
        has_real_product: updated.has_real_product,
      });
      setEligibility(saved);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save eligibility.");
    }
  }

  async function handleCreateCampaign(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(null);
    try {
      const qaQuestions: QAQuestion[] = campaignForm.useStructuredQa
        ? campaignForm.qaQuestionPrompts
            .map((prompt) => prompt.trim())
            .filter(Boolean)
            .map((prompt, i) => ({ id: `q${i + 1}`, prompt }))
        : [];
      await api.post("/brands/insight/campaigns", {
        title: campaignForm.title,
        material_url: campaignForm.material_url,
        business_question: campaignForm.business_question,
        panel_size: parseInt(campaignForm.panel_size, 10),
        compensation_cents: Math.round(parseFloat(campaignForm.compensation_cents) * 100),
        confidentiality_terms: campaignForm.confidentiality_terms,
        feedback_format: campaignForm.useStructuredQa ? "structured_qa" : "rating_scale",
        qa_questions: qaQuestions,
      });
      setCampaignForm(EMPTY_CAMPAIGN_FORM);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create this campaign.");
    } finally {
      setCreating(false);
    }
  }

  async function submitForReview(id: string) {
    await api.post(`/brands/insight/campaigns/${id}/submit-for-review`);
    load();
  }

  async function activate(id: string) {
    try {
      await api.post(`/brands/insight/campaigns/${id}/activate`);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not activate this campaign.");
    }
  }

  async function viewResults(id: string) {
    setResultsFor(id);
    const data = await api.get<InsightBrandResults>(`/brands/insight/campaigns/${id}/results`);
    setResults(data);
  }

  return (
    <BrandShell title="Insight & Feedback">
      {error ? <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p> : null}

      <Card>
        <CardContent>
          <div className="mb-3 flex items-center justify-between">
            <p className="font-semibold">Vetting requirements</p>
            <Badge variant={eligibility?.eligible ? "done" : "pending"}>
              {eligibility?.eligible ? "Eligible" : "Not yet eligible"}
            </Badge>
          </div>
          <p className="mb-3 text-sm text-text-2">
            Every requirement below must be checked before you can create an Insight &amp; Feedback campaign.
          </p>
          {eligibility ? (
            <div className="flex flex-col gap-2">
              {(
                [
                  ["legal_entity_verified", "Verified legal entity"],
                  ["named_contact_verified", "Verified named point of contact"],
                  ["business_presence_verified", "Working business presence (site/product + professional email)"],
                  ["funding_confirmed", "Funding confirmed before launch"],
                  ["content_agreement_signed", "Signed content agreement"],
                  ["is_early_stage_startup", "This is a pre-launch / early-stage startup"],
                ] as [keyof InsightEligibility, string][]
              ).map(([field, label]) => (
                <label key={field} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={eligibility[field] as boolean}
                    onCheckedChange={(checked) => toggleEligibilityField(field, checked === true)}
                  />
                  {label}
                </label>
              ))}
              {eligibility.is_early_stage_startup ? (
                <div className="ml-6 flex flex-col gap-2 border-l border-border-muted pl-4">
                  <label className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={eligibility.incorporated_3mo_or_backed}
                      onCheckedChange={(checked) => toggleEligibilityField("incorporated_3mo_or_backed", checked === true)}
                    />
                    Incorporated 3+ months, or backed by a named accelerator/incubator/investor
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={eligibility.has_real_product}
                      onCheckedChange={(checked) => toggleEligibilityField("has_real_product", checked === true)}
                    />
                    Has a real product/prototype to validate
                  </label>
                  <p className="text-xs text-text-2">
                    Startup campaigns additionally require manual Teenure review before going live.
                  </p>
                </div>
              ) : null}
            </div>
          ) : (
            <Skeleton className="h-24 w-full" />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <form onSubmit={handleCreateCampaign} className="flex flex-col gap-3">
            <p className="font-semibold">New campaign</p>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ifTitle">Title</Label>
              <Input
                id="ifTitle"
                required
                value={campaignForm.title}
                onChange={(e) => setCampaignForm({ ...campaignForm, title: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="materialUrl">Material URL (pre-release concept/copy/packaging)</Label>
              <Input
                id="materialUrl"
                required
                placeholder="https://"
                value={campaignForm.material_url}
                onChange={(e) => setCampaignForm({ ...campaignForm, material_url: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="businessQuestion">Business question</Label>
              <Textarea
                id="businessQuestion"
                required
                rows={2}
                value={campaignForm.business_question}
                onChange={(e) => setCampaignForm({ ...campaignForm, business_question: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="panelSize">Panel size</Label>
                <Input
                  id="panelSize"
                  type="number"
                  required
                  min={1}
                  value={campaignForm.panel_size}
                  onChange={(e) => setCampaignForm({ ...campaignForm, panel_size: e.target.value })}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="compensation">Compensation per panelist ($)</Label>
                <Input
                  id="compensation"
                  type="number"
                  required
                  min={0}
                  value={campaignForm.compensation_cents}
                  onChange={(e) => setCampaignForm({ ...campaignForm, compensation_cents: e.target.value })}
                />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="confidentiality">Confidentiality terms (shown to teen + parent)</Label>
              <Textarea
                id="confidentiality"
                required
                rows={2}
                value={campaignForm.confidentiality_terms}
                onChange={(e) => setCampaignForm({ ...campaignForm, confidentiality_terms: e.target.value })}
              />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={campaignForm.useStructuredQa}
                onCheckedChange={(checked) => setCampaignForm({ ...campaignForm, useStructuredQa: checked === true })}
              />
              Use structured Q&amp;A instead of a single 1-5 rating
            </label>
            {campaignForm.useStructuredQa ? (
              <div className="flex flex-col gap-2 border-l border-border-muted pl-4">
                <p className="text-xs text-text-2">
                  Up to 8 short-answer questions. Responses are held back and reviewed before you can see them, and
                  are only released once every panelist has answered (issue #52's k-anonymity gate).
                </p>
                {campaignForm.qaQuestionPrompts.map((prompt, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Input
                      placeholder={`Question ${i + 1}`}
                      value={prompt}
                      onChange={(e) => {
                        const next = [...campaignForm.qaQuestionPrompts];
                        next[i] = e.target.value;
                        setCampaignForm({ ...campaignForm, qaQuestionPrompts: next });
                      }}
                    />
                    {campaignForm.qaQuestionPrompts.length > 1 ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() =>
                          setCampaignForm({
                            ...campaignForm,
                            qaQuestionPrompts: campaignForm.qaQuestionPrompts.filter((_, j) => j !== i),
                          })
                        }
                      >
                        Remove
                      </Button>
                    ) : null}
                  </div>
                ))}
                {campaignForm.qaQuestionPrompts.length < 8 ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="w-fit"
                    onClick={() =>
                      setCampaignForm({ ...campaignForm, qaQuestionPrompts: [...campaignForm.qaQuestionPrompts, ""] })
                    }
                  >
                    Add question
                  </Button>
                ) : null}
              </div>
            ) : null}
            <Button type="submit" disabled={creating || !eligibility?.eligible} className="w-fit">
              {creating ? "Creating..." : "Create campaign"}
            </Button>
            {!eligibility?.eligible ? (
              <p className="text-xs text-text-2">Complete vetting above before creating a campaign.</p>
            ) : null}
          </form>
        </CardContent>
      </Card>

      {campaigns === null ? (
        <Skeleton className="h-28 w-full" />
      ) : campaigns.length === 0 ? (
        <EmptyState title="No Insight & Feedback campaigns yet" description="Create your first campaign above." />
      ) : (
        <div className="flex flex-col gap-3">
          {campaigns.map((c) => (
            <Card key={c.id}>
              <CardContent className="flex flex-col gap-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold">{c.title}</p>
                  <div className="flex gap-2">
                    <Badge variant={MODERATION_VARIANT[c.moderation_status]}>{c.moderation_status}</Badge>
                    <Badge variant={c.status === "active" ? "active" : "pending"}>{c.status}</Badge>
                  </div>
                </div>
                <p className="text-sm text-text-2">
                  Panel of {c.panel_size} -- ${(c.compensation_cents / 100).toFixed(2)} per panelist
                </p>
                {c.rejection_reason ? <p className="text-sm text-danger">Rejected: {c.rejection_reason}</p> : null}
                <div className="flex flex-wrap gap-2">
                  {c.moderation_status === "draft" ? (
                    <Button size="sm" variant="outline" onClick={() => submitForReview(c.id)}>
                      Submit for review
                    </Button>
                  ) : null}
                  {c.moderation_status === "approved" && c.status === "draft" ? (
                    <Button size="sm" onClick={() => activate(c.id)}>
                      Activate (fills panel)
                    </Button>
                  ) : null}
                  {c.status === "active" ? (
                    <Button size="sm" variant="ghost" onClick={() => viewResults(c.id)}>
                      View results
                    </Button>
                  ) : null}
                </div>

                {resultsFor === c.id && results ? (
                  <div className="mt-2 flex flex-col gap-2 border-t border-border-muted pt-2">
                    {!results.released ? (
                      <p className="text-sm text-text-2">
                        Withholding results until every panelist has responded and been reviewed --{" "}
                        {results.responses_submitted}/{results.responses_required} approved so far.
                      </p>
                    ) : results.results.length === 0 ? (
                      <p className="text-sm text-text-2">No responses yet.</p>
                    ) : (
                      results.results.map((r, i) => (
                        <div key={i} className="text-sm">
                          <span className="font-medium text-teal">{r.pseudonym_handle}</span>
                          {r.ratings?.map((rating, j) => (
                            <div key={j} className="text-text-2">
                              {rating.question}: {rating.score}/5
                            </div>
                          ))}
                          {r.qa_answers?.map((answer, j) => (
                            <div key={j} className="text-text-2">
                              {c.qa_questions.find((q) => q.id === answer.question_id)?.prompt ?? answer.question_id}:{" "}
                              {answer.answer_text}
                            </div>
                          ))}
                        </div>
                      ))
                    )}
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </BrandShell>
  );
}
