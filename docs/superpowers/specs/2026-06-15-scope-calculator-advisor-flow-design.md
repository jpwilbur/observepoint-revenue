# ObservePoint Revenue — Scope Calculator: Advisor Flow & Live Model (design spec)

**Date:** 2026-06-15
**Author:** Jarrod Wilbur (jarrod.wilbur@observepoint.com) + Claude
**Status:** Approved design (decisions locked via brainstorming), pending spec review → implementation plan
**Supersedes/extends:** `2026-06-06-op-revenue-scope-calculator-design.md` (the engine + 3-stage design). That spec stands for the calculation engine, pricing model, and Site Census methodology. This spec changes **how the rep drives the tool** (a guided advisor flow instead of a one-shot generator), **how cadence is proposed** (a rationale-driven, anchor-high ladder), **what the deliverables are** (a live Excel model + a clean snapshot doc + a separate internal file), and **how internal jargon is kept out of customer artifacts.**

---

## 1. Purpose & background

The scope-calculator engine is sound (deterministic page-count → multipliers → layered cadence → live graduated pricing → `.docx` + `.xlsx`). Three problems remain, all surfaced from real use on the **Arthur J. Gallagher** deal:

1. **Frequencies are "plopped," not advised.** The AE's feedback: cadence currently arrives as a pre-baked use-case-profile template (Gallagher shipped with baseline 100%×1 + quarterly 5%×4 + monthly 2.5%×12 ≈ 1.5× blended). It should be proposed like an advisor would — each cadence carrying its *reason*, anchored high, then negotiated down.
2. **The tool makes assumptions it should be eliciting.** Use cases, number of geographies, consent scenarios, and environments are applied as silent defaults from a reference doc. The rep should be walked through each, contributing what they know about the customer; "I don't know" is a first-class answer that falls back to a labeled best practice.
3. **Internal artifacts leak into customer-facing files.** The `.xlsx` exposes a `Spiral?` column, "raw URLs / defensible / reduced", census IDs, crawl status; the `.docx` relies on a manual "remove before sending" section. Anything a customer might see must be clean **by construction**.

A parallel post-mortem on the same deal (`Gallagher census 711, 2026-06-15`) also hardened the **page-count anchor** against silent recursion-trap over-counts (a ~15× inflation that no gate caught). That work is now committed to this repo (`harden/scope-calculator-recursion-port`, commit `c6ac67c`) and this redesign **builds on top of it** (§9).

### Why now
The Gallagher proposal went to the AE and came back with exactly this feedback. The redesign turns the skill into the consultative advisor it was always meant to be, and makes the deliverables safe to put in front of a customer.

---

## 2. Goals / non-goals

### Goals
- Turn the skill into a **guided advisor flow** (in the spirit of the brainstorming skill): recommend-first, one decision at a time, with an explicit "I don't know → labeled best practice" path for every soft input.
- Replace the silent cadence template with a **frequency advisor**: a 5-layer ladder where each cadence carries a customer-facing rationale, opens at an **aggressive anchor-high default**, and is independently kept / adjusted / dropped.
- Make the customer **Investment Model (`.xlsx`) a live calculator**: page count, geos, scenarios, environments, and each frequency's % + cadence are input cells; annual scans and graduated price are live formulas. The customer/AE can flex it themselves.
- Keep customer artifacts **clean by construction**; route all rep-only context into a **separate internal file** that is never forwarded.
- **Adopt** the ported recursion guard and wire it into the flow with explicit rep confirmation of the anchor.
- Preserve the repo's architecture principle: **Claude gathers and judges; deterministic scripts compute and render.** `compute_scope.py` stays the single source of truth for every quoted number.

### Non-goals (v1)
- **No live web/HTML calculator.** The dynamism lives in the workbook (decision §14). An HTML companion is a possible phase 3, explicitly out of scope here.
- **No formulaic `.docx`.** Word cannot do this cleanly; the doc is a static, point-in-time snapshot regenerated when the scenario is locked.
- **No change to the pricing model or the Site Census derivation math** (those are inherited from the 2026-06-06 spec and the recursion-port commit).
- **No journey-run metering** (still free-tier default, flagged — unchanged).
- No CRM integration.

