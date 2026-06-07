# ObservePoint Revenue — Scope Calculator (design spec)

**Date:** 2026-06-06
**Author:** Jarrod Wilbur (jarrod.wilbur@observepoint.com) + Claude
**Status:** Approved design, pending spec review → implementation plan

---

## 1. Purpose & background

ObservePoint's pricing is **usage-based**: a customer buys the number of page-scans they
will run in a year. Two questions block every deal:

1. **"How many pages do I even have?"** — answered by ObservePoint Site Census (Part 1).
2. **"How do I multiply that into annual usage, and what does it cost?"** — answered by
   the multiplier × cadence × pricing engine (Parts 2–3).

Today the revenue team answers #2 with a fragile spreadsheet (`Scope Calculator.xlsx`)
that has two near-duplicate sheets (annual vs monthly) and a hardcoded, **stale** price
of $0.135/page that does not match ObservePoint's public pricing calculator.

This project replaces that with a consultative, deterministic skill that produces a
**defensible annual page-scan usage number and a live, authoritative price**, plus a
customer-facing proposal one-pager and an evidence appendix that shows the customer *why*
that page count is what it is.

This is the **first capability** of a broader **`observepoint-revenue`** plugin that will
later grow account research, enrichment, contact finding, and other revenue tooling.

---

## 2. Goals / non-goals

### Goals
- One memorable entry point (`scope-calculator`) a rep invokes to scope any prospect/customer.
- Derive a **defensible page-count range** (low/anchor/high + confidence) from Site Census,
  per the Part 1 brief (`SCOPE CALCULATOR SKILL.md`).
- Apply **layered-cadence** usage math (whole-site baseline + higher-cadence critical slices),
  grounded in ObservePoint account-config best practices.
- Price the resulting annual page-scans through ObservePoint's **live** graduated pricing
  table (sole source of truth), with a baked last-known-good fallback.
- Take a **consultative** approach: default every unknown, label it, and tell the rep exactly
  what to ask the customer to firm up the quote.
- Produce a customer-facing **`.docx` proposal one-pager**, with the full internal breakdown
  shown in chat for the rep.
