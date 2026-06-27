# revenue-insights engine + domo-core foundation — design

- **Date:** 2026-06-26
- **Status:** Draft for review
- **Author:** Jarrod Wilbur (Solutions Consultant) with Claude
- **Roadmap:** New — the general revenue-analytics engine the Active-sequence CS items
  (customer review builder, expansion radar, consumption pacing monitor) become consumers of.

## Context

The rev-ops director built a "Renewals at Risk" report by hand with Claude + the Salesforce MCP. The
ask here is **not that one report** — it's the *capability* that produces world-class revenue insight
at **every altitude** of a SaaS revenue org (board/CRO, VP Sales, RevOps, frontline AE, CSM, Finance),
from a question in chat, with the numbers defensible and reproducible.

Three data sources are now reachable: **Salesforce** (system of record for live deals — pipeline,
opps, renewals, activity), **Domo** (the curated warehouse — board-grade ARR/NRR/GRR, cohorts,
financial roll-ups, often blending SF + billing + product), and **ObservePoint's own usage telemetry**
(via the OP MCP — essential for consumption pacing). The division of labor: **SF = live deals, Domo =
curated truth, OP = product usage.**

This is the first plugin capability whose questions are *unbounded*. The whole design is about keeping
the plugin's iron architecture rule intact under that openness.

## The architecture rule (the crux)

The plugin invariant: *Claude gathers and judges → deterministic Python computes and renders; no LLM
math, no LLM-maintained state.* It holds here because MCP tools are **model-invoked, not callable from
Python**:

> **The model calls the SF / Domo / OP MCPs (the *gather* step); deterministic Python only ever
> parses, computes, and renders from the returned JSON (the *compute* step). No Python script fetches
> a source. No model arithmetic. No model-held state.**

Every number in every report is produced by a tested Python script. The model classifies the ask,
runs the queries, judges the "so what," and narrates caveats — it never does the arithmetic.

**Read-only**, matching `salesforce-core`. No SF/Domo/OP writes in this work; any future write-back is
deferred and governed separately.

## Scope

**In scope (Phase 1)**
- A new foundation skill **`domo-core`** (twin of `salesforce-core`): canonical dataset map +
  `domo_io.py` digester. Read-only.
- A new engine skill **`revenue-insights`**: the metrics canon, the recipe catalog, the per-recipe
  compute scripts, shared compute helpers, the branded in-chat **viz kit**, and the ad-hoc fallback.
- **Four seed recipes** spanning every altitude and all three sources:
  1. **renewals-at-risk** (RevOps/CSM; SF) — rebuild the screenshot, better. *Built first* as the
     anchor that validates the viz kit against a known-good target.
  2. **pipeline-coverage & forecast-pacing** (VP Sales; SF live + Domo trend).
  3. **arr-nrr-bridge** (Board/CRO; Domo curated).
  4. **consumption-pacing** (CSM; OP usage + SF contract terms).
- Live, read-only Domo inventory at implementation start to author `domo-datasets.md`.
- Tests for every compute script + the viz kit against fixture MCP JSON.

**Out of scope (future / Phase 2)**
- Refactoring the roadmap CS items (review builder, expansion radar, pacing monitor) into thin
  consumers of the engine.
- Any SF/Domo/OP **write**.
- Scheduled/automated report delivery (the `scheduled-tasks` MCP is a later enhancement).
- Recipes beyond the four seeds (they accrete over time; the ad-hoc path covers the gap meanwhile).

## Decisions captured during brainstorming

1. **Structure:** Approach C — foundation (`domo-core`) + engine (`revenue-insights`) + future
   consumers. *(chosen over a single knowledge-rich skill and over a strict recipe-only catalog.)*
2. **Hero deliverable:** in-chat branded **visual** first (like the screenshot); PDF/deck/`.xlsx`
   exports are on-request via `branding-guide`.
3. **Data division:** SF = live deals · Domo = curated truth · OP = product usage. Engine picks the
   source per metric; the canon records which source is authoritative for each.
4. **Engine name:** `revenue-insights`.
5. **Recipe-catalog-first with an ad-hoc fallback** — vetted recipes carry tested compute scripts;
   novel asks use the canon + a generic compute helper, clearly labeled, with a promote-to-recipe path.
6. **Quota/target source:** unknown today → **discover during the live SF/Domo inventory**, record in
   the canon.