---

## 3. What changes vs. today

| Area | Today | After this redesign |
|---|---|---|
| Interaction | One-shot: gather → compute → emit both files | **Guided advisor flow**, recommend-first, "I don't know" path |
| Cadence | Silent use-case-profile template (~1.5× blended) | **5-layer rationale ladder**, anchor-high (~11× default), per-layer keep/adjust/drop |
| Soft inputs | Applied as silent defaults | **Elicited** with anchored recommendations + the reasoning |
| Customer `.xlsx` | Static "evidence appendix" mixing customer + internal data | **Live Investment Model** (formulas) + clean scope/sample sheets |
| Customer `.docx` | Snapshot with a strippable `[INTERNAL]` section | Clean **by construction**; cadence rows show the "why" |
| Internal data | Mixed into customer files | **Separate internal-evidence file**, never forwarded |
| Anchor safety | Spiral + %22 gates (blind to recursion) | + **recursion detector** (ported) wired into the flow with rep confirmation |

---

## 4. The advisor flow

Five phases. The model orchestrates conversationally — recommend-first, surfacing reasoning, accepting "I don't know." It is **not** freeform: each phase has a defined output the next phase consumes. Entry points from the 2026-06-06 spec are preserved (full / known-page-count / count-only).

```dot
Phase 0  Frame & audience      → who/what + "will the customer see these files?" (default: yes)
Phase 1  Evidence: page count  → automated derivation + ANCHOR GUARD + rep confirmation   [§9]
Phase 2  Soft-input elicitation→ use case, geos, scenarios, environments (recommend-first) [§6]
Phase 3  Frequency advisor     → 5-layer ladder, anchor-high, keep/adjust/drop            [§5]
Phase 4  Model, price          → compute_scope.py → chat breakdown                        [§7]
Phase 5  Deliverables          → live model .xlsx + proposal .docx + internal .xlsx       [§8]
```

**Phase 0 — Frame & audience.** Customer, domains, and one new question up front: *"Will these files ever reach the customer?"* Default **yes** → customer-clean mode. This routes all internal context to the separate internal file (§8) regardless of later choices.

**Phase 1 — Evidence: the page count.** The Site Census derivation runs as today (automated; it is the *concrete evidence* the proposal rests on, so it is not a guessing game). New: the **anchor guard** (§9) runs before the number is allowed to propagate, and the rep explicitly confirms the anchor when a flag trips or confidence is MEDIUM/LOW. All derivation exhaust is captured for the internal file only.

**Phase 2 — Soft-input elicitation.** §6. Recommend-first walk-through of use case(s), geographies, scenarios, environments. Each "I don't know" applies a labeled default and adds an "assumption to verify" line.

**Phase 3 — Frequency advisor.** §5. The 5-layer ladder, opened at the aggressive default, walked layer by layer.

**Phase 4 — Model & price.** Assemble the inputs JSON and run `compute_scope.py` (verbatim numbers). Present the rep-facing breakdown (unchanged structure from the 2026-06-06 spec §8 chat output, plus the per-layer rationale).

**Phase 5 — Deliverables.** §8. Generate the three artifacts; report absolute paths.

---

## 5. The frequency advisor

The cadence model is unchanged under the hood — `cadence_layers: [{name, pct, runs_per_year}]`, additive, priced by `compute_scope.py`. What changes is the **advisory layer** on top: five canonical layers, each with a rationale, an anchor-high default %, and the page-slice it targets.

