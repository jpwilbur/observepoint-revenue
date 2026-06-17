# Deliverables mapping — the Scope of Work, the proposal & internal evidence

The default Stage-3 deliverable is ONE file: the **Scope of Work** workbook (`<Customer> - Scope of Work.xlsx`) in the customer folder. The proposal `.docx` and the internal-evidence `.xlsx` are produced **on request**, not up front. Use the **precise** anchor everywhere (never a rounded value) — the same `combined_pages` and `predicted_scans` must reconcile across the Scope of Work, the proposal (when built), and the internal evidence. The proposal is built by reading the **AE-edited** Scope of Work and recomputing — never assembled from the original Stage-2 anchor. The full `proposal.json` schema also lives in `scripts/build_proposal.py`'s docstring; this file is the orchestration glue.

> **Cadence layers carry `pct` and `why`; the buffer is additive.** Every layer from the frequency-advisor walk must include
> `{name, pct, runs_per_year, why}`. `pct` is required — each row's pages and scans derive from it
> (`pages_each = round(combined_pages × pct)`, `scans = round(combined_pages × pct × runs_per_year)`).
> The total predicted scans is the **sum over layers** plus one **additive buffer** pass:
> `predicted_scans = Σ(combined_pages × pct × runs_per_year) + round(combined_pages × buffer_pct)`.
> `pages` and `runs` keys are ignored if present. `why` rides into the Scope of Work (and into the proposal when it is built) and is not used in math.

> **`multipliers` is now required in `proposal.json`.** Supply `{geographies, scenarios, environments}`.
> The sweep table renders a Geographies row only when `geographies > 1`, and an Environments row only
> when `environments > 1` (or not 1). The consent-states row always renders using `scenarios` for the
> ×N and `consent_states.names` for the label. This makes the chain reconcile to `usage.combined_pages`
> for all multi-geo / multi-environment deals (e.g. Gilead: 848 × 3 geos × 3 consent = 7,632).

## Output — Proposal (customer-facing, clean, ON REQUEST): `build_proposal.py <proposal.json> <out.docx>`

Built **only when the rep asks**, by reading the **AE-edited Scope of Work** xlsx and **recomputing** the
footprint, scans and price, then writing the `.docx` into the customer folder. Clean customer snapshot:
footprint, cadence table with per-row "why", recommended investment. No `[INTERNAL]` section by
construction. Agent-composed strings (monitoring_summary, cadence names, why lines) are guard-checked
via `customer_clean.py` — the generator rejects internal terms.

Reconstruct `proposal.json` from the edited Scope of Work, then:

- `page_count` ← Stage-1 `rollup` (`low/anchor/high`) — internal fields (`confidence`, `url_total`, `census_id`, `crawl_status`) are accepted-if-present but are NOT rendered to the customer doc; they go to the internal file.
- `consent_states` = `{count: <scenarios multiplier>, names: [Default/Opt-Out/GPC …]}`.
- `multipliers` = `{geographies: <N>, scenarios: <N>, environments: <N>}` — all three required. Geographies and Environments rows render in the sweep table only when their value is >1; the consent-states row always renders.
- `cadence_layers` ← Stage-2 `anchor.cadence_by_layer` verbatim (each entry must include `pct` and `why`). `pages`/`runs` keys are ignored — the proposal derives them from `pct`.
- `usage` = `{combined_pages: anchor.combined_pages, predicted_scans: anchor.predicted_scans}` — `predicted_scans` is the layer sum plus the additive buffer.
- `pricing` = `{predicted_price: anchor.price.total, predicted_scans: anchor.predicted_scans, range_low_price: range.low.price_total, range_high_price: range.high.price_total, price_by_band: anchor.price.breakdown, pricing_source}` — the price key `build_proposal` reads is **`predicted_price`**; there is no back-solved recommended scans/price pair. **`pricing_source` is accepted-if-present but NOT rendered to the customer doc — the source stamp belongs in the internal-evidence file; include it there, not here.**
- plus `customer`, `prepared_by`, `date`, `use_case`, `domains`, `properties_note`, `regulations`, and a one-line `monitoring_summary` (NO internal terms — the generator rejects them).