- Produce a customer-facing **`.xlsx` evidence appendix** that backs the page count with the
  Site Census per-domain data — proving the number is evidence-based (not pulled "out of
  nowhere") and letting the customer **validate the domain scope** (include/exclude, priority).

### Non-goals (v1)
- **No journey-run scoping.** Journeys default to the pricing page's free tier ($0); noted,
  not metered. Add later.
- **No pricing override / discounting in-skill.** The live calculator is authoritative; if a
  rep needs something bespoke, they tweak the skill's output themselves (uncommon).
- **No use of the spreadsheet's $0.135 flat rate** — ignored entirely.
- Not a CRM/Salesforce integration; output is copy-paste + a file.

---

## 3. Architecture

Plugin: **`observepoint-revenue`**. Three skills; one entry point.

```
observepoint-revenue/
├── .claude-plugin/plugin.json              # manifest: name, version, description
└── skills/
    ├── scope-calculator/                   # ★ ENTRY POINT — the only skill reps must remember
    │   └── SKILL.md                         #   orchestrates derive-page-count → size-and-price → proposal
    ├── derive-page-count/                   # Part 1 — Site Census page-count (reusable standalone)
    │   ├── SKILL.md
    │   ├── references/site-census-methodology.md
    │   └── scripts/build_evidence_appendix.py   # per-domain JSON → customer evidence .xlsx
    └── size-and-price/                      # Parts 2+3 — usage engine + live pricing + tier classify
        ├── SKILL.md
        ├── references/usage-methodology.md  # multipliers, cadence table, use-case profiles, ask-the-customer map
        ├── references/pricing-model.md      # official model, fallback table, refresh path, journey note
        └── scripts/
            ├── fetch_pricing.py             # fetch + parse live Gt table from JS bundle; baked fallback
            └── compute_scope.py             # deterministic math: inputs JSON → full breakdown JSON
```

**Orchestration:** `scope-calculator`'s SKILL.md drives the session — it invokes
`derive-page-count` (Part 1), then `size-and-price` (Parts 2–3), then renders the proposal.
Reps only invoke `scope-calculator`. The two sub-skills are independently invocable for
power users and future reuse, but never required knowledge for a rep.

**Why this granularity:** `derive-page-count` is genuinely reusable (future account research),
so it earns its own skill. `size-and-price` is one continuous flow with no independent reuse,
so usage/pricing/proposal stay together. Splitting further would be over-engineering.

---

## 4. The calculation engine

### 4.1 Pipeline

```
Part 1: page-count range            Part 2: multipliers + layered cadence           Part 3: live pricing
(low / anchor / high, confidence) → use_case_pages = base × geos × scenarios × env → annual_scans priced
                                    annual_scans = Σ_c (use_case_pages × pct_c × runs_per_year_c)   through live tiers
```

### 4.2 Multipliers (kept granular; product reconciles to the official "geoPersonaMultiplier")

- **geographies** — number of geo test locations. Default `1`.
- **scenarios** (consent states / user profiles) — default by regulation:
  CCPA/CPRA → `3` (Default + Opt-Out + GPC), GDPR/ePrivacy → `2` (Accept-All + Reject-All),
  HIPAA / none → `1`. (Mirrors account-config's "one audit per consent-state × purpose".)
- **environments** — prod only → `1`; prod + staging/pre-prod → `1.5` (matches the official
  `jF`: both = 1.5, single = 1). Common in analytics-validation, rare in privacy.

`use_case_pages = base_pages × geographies × scenarios × environments`

### 4.3 Layered cadence model (the spreadsheet's model, made airtight)

For each cadence layer `c` the rep assigns a percentage of pages and a runs/year:

| Cadence layer | runs/year | Typical role (account-config cadence table) |
|---|---|---|
| per-deploy (triggered) | rep-supplied estimate | release-gate / staging |
| daily | 365 | tier-1 revenue / consent-critical |
| weekly | 52 | standard production |
| monthly | 12 | stable / low-change |
| quarterly | 4 | periodic deep check |
| annual baseline | 1 | full-site inventory/audit |

`runs_c = use_case_pages × pct_c × runs_per_year_c` (layers are **additive** — a page in the
annual baseline can also be in the weekly slice). `annual_scans = Σ_c runs_c`.

Percentages need **not** sum to 100% — the annual baseline is typically 100% and higher
cadences are smaller critical slices layered on top.

### 4.4 Official pricing model (reverse-engineered; sole source of truth)

From `https://app.observepoint.com/www-pricing/main.js` (the public calculator's Angular bundle):

**Graduated audit page-scan tiers (`Gt`)** — each band's width priced at its rate, summed:

| Band width (pages) | Rate / page |
|---|---|
| first 1,000 | $0.00 (free) |
| next 50,000 | $0.17 |
| next 500,000 | $0.12 |
| next 1,000,000 | $0.06 |
| next 5,000,000 | $0.04 |
| next 50,000,000 | $0.03 |

**Tier classifier (`$F`):** `annual_scans < 600,000` → *starter*; `≤ 6,000,000` → *professional*;
else *enterprise*.

**Official master formula (`Ef`), for reconciliation only:**
`annual_scans = round(totalPages × frequency × geoPersonaMultiplier × environment)`, where
`frequency` (`VF`) is a single value or a weighted average of a frequency mix, and
`environment` (`jF`) is 1.5 (both) or 1. Our skill keeps geos and scenarios **separate**;
their product equals the official `geoPersonaMultiplier`.

**Journeys (`UF` / `journeyTierLabel`) — v1 default = free tier ($0):** ≤100 runs free,
≤1,500 $2.5K, ≤6,000 $5K, ≤36,000 $15K, else $30K. Not metered in v1.

### 4.5 Live fetch + fallback (`fetch_pricing.py`)

1. Fetch the bundle URL.
2. Regex-extract the `Gt=[{limit:…,pricePerPage:…},…]` array and validate
   (≥5 bands, positive band widths, non-negative & non-increasing paid rates — note `limit` is a
   band WIDTH, not a cumulative cap, so widths are NOT required to increase).
3. On success: return parsed table + a `pricing_source = "live @ <timestamp>"` stamp.
4. On any failure (network, parse, validation): return the **baked last-known-good** table
   (the §4.4 values), set `pricing_source = "fallback (baked <date>)"`, and surface a visible
   warning so the rep knows to refresh.

`compute_scope.py` applies the graduated math identically to the website
(`Σ over bands of min(band_width, remaining) × rate`).

### 4.6 Per-domain evidence (Part 1 output contract → evidence appendix)

`derive-page-count` (Part 1) must surface, in addition to the rolled-up range, a **per-domain
table** — this is both the page-count evidence and the raw material for the appendix:

```
per_domain[] = { hostname, raw_urls, paths, patterns, spiral_flag, spiral_ratio,
                 defensible_pages, discounted, why }   # why = human note, e.g. "349× query-param spiral"
rollup = { url_total, path_floor, spiral_adjusted_anchor, low, high, confidence,
           census_ids, crawl_status, thresholds_swept }
```

`defensible_pages` = paths for spiral-flagged domains, distinct URLs otherwise (the Part 1
spiral-adjusted rule). The per-domain rows MUST sum to the rolled-up anchor — a tested invariant.

### 4.7 Optional buffer (purchased vs predicted usage)

Reps may add a customer-requested **buffer** so the contract carries headroom above predicted
usage (growth, seasonal spikes). Optional input `buffer_pct` (default `0`). Applied as the LAST
step before pricing:

`purchased_scans = round(annual_scans × (1 + buffer_pct))`

Pricing and tier classification use `purchased_scans` (the number actually bought). The chat and
proposal always show **both** numbers, e.g. *"110,000 purchased = 100,000 predicted + 10% buffer."*
The buffer scales the low/anchor/high range uniformly (§7).

---

## 5. Consultative input map (defaults + the question to ask)

The skill never blocks on an unknown. It applies a labeled default and emits the exact ask.

| Input | Default if unknown | Question the skill tells the rep to ask the customer |
|---|---|---|
| use case | analytics-validation OR privacy (rep selects up front) | "Is this primarily privacy/consent monitoring, analytics validation, or accessibility?" |
| geographies | 1 | "Which regulated regions/markets need verified behavior? (EU, US-CA…)" |
| scenarios | by regulation (CCPA 3 / GDPR 2 / else 1) | "Which privacy regs apply? Which consent states (opt-in/opt-out/GPC) + logged-in/out matter?" |
| environments | 1 (prod) | "Do you validate in staging/pre-prod before release?" → 1.5 if both |
| cadence mix | use-case profile (§6) | "Two drivers: how fast does the site change, and **how long can you tolerate an undetected issue?** (privacy = unauthorized-data-collection / legal-exposure window; analytics = data-quality-degradation window). Which pages are revenue/consent-critical?" |
| buffer % | 0% (none) | "Want headroom above predicted usage for growth/spikes? (e.g. +10%)" |

Every output ends with an **"Assumptions to verify with the customer"** checklist listing each
defaulted unknown and its ask, so the rep knows precisely what firms up the quote.

---

## 6. Use-case profiles (seed defaults)

**Cadence is risk-driven, not just volatility-driven.** Beyond "how fast does the site change?",
the deciding question is *"how long can you tolerate an undetected issue?"* — and for privacy,
cadence also builds a **legal-evidence record**. The skill frames the cadence conversation this way.

- **Privacy / consent monitoring** — "catch active issues across the whole site." Cadence is driven
  by (a) the **legal-exposure window** — how long you can tolerate unauthorized data collection
  before it becomes regulatory/litigation risk; and (b) **evidentiary cadence** — regular,
  time-stamped scans at a *consistent* frequency demonstrate ongoing diligence and are usable if a
  regulator or plaintiff alleges a violation (ties to the litigation-defense value prop). Higher and
  consistent cadence = stronger legal posture. Scenarios multiplier active (CCPA ×3 / GDPR ×2),
  environments ×1, broad coverage. Default: 100% annual baseline + a meaningful monthly/quarterly slice.
- **Analytics validation** — "verify tagging before release." Cadence is driven by the **data-quality
  window** — how long you can tolerate degraded/missing data flowing into reporting, ad spend, and
  attribution before it's caught. Environments ×1.5 (prod+staging), scenarios ×1, targeted. Default:
  critical conversion pages weekly/daily + full-site quarterly.
- **Accessibility** (stretch) — periodic full-site sweeps; scenarios/environments ×1.

---

## 7. Range, confidence & reconciliation

- Part 1 hands over **low / anchor / high + confidence**. The engine runs the full calc at all
  three → a **price range**; the anchor is the recommended quote.
- Part 1 transparency (e.g. "excluded ~388K query-param spiral URLs") and confidence carry
  through to the chat output.
- **Buffer** (§4.7), if set, scales low/anchor/high uniformly; the recommended quote is the
  buffered (purchased) anchor, always shown alongside the predicted number.
- **Usage reconciliation note:** the skill reports the implied blended frequency
  (`annual_scans / use_case_pages`) and what a customer self-serving on the website (single
  frequency) would see, so the rep is never blindsided by a discrepancy. Price itself is always
  the live graduated number.

---

## 8. Outputs

- **Chat (rep-facing, internal):** page-count range + confidence + what was discounted; each
  multiplier with rationale; the cadence table; annual_scans range; predicted vs purchased
  (buffer); tier (starter/professional/enterprise); live price-by-band breakdown with
  `pricing_source` stamp; total price range; recommended quote; reconciliation note;
  "Assumptions to verify" checklist.
- **`.docx` (customer-facing):** clean one-pager via the `docx` skill — customer name, scope
  (domains, page universe, what OP monitors + how often, regs covered), recommended annual usage,
  price. If a buffer is applied, the doc **explicitly states it** (purchased = predicted + N%
  buffer). **Excludes** internal discounting and spiral/discount notes.
- **`.xlsx` evidence appendix (customer-facing):** deterministic, built by
  `build_evidence_appendix.py` from the §4.6 per-domain data. Sheets:
  1. **Scope Summary** — customer, census ID(s), crawl completeness + confidence, page-count
     low/anchor/high, total raw URLs vs total defensible pages (the discount at a glance), and a
     "review the Domains tab to confirm scope" callout.
  2. **Pages by Domain (defensible)** — `Domain | Defensible pages | Spiral? | Include in scope? |
     Priority | Notes`. The last three are **customer-fillable** to validate scope + flag tiering.
  3. **Raw Evidence (the "why")** — `Domain | Raw distinct URLs | Distinct paths | Spiral ratio |
     Discounted | Why`. The defensibility proof (what we discounted and why).
  4. **URL Samples (truncated)** — capped per-domain sample of real URLs so the customer can
     eyeball that these are genuine pages.

---

## 9. Guardrails (air-tight)

- **All math in `compute_scope.py`** — no LLM arithmetic. Reproducible and unit-tested.
- **Live pricing** validated on parse; baked fallback + visible warning on failure; always stamped.
- **Site Census admin discipline** (Part 1 brief): `whoami` → impersonate central census account
  → revert; for any census write, state account + plan, get explicit go-ahead, `confirm_account_plan`,
  act, revert. Never quote raw URL totals; spiral discounting transparent.
- **Never fabricate a page count.** If no usable census exists → cold-start hand-off (create +
  start census, tell rep crawl takes hours-to-days, return later). Never block on a crawl.

---

## 10. Testing plan (TDD, per writing-skills)

- **Deterministic scripts → pytest:**
  - `compute_scope.py`: fixture from the spreadsheet — base 197,000, geos 2, scenarios 3, env 1,
    cadence {annual 100%×1, quarterly 5%×4, weekly 0.4%×52, daily 0%} → **annual_scans = 1,664,256**.
  - Pricing: 1,664,256 annual_scans through the live tiers → **$133,030.24** (avg ~$0.0799/page),
    tier *professional*. (0 + 50,000×.17 + 500,000×.12 + 1,000,000×.06 + 113,256×.04.)
  - `fetch_pricing.py`: parser handles the live bundle, malformed bundle → fallback, validation gate.
  - Buffer: `annual_scans` 100,000 + `buffer_pct` 0.10 → `purchased_scans` 110,000 priced through
    live tiers; both predicted and purchased reported; `buffer_pct` 0 is a no-op.
  - `build_evidence_appendix.py`: per-domain JSON → workbook with the 4 sheets; the per-domain
    `defensible_pages` sum equals the rolled-up anchor (invariant from §4.6); customer-fillable
    columns (Include in scope?, Priority, Notes) present and empty.
- **SKILL.md behavior → subagent pressure tests (RED first):** baseline without the skill, then
  verify the agent (a) gathers inputs consultatively, (b) defaults-and-flags unknowns rather than
  inventing them, (c) refuses to fabricate a page count, (d) never quotes raw URL totals, (e) uses
  live pricing with the stamp, (f) produces the `.docx`. Close loopholes; build a rationalization table.

---

## 11. Future extensions (not v1)

- Journey-run scoping as a second usage meter (the calculator already prices it).
- Additional `observepoint-revenue` skills: account research, firmographic enrichment, contact finding.
- A shared `references/` for cross-skill ObservePoint product/pricing facts.

---

## 12. Resolved decisions

| # | Decision | Choice |
|---|---|---|
| Scope | plugin vs single skill | `observepoint-revenue` plugin, 3 skills, single `scope-calculator` entry |
| Pricing source | sheet vs live vs rep | **live calculator only** (sole truth, no override) |
| Output | md / xlsx / docx | **`.docx` proposal** + **`.xlsx` evidence appendix** + full chat breakdown |
| Usage model | layered vs blended | **layered cadences**, priced through live tiers, reconciled vs website |
| Journeys | meter vs none | **none in v1** — free-tier default ($0) |
| Buffer | none vs optional | **optional `buffer_pct`** (default 0); priced on purchased number; called out in the proposal |

---

## 13. Plan 2 contract notes (from the engine final review)

Plan 1 (the deterministic engine) is built and tested (33 tests). The orchestration layer (Plan 2 —
the three SKILL.md files + `.docx` proposal + Site Census MCP wiring) must honor these seams:

- **`compute()` input** (`size-and-price/scripts/compute_scope.py`): `{customer, use_case,
  page_count:{low,anchor,high,confidence}, multipliers:{geographies,scenarios,environments},
  cadence_layers:[{name,pct,runs_per_year}], buffer_pct, tiers?, pricing_source?|source?}`.
  Missing required keys raise raw `KeyError` — **the orchestrator owns input validation**.
- **`fetch_pricing()` output**: `{tiers, source}`. Pass `tiers` and `source` straight into
  `compute()` (it accepts `source` as an alias for `pricing_source`). When `source` starts with
  `"fallback"`, the orchestrator must surface the spec §4.5 refresh warning in chat — the engine
  only stamps, it does not warn.
- **Single Part-1 object feeds both price and evidence.** The evidence appendix's
  `rollup.spiral_adjusted_anchor` and `compute()`'s `page_count.anchor` must be the SAME number
  (likewise `low`/`high`). Derive them from ONE Part-1 output, don't re-state the anchor twice.
  `build_evidence_appendix` requires `hostname`, `raw_urls`, `defensible_pages` per domain and
  `rollup.spiral_adjusted_anchor`; all other per-domain fields are optional.
- **Tier is classified on the buffered (purchased) number.** A buffer can push a deal across a tier
  boundary — the "predicted vs purchased" chat output should make that visible when it happens.
- **Range payload is lean:** `range.low/high` carry only `{predicted_scans, purchased_scans,
  price_total}` (full per-band/tier/cadence detail is on `anchor` only). If the chat wants a
  per-band table at the range endpoints, the orchestrator must call `graduated_price` itself.