| Layer (`name`) | Cadence (`runs_per_year`) | Rationale (customer-facing "why") | Anchor-high default (`pct`) | Targets |
|---|---|---|---|---|
| Baseline inventory | Annual · 1 | "A full sweep so nothing on the site is invisible — your lay of the land." | **1.00** | Entire validated footprint |
| Inventory refresh | Quarterly · 4 | "Sites drift — new sections, campaigns, redirects. Quarterly keeps the full picture current." | **0.50** | Broad cross-section |
| Compliance / quality audit | Monthly · 12 | "Monthly audit of the meaningful body of the site for tag health & consent compliance." | **0.15** | Key templates & high-value sections |
| Release catch | Weekly · 52 | "Aligned to release cadence — catches tags/consent breaking shortly after a deploy." | **0.05** | Actively-changing / recently-released |
| Critical watch | Daily · 365 | "Crown-jewel pages — highest traffic, revenue, visibility. A failure here is most expensive, so check daily." | **0.01** | Top revenue / traffic / consent-critical |

**Blended:** Σ(`pct` × `runs_per_year`) = 1.0 + 2.0 + 1.8 + 2.6 + 3.65 = **≈ 11.05 scans per footprint page / year** (this is the cadence blend itself; the geo × scenario × environment multipliers scale it further). A deliberately strong anchor.

**Behavior.** The flow opens with all five layers populated at the default and walks them top to bottom. For each: state the rationale + default %, then the rep **keeps**, **adjusts the %**, or **drops** the layer (sets `pct = 0` / removes it). "I don't know" keeps the default and logs an assumption-to-verify. The aggressive anchor is intentional — the customer negotiates *down* from it, and in the live model (§7) they can do that themselves and watch the price fall.

**Customer visibility.** Each retained layer's rationale appears in the proposal's cadence table and the model's frequency rows (decision §14: "show the why"). The advisor framing is on the page, not just verbal.

**Reference doc.** A new `references/frequency-advisor.md` holds the ladder, the rationale strings, the anchor-high defaults, and "how to pull back" guidance (which layer to trim first under budget pressure). This is the seed map the flow reads — analogous to today's use-case profiles in `usage-methodology.md`, which this largely replaces for cadence.

---

## 6. Soft-input elicitation (recommend-first)

For each input the flow leads with an **aggressive best-practice recommendation + the reasoning**, pre-filled; the rep accepts / adjusts / says "I don't know" (keeps the recommendation, logs an assumption). This strengthens the existing "ask-the-customer map" (`usage-methodology.md`) into an interactive, anchored walk-through. Multipliers and defaults are unchanged from the 2026-06-06 spec §4.2 / §5.

| Input | Anchored recommendation + reasoning | "I don't know" default |
|---|---|---|
| Use case(s) | "Which of privacy/consent, analytics validation, accessibility — or several?" Drives which layers/scenarios matter. | Rep selects up front; if truly unknown, privacy (broadest scenario multiplier) |
| Geographies | "Which regulated regions need verified behavior? Anchor to all that plausibly apply." | 1 |
| Consent scenarios | "Which consent states matter? CCPA → 3, GDPR → 2…" | By regulation (CCPA 3 / GDPR 2 / else 1) |
| Environments | "Validate staging/pre-prod before release too?" → 1.5 | 1 (prod) |

Every defaulted value is flagged and appears in the **"Assumptions to verify with the customer"** list — which lives in the internal file and the rep chat, not the customer proposal.

---

## 7. The live Excel investment model (new technical heart)

The customer `.xlsx` becomes a **live calculator**, built by a new `build_model.py` using `openpyxl` (already a dependency). This honors the architecture principle: the **script renders** the workbook, and `compute_scope.py` remains the **source of truth** for every number we quote (§7.4).

### 7.1 Sheet: "Investment Model"

Two visually distinct zones:

```
INPUTS (editable, highlighted)                 OUTPUTS (formulas, shaded/locked)
─────────────────────────────────             ──────────────────────────────────
Validated pages         [  95,721 ]
Geographies             [       1 ]
Consent scenarios       [       3 ]            Pages per full sweep   =Pages*Geos*Scenarios*Env
Environments            [     1.0 ]
                                               Total annual page-scans=SUM(scans column)
Frequency ladder:                              Recommended investment =Pricing!Total
  Layer            % pages   runs/yr   pages each run        scans/yr
  Baseline invtry  [1.00 ]   [  1 ]    =Sweep*pct            =pages_each*runs
  Inventory rfrsh  [0.50 ]   [  4 ]    =Sweep*pct            =pages_each*runs
  Compliance audit [0.15 ]   [ 12 ]    =Sweep*pct            =pages_each*runs
  Release catch    [0.05 ]   [ 52 ]    =Sweep*pct            =pages_each*runs
  Critical watch   [0.01 ]   [365 ]    =Sweep*pct            =pages_each*runs
  (Why: one rationale line per row, customer-facing)
```

