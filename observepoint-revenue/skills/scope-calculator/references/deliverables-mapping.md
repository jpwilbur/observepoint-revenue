# Deliverables mapping — assembling the proposal, customer workbook & internal evidence

Three files are produced at Stage 3 — never just one or two. Use the **precise** anchor everywhere
(never a rounded value) — the same number must appear in pricing, the customer workbook, and the
proposal. The full `proposal.json` schema also lives in `scripts/build_proposal.py`'s docstring; this
file is the orchestration glue.

> **Cadence layers carry `pct` and `why`.** Every layer from the frequency-advisor walk must include
> `{name, pct, runs_per_year, why}`. `pct` is required — the proposal derives each row's pages and
> scans from it (`pages_each = round(pages_per_sweep × pct)`, `scans = round(pages_per_sweep × pct × runs_per_year)`).
> `pages` and `runs` keys are ignored if present. `why` rides into both customer deliverables and is not used in math.

> **`multipliers` is now required in `proposal.json`.** Supply `{geographies, scenarios, environments}`.
> The sweep table renders a Geographies row only when `geographies > 1`, and an Environments row only
> when `environments > 1` (or not 1). The consent-states row always renders using `scenarios` for the
> ×N and `consent_states.names` for the label. This makes the chain reconcile to `usage.pages_per_sweep`
> for all multi-geo / multi-environment deals (e.g. Gilead: 848 × 3 geos × 3 consent = 7,632).

## Output 1 — Proposal (customer-facing, clean): `build_proposal.py <proposal.json> <out.docx>`

Clean customer snapshot: footprint, cadence table with per-row "why", recommended investment.
No `[INTERNAL]` section by construction. Agent-composed strings (monitoring_summary, cadence names,
why lines) are guard-checked via `customer_clean.py` — the generator rejects internal terms.

Assemble `proposal.json`:

- `page_count` ← Stage-1 `rollup` (`low/anchor/high`) — internal fields (`confidence`, `url_total`, `census_id`, `crawl_status`) are accepted-if-present but are NOT rendered to the customer doc; they go to the internal file.
- `consent_states` = `{count: <scenarios multiplier>, names: [Default/Opt-Out/GPC …]}`.
- `multipliers` = `{geographies: <N>, scenarios: <N>, environments: <N>}` — all three required. Geographies and Environments rows render in the sweep table only when their value is >1; the consent-states row always renders.
- `cadence_layers` ← Stage-2 `anchor.cadence_by_layer` verbatim (each entry must include `pct` and `why`). `pages`/`runs` keys are ignored — the proposal derives them from `pct`.
- `usage` = `{pages_per_sweep: anchor.use_case_pages, annual_scans: anchor.predicted_scans}`.
- `pricing` = `{recommended_price: recommended_contract.price, recommended_scans: recommended_contract.scans, range_low_price: range.low.price_total, range_high_price: range.high.price_total, modeled_scans: anchor.predicted_scans, modeled_price: anchor.price.total, pricing_source}` — the recommended pair is the **clean price ↔ exact scans** that reconcile in the calculator. **`pricing_source` is accepted-if-present but NOT rendered to the customer doc — the source stamp belongs in the internal-evidence file (Output 3); include it there, not here.**
- plus `customer`, `prepared_by`, `date`, `use_case`, `domains`, `properties_note`, `regulations`, and a one-line `monitoring_summary` (NO internal terms — the generator rejects them).

## Output 2 — Customer workbook (customer-facing, live model): `build_model.py <model.json> <out.xlsx>`

Live Investment Model workbook: yellow INPUT cells (pages, multipliers, cadence %) with Excel formulas
so the customer's page-scans and annual investment recompute automatically when they adjust inputs.
No Spiral? column, no raw-URL math, no census/crawl/confidence. Four sheets:

- **Investment Model** — live calculator (validated pages, geographies, consent scenarios, environments,
  cadence layers with % and runs/yr inputs; scans-per-layer and total formula cells; investment cell
  linked to Pricing sheet).
- **Pricing** — graduated tier table with live price formula referencing Purchased page-scans.
- **Scope detail** — per-domain pages sorted desc with customer-fillable Include/Priority/Notes columns.
- **Sample pages** — real example URLs per property (the largest by page count).

Assemble `model.json`:

```
{
  customer:        <string>,
  date?:           <string>,
  page_count: {low, anchor, high},            # precise anchor (e.g. 95721, not 96000)
  multipliers: {geographies, scenarios, environments},
  cadence_layers: [                           # exactly 5 — drop a layer by pct=0, never remove it
    {name, why, pct, runs_per_year},
  ],
  buffer_pct?:     <float>,                   # default 0.0
  tiers:           <from fetch_pricing.py>,   # graduated tier array
  per_domain: [                               # from Stage-1 rollup
    {hostname, defensible_pages, url_samples[]},
  ],
  rollup: {spiral_adjusted_anchor},           # per_domain[].defensible_pages must sum to this
}
```

- `page_count.anchor` / `rollup.spiral_adjusted_anchor` / proposal `page_count.anchor` MUST be the
  same precise number. Round only in display text, never in the input JSON.
- `cadence_layers` must have exactly 5 entries (the Investment Model sheet has 5 fixed rows).
- `tiers` comes from `fetch_pricing.py`; do not hardcode.

## Output 3 — Internal evidence (rep-only, NEVER sent): `build_internal_evidence.py <internal.json> <out.xlsx>`

The page-count derivation (census IDs, crawl status, raw/defensible/reduced per domain), spiral and
recursion notes, assumptions-to-verify, modeled-vs-contracted price, price-by-band, and the
rollup-dominance flag (spec §9.2 — one host is an outsized share of the anchor). This file is the
home for all internal context; it is never forwarded to the customer.

Assemble `internal.json`:

- `rollup` ← Stage-1 `rollup` in full (`spiral_adjusted_anchor`, `low`, `high`, `url_total`, `confidence`, `census_ids`, `crawl_status`).
- `per_domain` ← Stage-1 `per_domain[]` in full (including `raw_urls`, `discounted`, `spiral_flag`, `why` notes).
- `pricing` = `{price_by_band: anchor.price.breakdown, modeled_scans: anchor.predicted_scans, modeled_price: anchor.price.total, recommended_scans: recommended_contract.scans, recommended_price: recommended_contract.price, pricing_source}` — **`pricing_source` belongs here** (internal evidence), not in the customer-facing proposal (Output 1).
- `internal` = `{assumptions: <assumptions-to-verify list>, implied_frequency: anchor.implied_blended_frequency}`.
- plus `customer`, `date`.