## Output — Scope of Work workbook (customer-facing, live model, DEFAULT): `build_model.py <model.json> <out.xlsx>`

Live Scope of Work workbook: yellow INPUT/lever cells (per-domain Include? and Sample Size %, multipliers,
cadence %) with Excel formulas so the customer's page-scans and annual investment recompute automatically
when they adjust inputs. No Spiral? column, no raw-URL math, no census/crawl/confidence. Sheets are **not**
protected. Four sheets:

- **Scope Detail** — top-20 domains then a single bottom aggregate row; per-domain `Include?` (bool) and
  `Sample Size` (%) yellow levers. `Total Pages Found = SUMPRODUCT(Include?, Pages, Sample Size)`.
- **Scope of Work** — live calculator (combined pages from Scope Detail, geographies, consent scenarios,
  environments, cadence layers with % and runs/yr inputs, additive buffer %; scans-per-layer and total
  formula cells; investment cell linked to Pricing sheet).
- **Pricing** — graduated tier table with live price formula referencing the predicted page-scans.
- **Sample pages** — real example URLs per property (the largest by page count).

Assemble `model.json`:

```
{
  customer:        <string>,
  date?:           <string>,
  page_count: {low, anchor, high},            # precise anchor (e.g. 95721, not 96000)
  multipliers: {geographies, scenarios, environments},
  cadence_layers: [                           # 4 layers — drop a layer by pct=0, never remove it
    {name, why, pct, runs_per_year},          # Baseline inventory/Yearly/100%, High Priority/Weekly/1.5%,
  ],                                          #   Moderate Priority Pages/Monthly/7.5%, Low Priority Pages/Quarterly/20%
  buffer_pct:      <float>,                   # additive; default 0.15 (combined_pages × 15%, one pass)
  tiers:           <from fetch_pricing.py>,   # graduated tier array
  per_domain: [                               # from Stage-1 rollup; top-20 + aggregate on Scope Detail
    {hostname, defensible_pages, url_samples[]},
  ],
  rollup: {spiral_adjusted_anchor},           # per_domain[].defensible_pages must sum to this
}
```

- `page_count.anchor` / `rollup.spiral_adjusted_anchor` / proposal `page_count.anchor` MUST be the
  same precise number. Round only in display text, never in the input JSON.
- `cadence_layers` has 4 entries by default (the Scope of Work sheet's fixed rows); `buffer_pct` is the additive 15% term and is required, not optional.
- `tiers` comes from `fetch_pricing.py`; do not hardcode.

## Output — Internal evidence (rep-only, NEVER sent, ON REQUEST): `build_internal_evidence.py <internal.json> <out.xlsx>`

Pre-built into the hidden `<customer>/.work/` subfolder at Stage 3 and **moved up** to the customer folder
only when the rep asks. The page-count derivation (census IDs, crawl status, raw/defensible/reduced per
domain), spiral and recursion notes, assumptions-to-verify, the modeled price and its price-by-band
breakdown, and the rollup-dominance flag (spec §9.2 — one host is an outsized share of the anchor). This
file is the home for all internal context; it is never forwarded to the customer.

Assemble `internal.json`:

- `rollup` ← Stage-1 `rollup` in full (`spiral_adjusted_anchor`, `low`, `high`, `url_total`, `confidence`, `census_ids`, `crawl_status`).
- `per_domain` ← Stage-1 `per_domain[]` in full (including `raw_urls`, `discounted`, `spiral_flag`, `why` notes).
- `pricing` = `{price_by_band: anchor.price.breakdown, predicted_scans: anchor.predicted_scans, modeled_price: anchor.price.total, pricing_source}` — `predicted_scans` is the buffer-inclusive total and `modeled_price` is its exact graduated price. **`pricing_source` belongs here** (internal evidence), not in the customer-facing proposal.
- `internal` = `{assumptions: <assumptions-to-verify list>, implied_frequency: anchor.implied_blended_frequency}`.
- plus `customer`, `date`.