Change any input cell — drop daily to 0%, trim quarterly 0.50→0.25, add a geo — and pages-each-run, scans/yr, total, and price **recompute instantly in plain Excel**, no tooling, openable by the customer.

### 7.2 Graduated price as a live formula

A helper **"Pricing"** sheet holds the live tier table (from `fetch_pricing.py`), expressed as **band lower/upper bounds + rate**, one row per band, with a per-band cost formula referencing the Total Annual Scans cell:

```
band   lower(Lo)   upper(Hi)    rate     cost  =MAX(0, MIN($Total,Hi)-Lo) * rate
1      0           1,000        0.00     …
2      1,000       51,000       0.17     …
3      51,000      551,000      0.12     …
4      551,000     1,551,000    0.06     …
5      1,551,000   6,551,000    0.04     …
6      6,551,000   56,551,000   0.03     …
Recommended investment = SUM(cost column)
```

This **exactly mirrors** `compute_scope.graduated_price` (each tier `limit` is a band *width*; cumulative breakpoints 1k/51k/551k/1.551M/6.551M/56.551M). The per-band cost column doubles as the auditable "price by band" breakdown. Bands are embedded at generation time; if ObservePoint pricing changes, regenerate (same policy as today).

### 7.3 Other customer sheets (cleaned)
- **Scope detail** — per-property pages, `% of footprint`, and customer-fillable `Include? / Priority / Notes`. The cleaned successor to today's "Pages by Domain" — **no `Spiral?` column, no raw-URL math**.
- **Sample pages** — example URLs per property (unchanged; already clean).

### 7.4 Single source of truth (architecture-principle compliance)
`build_model.py` is fed the **same inputs object** that `compute_scope.py` consumes. The Python compute produces the numbers shown in chat and in the `.docx`; the workbook carries **formulas** for interactivity. A tested invariant (§12) asserts the workbook's formulas, evaluated at the anchor inputs, reproduce `compute_scope.compute()` exactly — so the doc, the chat, and the model can never disagree on the opening number. The model's interactivity is a *what-if rendering*, not a second source of truth.

> **openpyxl note:** openpyxl writes formula strings but does not evaluate them (cached values are blank until Excel opens the file). Nothing downstream reads computed values *from* the workbook — the canonical numbers come from `compute_scope.py` — so this is a non-issue for correctness, only for testing (§12 specifies how the formulas are verified).

---

## 8. Artifacts & the customer/internal split

Three files (decision §14: separate internal file, clean by construction). Output location unchanged: `~/Documents/ObservePoint Revenue/Scoping & Pricing/<Customer>/`.

| File | Audience | Contents |
|---|---|---|
| `<Customer> - proposal.docx` | Customer | Clean narrative snapshot. Footprint, what-we-monitor, cadence table **with the "why" per row**, recommended investment. **No** internal section, no internal terms. |
| `<Customer> - investment model.xlsx` | Customer | The live calculator (§7) + cleaned scope detail + sample pages. |
| `<Customer> - internal evidence.xlsx` | Rep only | Page-count derivation (raw/paths/patterns/spiral-adjust, recursion exclusions), census ID(s), crawl status, confidence + rationale, **assumptions-to-verify**, price-by-band, pricing-source stamp. Never forwarded. |

### 8.1 Vocabulary scrub (clean by construction)
A new `references/customer-vocabulary.md` maps internal → customer terms. An **expanded `_assert_clean`** checks **all** customer-facing strings (sheet names, headers, cell labels, prose), not just `monitoring_summary` as today. If a forbidden term reaches a customer cell, generation **fails loudly**.

