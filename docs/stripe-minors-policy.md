# Stripe Connect and minors (design note + required human review)

Build Prompt 7, deliverable 2. Researched against Stripe's own primary
sources — not the SEO/aggregator sites that dominate a plain web search
for "Stripe age requirements minor," several of which (aeanet.org,
vertexlegal.org, bridgelegal.org, thelegalguide.org) are content-farm
mirrors with no actual affiliation to Stripe and gave a materially
wrong answer (claiming Express/Custom Connect accounts require the
holder to be 18+, full stop). The findings below come from:

- Stripe's own support article: [Age requirement to create a Stripe account](https://support.stripe.com/questions/age-requirement-to-create-a-stripe-account)
- Stripe's Services Agreement (the actual contract terms): [stripe.com/legal/ssa](https://stripe.com/legal/ssa), Section 1.2(b)
- Stripe's API docs on the Persons object's `relationship.representative` field: [docs.stripe.com/api/persons](https://docs.stripe.com/api/persons)

## What Stripe actually requires

**Minimum age to open any Stripe account, including Connect Express and
Custom accounts, is 13** — not 18. Quoting the Services Agreement
directly (Section 1.2(b)):

> "Only people 13 years of age or older may open a Stripe Account and
> use the Services and Stripe Technology."

**Under 18** (or the local age of majority), an adult **Representative**
must be added to the account:

> "If User or User's Representative is not 18 years of age or older (or
> the age of majority where User resides): (i) User must add a
> Representative who is an adult (which may be a parent or legal
> guardian) to User's Stripe Account; (ii) both User and Representative
> agree to be bound by the terms of the Agreement; and (iii)
> Representative agrees to be responsible and liable for User's actions
> in its Stripe Account and User's compliance with this Agreement."

The Representative's own information is collected separately from the
minor's: full name, date of birth, last four digits of SSN (US
citizens), postal address, and an explicit consent statement. Stripe's
support article describes this as something Stripe "reach[es] out ...
and ask[s] for" once an under-18 individual's account is created —
i.e., this is triggered by the account holder's date of birth, not
something the integrating platform (Teenure) has to detect and branch
on itself.

In the Connect API, this Representative is modeled as a second `Person`
object on the account, distinct from the minor's own `individual`
object, with `relationship.representative = true`.

**Brazil is stricter**: 18+ required outright, no minor-with-guardian
path. Not relevant at MVP (Teenure launches US-only), but worth
remembering if international expansion is ever discussed.

## What this means for `create_connect_account`

`app/services/stripe_service.py`'s `create_connect_account` does **not**
special-case reps under 18. It creates a standard Express account
(`type="express"`, `business_type="individual"`) using only the rep's
email — no date of birth is collected at that step. The Representative
requirement is Stripe's hosted onboarding flow's problem to surface,
not ours to pre-empt: when the rep reaches Stripe's hosted onboarding
UI (the `Account Link` from `create_connect_onboarding_link`) and
enters their date of birth as part of standard Connect KYC, Stripe's
own requirements engine adds "provide a Representative" to that
account's `currently_due` requirements and the hosted UI prompts for it
in-flow.

This is standard, intended Stripe behavior — the same mechanism that
asks for any other missing requirement (SSN, address, bank account)
mid-onboarding. It is not something Teenure's code needs to detect or
implement custom UI for.

## The open question, flagged for human/legal review before launch

**Teenure's own age gate is narrower than Stripe's.** Per
`Teenure_MVP_Gameplan.md` Section 9 and this repo's `CLAUDE.md`, Teenure
requires parental consent only for reps **under 16** — a 16- or
17-year-old rep can sign up, use the platform, and accept campaigns
entirely independently, with no `parent_records` row at all (see
`docs/parent_records_creation_timing.md`).

Stripe's Representative requirement applies to **everyone under 18**.
That means a 16-17-year-old rep who has no parent involved in their
Teenure account at all will hit Stripe's hosted onboarding and be asked
to add an adult Representative — a parent or guardian who, per
Teenure's own product design, may have no account, no relationship to
the platform, and no reason to expect this request.

This is a real product gap, not a hypothetical:

1. **What happens if a 16-17-year-old rep has no parent willing or
   available to act as Stripe's Representative?** Their Connect account
   cannot complete onboarding, and Prompt 10's payout flow has no path
   for them to get paid. This needs a product decision, not a
   workaround invented here.
2. **The gameplan itself anticipates a fallback** (Section 9's
   requirements table): "Build parent-as-payee option into the payout
   flow as a fallback." That is the most likely correct direction —
   route payouts for under-18 reps through a parent/guardian's own
   Stripe Connect account rather than (or via) the rep's — but it is
   **not implemented in this prompt**. It requires:
   - Deciding whether every under-18 rep needs a `parent_records`-like
     row even outside the under-16 consent flow (a schema/product
     decision beyond Prompt 7's scope), or whether the Representative
     relationship is captured entirely on Stripe's side with no local
     schema change.
   - Legal confirmation of whether a parent added only as a Stripe
     Representative (not a Teenure account holder) satisfies the same
     compliance bar as Teenure's own under-16 parental-consent flow, or
     whether they are legally distinct obligations that both need to be
     independently satisfied.
3. **State-specific requirements are out of scope for this research.**
   The gameplan's Section 9 table flags "may require parent as account
   holder depending on state" — this note has not been independently
   verified against any specific state's minor-employment or
   minor-earnings statutes (e.g. child labor / entertainment-industry
   trust account laws that some states apply to minors' earnings,
   which are a separate legal regime from Stripe's own Terms). A
   privacy/compliance lawyer should confirm whether any Teenure launch
   state imposes requirements beyond what Stripe itself requires.

**Recommendation, pending the above sign-off:** ship Prompt 7 as
implemented (generic Express account creation + hosted onboarding,
no minor-specific branching) since it is what "test-mode Connect
onboarding end-to-end" in this prompt's acceptance criteria actually
requires, and it does not foreclose any future direction — the
Representative-as-parent path and the parent-as-payee fallback are both
still available to build on top of it. Do not enable real (non-test-mode)
Connect payouts for any rep under 18 until items 1-3 above are resolved.
