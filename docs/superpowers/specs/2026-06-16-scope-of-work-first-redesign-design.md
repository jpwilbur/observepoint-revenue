# Scope-of-Work-first redesign — design

**Date:** 2026-06-16
**Status:** approved-in-brainstorm, pending spec review
**Supersedes parts of:** `2026-06-15-scope-calculator-advisor-flow-design.md` (the "produce all three deliverables" Stage 3, the 5-layer frequency-advisor default, the buffer-as-multiplier model)

## Motivation

The AE hand-rebuilt the Gallagher investment model into a **Scope of Work** workbook — reordered/renamed tabs, a domain-driven page total, per-domain in-scope + sample-size levers, a simpler priority-based cadence, an additive buffer, and a cleaner price line. It is the artifact they actually want to lead with. This redesign makes the tooling generate *that* workbook as the primary (and by default only) deliverable, changes the flow so the Scope of Work is produced first and alone, and relocates every non-customer artifact out of the customer folder.

Reference template: `~/Documents/ObservePoint Revenue/Scoping & Pricing/Gallagher/Gallagher - Scope of Work.xlsx`.

## Decisions (locked in brainstorm)

1. **Cadence model:** the template's model becomes the **new default for every deal** — 4 layers + an additive buffer row, with these anchor-high default percentages. Retire the old 5-layer ladder and the buffer-as-multiplier.
2. **Working files:** live in a hidden **`.work/`** subfolder inside the per-account customer folder.
3. **Proposal source:** the proposal **reads the AE-edited Scope of Work** and recomputes from its input cells (not the original answers, not Excel's cached values).
4. **Long-tail row:** top 20 domains listed individually, then a single aggregate row **at the bottom** of the list.
5. **No sheet protection:** Scope Detail and Scope of Work are freely editable; yellow fill only marks the levers. Integrity is enforced at **proposal-generation time** via validation, not by locking cells.
6. **Investment:** shown as the **exact graduated price of the predicted total** — no clean-$1,000-budget rounding, no separate "recommended contract" scans/price pair (this removes the confusing predicted-vs-purchased split).

## The new flow

### Phase 0 — removed
No more "will these files reach the customer?" prompt. The Scope of Work is clean by construction, always.

### Stage 1 — Derive the page count (unchanged)
Census → `{rollup, per_domain}` + anchor confirmation gate, exactly as today (methodology, artifact checks, dominant-host gate all unchanged). The per-domain pages now seed the Scope Detail tab. `per_domain[]` defaults to `Include in scope? = TRUE`, `Sample Size = 100%`.

### Stage 2 — Size + price (same shape, new defaults)
The recommend-first soft-input walk is unchanged (use case → multipliers → cadence), but:
- **Cadence default = the new ladder** (below). The advisor opens at the anchor-high default and the rep keeps/adjusts/drops layers.
- The **buffer is additive** (a cadence row), not a multiplier.

### Stage 3 — Build the Scope of Work (replaces "produce all three")
- Generate **only** `<Customer> - Scope of Work.xlsx` into the customer folder.
- Write working JSONs + a pre-built internal-evidence workbook to `.work/`.
- Close with guidance: *"Edit the Scope of Work — toggle domains, set sample sizes, tune the cadence levers. When it's in good shape, come back and ask for the clean proposal. (The internal evidence is also available on request.)"*

## Output / file behavior (no prompts; all default; rep-overridable)

```
~/Documents/ObservePoint Revenue/Scoping & Pricing/<Customer>/
├── <Customer> - Scope of Work.xlsx        ← the ONLY thing here by default
└── .work/                                  ← hidden working dir
    ├── scope_inputs.json
    ├── model.json
    ├── proposal.json
    ├── internal.json
    └── <Customer> - internal evidence.xlsx
```

- **On "give me the internal evidence":** move/copy `.work/<Customer> - internal evidence.xlsx` → customer folder.
- **On "build the proposal":** read the edited Scope of Work → validate integrity → recompute → write `<Customer> - proposal.docx` → customer folder.
- These happen by default with **no confirmation prompt**. The rep can override the base folder by saying so.

## The Scope of Work workbook (`build_model.py` rework)

Sheet order and names: **Scope Detail · Scope of Work · Pricing · Sample pages**. No sheet protection. Theme unchanged (Montserrat, #1E1E1E, brand-yellow inputs/levers, #F2F2F2 alt rows, logo).

### Scope Detail (first sheet)
Columns: **Property (domain) · Pages · % of total · Include in scope? · Sample Size · Notes**
- `% of total` = live `=B{n}/SUM($B$first:$B$last)`, format `0.0%`.
- `Include in scope?` = `TRUE` default, centered, yellow lever, boolean.
- `Sample Size` = `1` (100%) default, format `0%`, yellow lever.
- `Notes` = empty, editable.
- **Top 20 domains** by page count listed individually; the remaining domains collapse into one **bottom** row `"(K additional domains — long tail, aggregated)"` with their summed pages.

### Scope of Work (renamed from Investment Model)
- `Total Pages Found` (B6) = array formula `=SUMPRODUCT(--'Scope Detail'!D{f}:D{l}, 'Scope Detail'!B{f}:B{l}, 'Scope Detail'!E{f}:E{l})`.
- `Geographies` (B7), `Consent scenarios` (B8), `Environments` (B9) — yellow levers, number format `"× "0`.
- `Combined Page Total` (B10) = `=B6*B7*B8*B9`, plus a human-readable note cell `=TEXT(B6,"#,##0")&" × "&B7&" × "&B8&" × "&B9&" = "&TEXT(B10,"#,##0")`.
- **Monitoring cadence** table — columns: **Recommended Monitor Layer · Recommended Cadence · Why · % of combined pages · Runs/yr · Pages each run · Scans/yr**.
  - `Recommended Cadence` is the word form of Runs/yr (1→Yearly, 4→Quarterly, 12→Monthly, 52→Weekly, 365→Daily, else "N×/yr").
  - `% of combined pages` (yellow lever, `0.##%`) and `Runs/yr` (yellow lever) are inputs.
  - `Pages each run` = `=$B$10*D{n}`; `Scans/yr` = `=ROUND(F{n}*E{n},2)`.
- **Buffer row** (additive): `% = buffer%` (yellow lever, `0%`), `Pages each run = $B$10*D{buffer}`, `Scans/yr = =F{buffer}` (one pass).
- `Total annual page-scans (predicted)` = `=ROUND(SUM(G{first}:G{buffer}),0)` (includes the buffer row). **No "Purchased page-scans" row.**
- `Recommended investment / year (USD)` = `='Pricing'!E{total}` (brand-yellow highlight).
- Footer note: "Yellow cells are editable — change them and the totals/price update automatically."

### Pricing
Graduated-tier mirror, unchanged math, with two updates: the cost column references `'Scope of Work'!$G${total}` (the predicted total) and the sheet name reference is "Scope of Work". Bands/rates derive from `data['tiers']` (cumulative widths; last Hi = `10**12`).

### Sample pages
~5 real example URLs per top property, grouped by domain (unchanged in spirit).

### Default cadence ladder (the new anchor-high seed)
| Layer | Recommended Cadence | Runs/yr | % of combined | Why (customer-facing) |
|---|---|---|---|---|
| Baseline inventory | Yearly | 1 | 100% | A full sweep so nothing on the site is invisible — your lay of the land. |
| High Priority | Weekly | 52 | 1.5% | Aligned to release cadence — catches tags/consent breaking shortly after a deploy. |
| Moderate Priority Pages | Monthly | 12 | 7.5% | Monthly audit of the meaningful body of the site for tag health & consent compliance. |
| Low Priority Pages | Quarterly | 4 | 20% | A quarterly sweep of the long tail — keeps low-traffic pages from becoming blind spots. |
| Buffer % | — | (additive ×1) | 15% | Ad-hoc testing and projects regularly push scanning past the scheduled monitoring. |

## Engine change (`compute_scope.py`)

- **Total Pages Found** derives from `per_domain` with `include`/`sample_size`: `base = Σ(include ? pages × sample : 0)`. Defaults all-in at 100% (so `base == anchor` when untouched).
- **Buffer becomes additive:** `buffer_scans = round(combined × buffer_pct)`; `predicted = Σ(layer: combined × pct × runs) + buffer_scans`.
- **Investment = `graduated_price(predicted)`** exactly. Remove `apply_buffer`, `purchased_scans`, the `recommended_contract` clean-budget rounding, and the predicted-vs-purchased distinction.
- The emitted object still carries the authoritative `multipliers` block and per-layer breakdown for downstream consumers.
- New default cadence ladder lives in `frequency-advisor.md` and seeds Stage 2.

## Proposal from the edited spreadsheet (new `read_scope_of_work.py`)

A small reader parses the **input cells** of `<Customer> - Scope of Work.xlsx`:
- Scope Detail: per-row `pages`, `include` (bool), `sample_size` (%), with the bottom aggregate row.
- Scope of Work: `geographies`, `scenarios`, `environments`, each cadence layer's `pct`/`runs`, `buffer%`.

It feeds these to `compute_scope` and builds `proposal.json` → `build_proposal.py`. Recomputing from inputs (rather than trusting cached formula values) keeps it deterministic and Excel-recalc-independent.

### Integrity validation (called out to the rep, not silently absorbed)
Because the sheets are unprotected, the reader **validates before building** and reports any problem in plain language instead of producing a wrong proposal:
- **Required sheets present** (Scope Detail, Scope of Work, Pricing).
- **Formula cells intact** — the derived cells still hold their expected formulas (Total Pages SUMPRODUCT; Combined `=B6*B7*B8*B9`; each `Pages each run`/`Scans/yr`; the predicted-total SUM; the Pricing graduated cost column and total). If a formula cell was overwritten with a literal or a different formula, flag it.
- **Inputs valid** — pages ≥ 0; Include? boolean; Sample Size in (0, 1]; multipliers ≥ 1; cadence % ≥ 0; runs ≥ 0; buffer ≥ 0.
- **Structure intact** — expected header rows/columns present; no required rows deleted.
- **Reconciliation** — if Excel cached values are present (`data_only`), recomputed totals must match within tolerance; warn on mismatch.

On any violation the reader **exits non-zero with an itemized, friendly message** ("the Scope of Work has changes I can't safely turn into a proposal: …") and builds nothing. The orchestrator surfaces the list to the rep; the proposal is built only after the rep fixes the workbook or explicitly says to proceed anyway. A reconciliation-only mismatch (cached vs recomputed) is a **warning**, not a hard stop. Never silently produce a proposal from a tampered workbook.

`build_proposal.py` §3 is reworked to mirror the new model (Total Pages Found → ×multipliers → Combined → cadence incl. buffer → exact investment); the §4 recommended-contract pair is removed. The existing clean-by-construction guard and the reconciliation guard remain as defense-in-depth.

## Retired

- Stage 3 "produce all three" rule; the Phase-0 audience question.
- Buffer-as-multiplier; `purchased_scans`; `recommended_contract` clean-budget rounding.
- 5-layer frequency-advisor default ladder (replaced by the 4-layer + buffer ladder).
- Sheet protection on the workbook.

## Testing

- `build_model` tests reworked for: sheet order/names, Scope Detail columns + bottom aggregate, SUMPRODUCT total, `× ` multiplier inputs, Recommended Cadence word column, additive buffer row, predicted-total SUM incl. buffer, investment = Pricing total, no protection.
- `compute_scope` tests for the additive-buffer model and Total-Pages-Found derivation; remove tests for retired behavior.
- **Emulator-vs-engine invariant** kept: a dependency-free Python emulation of the workbook formulas equals `compute_scope` at the anchor and under perturbations.
- **Round-trip test:** build SoW from a fixture → `read_scope_of_work` → recomputed numbers equal the fixture's.
- **Integrity-validator tests:** tampered formula / deleted row / out-of-range input each produce a clear flagged message; a clean edit (changed input only) passes.
- Update `frequency-advisor.md`, `deliverables-mapping.md`, `usage-methodology.md`, SKILL.md, README, CLAUDE.md to the new model and flow.

## Suggested implementation phasing

1. **Engine** — `compute_scope.py` additive-buffer model + Total-Pages-Found derivation; tests.
2. **Workbook** — `build_model.py` rework to the Scope of Work layout; emulator-vs-engine invariant + layout tests.
3. **Flow + outputs** — SKILL.md Scope-of-Work-first flow, `.work/` relocation, closing guidance; references/docs.
4. **Proposal-from-xlsx** — `read_scope_of_work.py` (parse + integrity validation + reconcile) → reworked `build_proposal.py` §3; round-trip + validator tests.

## Open / minor (decided, not blocking)

- Keep the script filename `build_model.py` (deliverable/tab labelled "Scope of Work") to limit churn; revisit a rename later.
- Internal-evidence workbook is pre-built into `.work/` during the default run so "give me the internal evidence" is an instant move.