7. **Domo probe:** read-only inventory at implementation start is approved.
8. **Read-only**, mirroring `salesforce-core`.

## Design

### A. `domo-core` (curated-truth foundation)

A new skill `observepoint-revenue/skills/domo-core/`, structured exactly like `salesforce-core`:

1. **`references/domo-datasets.md`** — the canonical, human-readable map: the Domo datasets/columns
   this plugin reads, the **named `DomoSqlQueryTool` queries** recipes run, which metric each dataset
   is *authoritative* for, refresh cadence/hygiene caveats, and the read-only rule. Authored from a
   live, read-only probe (`SearchTool` to inventory datasets, a few sample `DomoSqlQueryTool` /
   `FileSetQueryTool` reads to confirm columns). When Domo changes, this file changes.
2. **`scripts/domo_io.py`** — deterministic helpers that *parse, shape-check, coerce* the JSON the
   Domo MCP returns. Never calls Domo. Initial functions:
   - `parse_query_result(mcp_result)` → list of row dicts; validates the result envelope, raises on
     known error shapes so callers fall back cleanly.
   - type coercion (numeric/date) + null handling for downstream compute.

`tests/conftest.py` adds `domo-core/scripts` to `sys.path` so other skills `import domo_io`, mirroring
the `salesforce-core` arrangement.

### B. `revenue-insights` (the engine)

A new skill `observepoint-revenue/skills/revenue-insights/`.

**B1. `references/metrics-canon.md` — the encoded judgment.**
The world-class core. For each metric: its **definition/formula**, its **canonical source** (SF /
Domo / OP), and its **gotchas**. This is what makes two people compute the same NRR and what makes an
ad-hoc answer trustworthy. Covers at least: ARR, NRR, GRR, the renewal/expansion/contraction/churn
bridge, pipeline coverage ratio, forecast categories (commit/best-case/closed), risk-weighting,
consumption pacing, win-rate, sales-cycle, cohort retention. Cross-cutting methodology rules:
- **Currency:** never fabricate FX. Show native currency; aggregate across currencies only when Domo
  supplies an FX rate, and label converted totals. (The screenshot keeps USD and GBP separate and
  risk-weights within currency — that is the rule, encoded.)
- **Periods:** fiscal vs calendar. Fiscal calendar lives in config (`periods.py`); **fiscal year
  start to be confirmed during implementation** — the screenshot implies FY starts Feb 1 (Q2 FY26 =
  May 1–Jul 31), to verify against SF/Domo before encoding.
- **Partial periods & stale data:** explicit rules for in-window close dates and how stale opps are
  treated (and surfaced).
- **Reconciliation:** when live SF and curated Domo disagree, **show both, labeled by source; never
  silently pick.** The canon names the authoritative source per metric.

**B2. `references/recipe-catalog.md` — the index.**
One entry per vetted recipe: altitude/persona, the queries it runs, its compute script, its viz
layout. The discoverable menu of "what we can build with a tested recipe."

**B3. `scripts/` — deterministic compute.**
- One compute script per recipe: `renewals_at_risk.py`, `pipeline_coverage.py`, `arr_nrr_bridge.py`,
  `consumption_pacing.py`. Each takes the gathered MCP JSON, digests it via `sf_io` / `domo_io` /
  an OP-usage parser, and returns a structured result object (the numbers + the rows + the caveats).
- Shared helpers: `currency.py` (native + labeled conversion), `periods.py` (fiscal calendar +
  partial-period logic), `risk_weight.py` (health-score → risk-weighted ARR).
- All deterministic, all fixture-tested.

**B4. `scripts/viz_kit.py` — the branded in-chat visual.**
A render kit producing a **self-contained branded HTML artifact** shown in chat, in the dark NERD
theme `research-account` uses. Component vocabulary drawn from the screenshot: KPI stat-cards (count
+ ARR + sub-label), ranked tables, **health badges** (Green/Yellow/Red/Black), risk-weighted columns,
section headers, a caveats footnote. **Brand values come from `branding-guide`'s `brand-spec.json`
via `brand_kit` — never hardcoded.** Takes a recipe's structured result, emits HTML. Exports
(PDF/deck/`.xlsx`) reuse the existing `branding-guide` document kit on request.

### C. Request flow (the shared spine)