| Internal term | Customer-facing |
|---|---|
| Site Census / census ID / crawl status | (omitted — "your website footprint"); details → internal file |
| `Spiral?`, raw URLs, defensible, reduced, discounted | "pages" (the clean number); reconciliation → internal file |
| anchor (recommended) | "estimated footprint" |
| confidence HIGH/MEDIUM/LOW | internal file only |
| recursion trap / collapsed_distinct | internal file only |

The internal-evidence file is exempt from the scrub (it is the place those terms belong).

---

## 9. Page-count anchor guard (adopt + wire in)

The recursion detector is **already built and committed** (`check_artifacts.py`: `is_recursion()`, `collapsed_distinct`, recursion-vs-artifact verdicts; SKILL.md Stage-1 step 5 branches; impersonation + 504 guidance — commit `c6ac67c`). This redesign does **not** rebuild it. It:

1. **Wires it into Phase 1** as an explicit gate: the flow runs the artifact/recursion check on the biggest host(s) before the anchor propagates, and **requires explicit rep confirmation** of the anchor when any flag trips or confidence is MEDIUM/LOW.
2. **Adds a rollup-dominance flag** (orchestration level, new): when a single domain is an outsized share of the rollup (the Gallagher trap domain was 93% of the total), surface it for confirmation. The committed detector operates on a URL *sample*; this dominance signal operates on the *rollup* and is complementary. Candidate implementation: a small check in `compute_scope.py` or a helper that flags `max(per_domain.defensible) / anchor > threshold`.
3. Carries the recursion exclusion + `collapsed_distinct` floor into the **internal-evidence** file's derivation record (preserving the `Σ per_domain.defensible == anchor` invariant from the 2026-06-06 spec §4.6 and the post-mortem Issue 4).

---

## 10. File-level change plan

```
skills/scope-calculator/
├── SKILL.md                              [REWORK]  phase-based advisor playbook; preserve Stage-1 guards from c6ac67c
├── references/
│   ├── frequency-advisor.md              [NEW]     5-layer ladder, rationales, anchor-high defaults, pull-back guidance
│   ├── customer-vocabulary.md            [NEW]     internal→customer term map (drives _assert_clean)
│   ├── usage-methodology.md              [REWORK]  point cadence at frequency-advisor.md; keep multipliers/ask-map
│   ├── deliverables-mapping.md           [REWORK]  three-file mapping (model / proposal / internal)
│   ├── site-census-methodology.md        [REUSE]   (already hardened in c6ac67c)
│   └── pricing-model.md                  [REUSE]
└── scripts/
    ├── compute_scope.py                  [REUSE/light]  optional rollup-dominance flag (§9.2)
    ├── build_model.py                    [NEW]     live customer workbook (formulas + clean scope/samples)
    ├── build_proposal.py                 [REWORK]  clean vocab, per-row "why", drop the [INTERNAL] section
    ├── build_internal_evidence.py        [NEW]     rep-only derivation file (was the internal half of the appendix)
    ├── build_evidence_appendix.py        [REMOVE/SPLIT] superseded by build_model.py + build_internal_evidence.py
    ├── check_artifacts.py                [REUSE]   (recursion detector from c6ac67c)
    ├── fetch_pricing.py / fetch_samples.py [REUSE]
    └── _assert_clean (in build_proposal/build_model) [REWORK]  cover all customer strings
```

**Architecture-principle check:** every number still computed by `compute_scope.py`; the new scripts only *render*. No LLM math, no LLM-maintained state. ✔

---

## 11. Implementation phasing

Sequenced so the AE's main complaints are fixed first.

- **Phase A — advisor + clean artifacts (the feedback fix):** SKILL.md flow rework, `frequency-advisor.md`, soft-input elicitation, `customer-vocabulary.md` + expanded `_assert_clean`, `build_proposal.py` rework, split `build_internal_evidence.py` out. Customer files become clean and the cadence becomes advised.
- **Phase B — the live model:** `build_model.py` (formulas + graduated-price formula + clean scope/samples) and its tests.
- **Phase C — anchor-guard wiring:** rollup-dominance flag + Phase-1 confirmation gate.

