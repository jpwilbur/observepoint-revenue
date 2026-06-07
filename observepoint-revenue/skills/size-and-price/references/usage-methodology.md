# Usage methodology — multipliers, cadence, and the consultative flow

Reference for the `size-and-price` skill. Turns a defensible page count into an annual page-scan
usage number. The math is deterministic in `scripts/compute_scope.py`; this file is the judgment
layer — how to choose the inputs and what to ask the customer.

## 1. The model

```
use_case_pages = base_pages × geographies × scenarios × environments
annual_scans   = Σ over cadence layers c of ( use_case_pages × pct_c × runs_per_year_c )   # additive
purchased_scans = round( annual_scans × (1 + buffer_pct) )                                 # see pricing-model.md
```

`base_pages` is the page count from `derive-page-count` (use the range low/anchor/high; the anchor is
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

## 3. Cadence is risk-driven, not volatility-driven

Beyond "how fast does the site change?", the deciding question is **"how long can you tolerate an
undetected issue?"** — and for privacy, cadence also builds a **legal-evidence record**.

| Cadence layer | runs/year | Property role (account-config) |
|---|---|---|
| per-deploy (triggered) | rep-estimated | release-gate / staging |
| daily | 365 | tier-1 revenue / consent-critical |
| weekly | 52 | standard production |
| monthly | 12 | stable / low-change |
| quarterly | 4 | periodic deep check |
| annual baseline | 1 | full-site inventory/audit |

## 4. Use-case profiles (seed defaults)

Each profile ships a **concrete starting cadence template** (a list of `{pct, runs_per_year}` layers)
so the default is deterministic, not a guess. **Cadence is the #1 thing to confirm with the customer**
— always present the template as a labeled assumption-to-verify, never as settled fact. A "slice" is a
*fraction* of pages (a critical subset), not the whole site.

- **Privacy / consent monitoring** — "catch active issues across the whole site." Cadence driven by
  (a) the **legal-exposure window** (how long you can tolerate unauthorized data collection before it
  becomes regulatory/litigation risk) and (b) **evidentiary cadence** (regular, time-stamped scans at a
  *consistent* frequency demonstrate ongoing diligence and are usable if a regulator or plaintiff
  alleges a violation — the litigation-defense value). Higher + consistent cadence = stronger legal
  posture. Scenarios active (CCPA ×3 / GDPR ×2), environments ×1, broad coverage.
  **Starting template:** annual baseline 100% × 1/yr + quarterly slice 5% × 4/yr + monthly critical
  slice 2.5% × 12/yr (implied blended ≈ 1.5×).
- **Analytics validation** — "verify tagging before release." Cadence driven by the **data-quality
  window** (how long you can tolerate degraded/missing data flowing into reporting, ad spend, and
  attribution before it's caught). Environments ×1.5 (prod+staging), scenarios ×1, targeted.
  **Starting template:** annual baseline 100% × 1/yr + quarterly slice 5% × 4/yr + weekly
  conversion-critical slice 0.4% × 52/yr (implied blended ≈ 1.4×).
- **Accessibility** (stretch) — periodic full-site sweeps; scenarios/environments ×1.
  **Starting template:** annual baseline 100% × 1/yr + quarterly slice 25% × 4/yr (implied blended ≈ 2×).

## 5. Reconciliation vs the public calculator

Report the **implied blended frequency** = `annual_scans / use_case_pages`. ObservePoint's public
calculator applies ONE blended frequency to all pages; our layered model is richer. Surfacing the
implied blended frequency lets the rep see whether a customer self-serving on the website (single
frequency) would land near the same number — so nobody is blindsided. Price is always the live
graduated number regardless (see `pricing-model.md`).

## 6. The consultative rule + ask-the-customer map

**Never invent an unknown silently, and never block waiting.** For each input you don't have: apply
the labeled default below, and add a line to an **"Assumptions to verify with the customer"** list in
the output.

| Input | Default if unknown | Question to ask the customer |
|---|---|---|
| use case | rep selects (privacy / analytics / accessibility) | "Is this primarily privacy/consent monitoring, analytics validation, or accessibility?" |
| geographies | 1 | "Which regulated regions/markets need verified behavior? (EU, US-CA…)" |
| scenarios | by regulation (CCPA 3 / GDPR 2 / else 1) | "Which privacy regs apply? Which consent states (opt-in/opt-out/GPC) + logged-in/out matter?" |
| environments | 1 (prod) | "Do you validate in staging/pre-prod before release?" → 1.5 if both |
| cadence mix | use-case profile (§4) | "Two drivers: how fast does the site change, and how long can you tolerate an undetected issue? (privacy = legal-exposure window; analytics = data-quality window). Which pages are revenue/consent-critical?" |
| buffer % | 0% (none) | "Want headroom above predicted usage for growth/spikes? (e.g. +10%)" |