1. **Classify** — Claude maps the ask → altitude + recipe (or ad-hoc) + sources + parameters
   (period, segment, territory). Territory/segment resolution **reuses `salesforce-core`**.
2. **Gather** — Claude runs the queries via MCP: SF `soqlQuery`/`find`, Domo `DomoSqlQueryTool`,
   OP usage tools.
3. **Compute** — the recipe script (or the generic helper) digests the JSON and computes every number.
4. **Render** — `viz_kit` builds the visual from the result; Claude narrates the "so what" + caveats.
5. **Export on request** — PDF / deck / `.xlsx` via `branding-guide`.

### D. The ad-hoc fallback (limitless without breaking the rule)

When no recipe matches, the engine uses `metrics-canon` + a **generic compute helper** (Claude writes
the SF/Domo SQL → generic Python aggregation → viz kit). The output is **explicitly labeled
"ad-hoc — computed live, methodology per canon, not yet a vetted recipe,"** with a promote-to-recipe
note. Arithmetic still happens in Python; nothing is LLM math. Recurring good ad-hocs graduate into
tested recipes.

### E. Altitude catalog (the menu the engine grows into)

The "all levels" requirement is satisfied by **altitude as a lens over one engine**, not separate
skills. Representative analyses (seeds in **bold**):

- **Board / CRO** (Domo): **ARR/NRR bridge**, net-new ARR vs plan, retention by cohort, risk-adjusted
  forecast roll-up.
- **VP Sales** (SF + Domo): **pipeline coverage & forecast pacing**, win-rate & sales-cycle by
  segment/source, rep attainment & ramp, stage-conversion velocity & slippage.
- **RevOps** (SF + Domo): **renewals-at-risk**, forecast integrity (stale opps, missing close dates,
  push counts), territory/segment heatmaps, lead→opp→won funnel & SLA.
- **Frontline AE** (SF): my quarter / what to work, deals slipping, my at-risk renewals + next best
  actions, gap-to-goal.
- **CSM** (SF + OP): **consumption pacing (usage vs contract)**, at-risk book, expansion whitespace,
  review/QBR prep pack.
- **Finance / Deal desk** (Domo): bookings vs billings, ARR waterfall, discounting, cohort LTV, mix.

### F. Testing

Every compute script + `viz_kit` is tested against **fixture MCP JSON** (captured SF/Domo/OP
responses) — **no live source in the test suite**, mirroring `salesforce-core`. Fixtures include:
- renewals-at-risk: mixed-currency (USD + GBP), mixed health (incl. the "Green but flagged WNR"
  edge), in-window vs out-of-window close dates.
- pipeline-coverage: coverage ratio math, forecast-category splits, a missing-quota case.
- arr-nrr-bridge: the new/expansion/contraction/churn waterfall reconciling to NRR/GRR.
- consumption-pacing: over- / under- / on-pace against contract terms; missing-usage fallback.
- `domo_io` / OP-usage parser error-envelope handling → clean fallback.
- a viz-kit snapshot per recipe (brand values resolved from `brand-spec.json`).

## Assumptions to verify during implementation (never fabricate)

- **Domo dataset inventory** — exact dataset names/columns and which metric each is authoritative for
  (the live read-only probe).
- **Quota/target location** — SF vs Domo vs elsewhere; record in the canon.
- **Fiscal year start** — confirm Feb 1 (implied by the screenshot) against SF/Domo before encoding.
- **FX availability** — whether Domo carries FX rates for cross-currency aggregation; if not, native
  only.
- **Renewal data shape in SF** — the `Renewal_Forecast__c` field/object behind the screenshot, the
  health-score field, and `Renewable_ARR__c` (named in the screenshot footnote).
- **OP usage ↔ contract bridge** — how page-scan usage maps to the SF contract term for pacing
  (reuses the `OP_Account_ID__c`/`OP_App_ID__c` bridge noted in `salesforce-org.md`).

## Out of scope / future (links the engine forward)

- **Phase 2 — CS consumers:** customer review builder, expansion-signal radar, and consumption-pacing
  monitor refactor to call engine recipes + add their packaging, instead of three separate analytics
  builds.
- **Scheduled delivery** of recurring reports via the `scheduled-tasks` MCP.
- **Write-back** (e.g., pushing a computed health/forecast annotation to SF) — deferred and gated on
  the same rev-ops owned-custom-fields governance contract as the other SF write items.