Each phase is independently shippable and testable.

---

## 12. Testing plan (TDD, per CLAUDE.md)

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q` (currently 166 passing).

**Deterministic scripts → pytest:**
- `build_model.py`: (a) input cells equal the inputs; (b) each output cell holds the expected formula string; (c) **invariant** — a small Python emulator of the exact Excel band/scan formulas reproduces `compute_scope.compute()` at the anchor **and** at perturbed scenarios (drop daily → -365×slice; halve quarterly), proving the live formulas match the engine. Clean-vocab assertion: no forbidden term in any customer cell.
- `build_internal_evidence.py`: per-domain derivation present; `Σ defensible == anchor` invariant; recursion-excluded host itemized with `collapsed_distinct`.
- `build_proposal.py`: no `[INTERNAL]` section; cadence rows carry the rationale; `_assert_clean` rejects a seeded forbidden term (RED test).
- Frequency advisor: the anchor-high default blends to ≈11×; dropping a layer reduces scans by exactly that layer's contribution.
- Rollup-dominance flag (§9.2): a one-domain-93% fixture trips it; a balanced fixture does not.

**SKILL.md behavior → subagent pressure tests (RED first):** the flow (a) elicits soft inputs recommend-first and accepts "I don't know" with a logged assumption; (b) opens cadence at the anchor-high ladder and lets layers be dropped; (c) produces clean customer files + a separate internal file; (d) confirms the anchor when the recursion/dominance flag trips; (e) never leaks an internal term into a customer artifact.

---

## 13. Open questions / risks

- **Rollup-dominance threshold** (§9.2): what share trips it (e.g. >50% from one host)? Tune with the Gallagher fixture; default proposed: flag the single largest host whenever it exceeds ~40% of the anchor.
- **Excel formula testing without a formula engine:** the emulator approach (§12) avoids a heavy `pycel`/`formulas` dependency. If fidelity concerns arise, revisit adding one as a dev-only test dep.
- **Model sheet protection:** lock the formula/output cells (leave inputs editable) so a customer doesn't overwrite a formula by accident — confirm desired during Phase B.
- **`usage-methodology.md` vs `frequency-advisor.md` overlap:** cadence content moves to the new file; keep multipliers + ask-map in usage-methodology to avoid duplication.

---

## 14. Resolved decisions (this session)

| # | Decision | Choice |
|---|---|---|
| Dynamism | static / live-xlsx / html / both | **Live Excel model** — workbook is the calculator; doc is a static snapshot |
| Audience | toggle / two-renders / separate internal file | **Separate internal file**, customer files clean by construction; default customer-safe |
| Elicitation | recommend-first / ask-first / conservative | **Recommend-first, anchor high** |
| Cadence anchor | aggressive / bolder / leaner | **Aggressive default** — Daily 1% / Weekly 5% / Monthly 15% / Quarterly 50% / Annual 100% (≈11× blended) |
| Rationale visibility | customer-facing / rep-only | **Customer-facing** "why" per cadence row |
| Anchor guard | skill-level / server-only / guard+consume | Resolved by the ported recursion detector (`c6ac67c`); this spec **adopts** it and adds a rollup-dominance flag + Phase-1 confirmation |

---

## 15. Relationship to the 2026-06-06 spec

That spec remains authoritative for: the calculation pipeline (§4), multipliers (§4.2), the graduated pricing model and fetch/fallback (§4.4–4.5), the per-domain evidence contract and sum-to-anchor invariant (§4.6), the optional buffer (§4.7), and Site Census admin discipline (§9). This spec overrides it on: interaction model (one-shot → advisor flow), cadence presentation (template → rationale ladder), and deliverables (two mixed files → live model + clean doc + separate internal file). Where they conflict, **this spec wins for those three areas only.**
