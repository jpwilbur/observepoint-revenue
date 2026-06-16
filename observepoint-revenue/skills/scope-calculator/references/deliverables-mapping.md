# Deliverables mapping — assembling the proposal, customer workbook & internal evidence

Three files are produced at Stage 3 — never just one or two. Use the **precise** anchor everywhere
(never a rounded value) — the same number must appear in pricing, the customer workbook, and the
proposal. The full `proposal.json` schema also lives in `scripts/build_proposal.py`'s docstring; this
file is the orchestration glue.

> **Cadence layers now carry a `why` field.** Every `{name, pct, runs_per_year}` layer from the
> frequency-advisor walk also carries `why` (the customer-facing rationale string from
> `frequency-advisor.md`). The `why` rides into both customer deliverables (cadence table in the
> proposal, Annual Usage Breakdown in the customer workbook) and is not used in math.

## Output 1 — Proposal (customer-facing, clean): `build_proposal.py <proposal.json> <out.docx>`

Clean customer snapshot: footprint, cadence table with per-row "why", recommended investment.
No `[INTERNAL]` section by construction. Agent-composed strings (monitoring_summary, cadence names,
why lines) are guard-checked via `customer_clean.py` — the generator rejects internal terms.

Assemble `proposal.json`:

- `page_count` ← Stage-1 `rollup` (`low/anchor/high`) — internal fields (`confidence`, `url_total`, `census_id`, `crawl_status`) are accepted-if-present but are NOT rendered to the customer doc; they go to the internal file.
- `consent_states` = `{count: <scenarios multiplier>, names: [Default/Opt-Out/GPC …]}`.
- `cadence_layers` ← Stage-2 `anchor.cadence_by_layer` verbatim (each entry must include `why`).
- `usage` = `{pages_per_sweep: anchor.use_case_pages, annual_scans: anchor.predicted_scans}`.
- `pricing` = `{recommended_price: recommended_contract.price, recommended_scans: recommended_contract.scans, range_low_price: range.low.price_total, range_high_price: range.high.price_total, pricing_source, modeled_scans: anchor.predicted_scans, modeled_price: anchor.price.total}` — the recommended pair is the **clean price ↔ exact scans** that reconcile in the calculator.
- plus `customer`, `prepared_by`, `date`, `use_case`, `domains`, `properties_note`, `regulations`, and a one-line `monitoring_summary` (NO internal terms — the generator rejects them).

## Output 2 — Customer workbook (customer-facing, clean): `build_evidence_appendix.py <perdomain.json> <out.xlsx>`

Clean scope detail + sample pages + Annual Usage Breakdown. No Spiral? column, no raw-URL math, no
census/crawl/confidence. Feed the Stage-1 `{rollup, per_domain}` (each domain with its `url_samples`)
PLUS a `usage` object so the **Annual Usage Breakdown** sheet renders:

```
usage = {
  consent_states: {count, names},            # e.g. 3, [Default, Opt-Out, GPC]
  pages_per_sweep: anchor.use_case_pages,
  annual_scans:    anchor.predicted_scans,
  recommended_price: recommended_contract.price,
  recommended_scans: recommended_contract.scans,
  cadence_layers:  anchor.cadence_by_layer,  # each entry must include why
}
```

> **Phase B note:** `build_model.py` (the live Excel investment model with formula cells) will supersede
> the customer workbook in Phase B. Until then, `build_evidence_appendix.py` is the customer `.xlsx`.

## Output 3 — Internal evidence (rep-only, NEVER sent): `build_internal_evidence.py <internal.json> <out.xlsx>`

The page-count derivation (census IDs, crawl status, raw/defensible/reduced per domain), spiral and
recursion notes, assumptions-to-verify, modeled-vs-contracted price, price-by-band, and the
rollup-dominance flag (spec §9.2 — one host is an outsized share of the anchor). This file is the
home for all internal context; it is never forwarded to the customer.

Assemble `internal.json`:

- `rollup` ← Stage-1 `rollup` in full (`spiral_adjusted_anchor`, `low`, `high`, `url_total`, `confidence`, `census_ids`, `crawl_status`).
- `per_domain` ← Stage-1 `per_domain[]` in full (including `raw_urls`, `discounted`, `spiral_flag`, `why` notes).
- `pricing` = `{price_by_band: anchor.price.breakdown, modeled_scans: anchor.predicted_scans, modeled_price: anchor.price.total, recommended_scans: recommended_contract.scans, recommended_price: recommended_contract.price, pricing_source}`.
- `internal` = `{assumptions: <assumptions-to-verify list>, implied_frequency: anchor.implied_blended_frequency}`.
- plus `customer`, `date`.
