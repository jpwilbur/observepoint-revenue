# Usage methodology — multipliers, cadence, and the consultative flow

Reference for scope-calculator's **usage + price stage** (Stage 2). Turns a defensible page count into an annual page-scan
usage number. The math is deterministic in `scripts/compute_scope.py`; this file is the judgment
layer — how to choose the inputs and what to ask the customer.

## 1. The model

```
use_case_pages = base_pages × geographies × scenarios × environments
annual_scans   = Σ over cadence layers c of ( use_case_pages × pct_c × runs_per_year_c )   # additive
purchased_scans = round( annual_scans × (1 + buffer_pct) )                                 # see pricing-model.md
```

`base_pages` is the page count from Stage 1 (use the range low/anchor/high; the anchor is
the planning number). Layers are **additive** — a page in the annual baseline can ALSO be in the
weekly slice; percentages need not sum to 100%.

## 2. Multipliers (defaults + the ask)

| Multiplier | Default | Set higher when… |
|---|---|---|
| **geographies** | 1 | the customer needs verified behavior in multiple regulated regions/markets (EU, US-CA, …). One geo test-location per region they care about. |
| **scenarios** (consent states / user profiles) | by regulation: **CCPA/CPRA → 3** (Default + Opt-Out + GPC), **GDPR/ePrivacy → 2** (Accept-All + Reject-All), **HIPAA / none → 1** | extra logged-in/out states or personas matter. Mirrors account-config's "one audit per consent-state × purpose." |
| **environments** | 1 (prod only) | they validate in staging/pre-prod before release → **1.5** (prod + staging). Common in analytics validation, rare in privacy. |

`geographies × scenarios` together equal what ObservePoint's public calculator calls the
"geoPersonaMultiplier"; we keep them separate for clarity.

## 3. Cadence — use the frequency advisor

Cadence is now driven by the **frequency advisor** — see `frequency-advisor.md`. That reference holds
the 5-layer anchor-high ladder, each layer's customer-facing "why", anchor-high default percentages
(blended ≈ 11 scans/page/year), and pull-back guidance. The use-case profiles and their static
cadence templates are superseded; the frequency advisor is the single seed.

The key risk-framing question is still: **"how long can you tolerate an undetected issue?"** (and for
privacy: cadence also builds a **legal-evidence record**). Surface this framing when walking the
frequency-advisor layers with the rep.

## 4. Reconciliation vs the public calculator

Report the **implied blended frequency** = `annual_scans / use_case_pages`. ObservePoint's public
calculator applies ONE blended frequency to all pages; our layered model is richer. Surfacing the
implied blended frequency lets the rep see whether a customer self-serving on the website (single
frequency) would land near the same number — so nobody is blindsided. Price is always the live
graduated number regardless (see `pricing-model.md`).

## 5. The consultative rule + ask-the-customer map

**Never invent an unknown silently, and never block waiting.** For each input you don't have: apply
the labeled default below, and add a line to an **"Assumptions to verify with the customer"** list in
the output.

| Input | Default if unknown | Question to ask the customer |
|---|---|---|
| use case | rep selects (privacy / analytics / accessibility) | "Is this primarily privacy/consent monitoring, analytics validation, or accessibility?" |
| geographies | 1 | "Which regulated regions/markets need verified behavior? (EU, US-CA…)" |
| scenarios | by regulation (CCPA 3 / GDPR 2 / else 1) | "Which privacy regs apply? Which consent states (opt-in/opt-out/GPC) + logged-in/out matter?" |
| environments | 1 (prod) | "Do you validate in staging/pre-prod before release?" → 1.5 if both |
| cadence mix | frequency-advisor ladder (`frequency-advisor.md`) | "Two drivers: how fast does the site change, and how long can you tolerate an undetected issue? (privacy = legal-exposure window; analytics = data-quality window). Which pages are revenue/consent-critical?" |
| buffer % | 0% (none) | "Want headroom above predicted usage for growth/spikes? (e.g. +10%)" |
