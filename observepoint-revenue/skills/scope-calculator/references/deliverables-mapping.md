# Deliverables mapping — assembling the proposal & evidence inputs

How to map the Stage-1 `{rollup, per_domain}` and the Stage-2 `compute_scope.py` output into the two
script inputs. The full `proposal.json` schema also lives in `scripts/build_proposal.py`'s docstring;
this file is the orchestration glue. Use the **precise** anchor everywhere (never a rounded value) —
the same number must appear in pricing, the appendix, and the proposal.

## Evidence workbook — `build_evidence_appendix.py <perdomain.json> <out.xlsx>`

Feed the Stage-1 `{rollup, per_domain}` (each domain with its `url_samples`) PLUS a `usage` object so
the **Annual Usage Breakdown** sheet renders:

```
usage = {
  consent_states: {count, names},            # e.g. 3, [Default, Opt-Out, GPC]
  pages_per_sweep: anchor.use_case_pages,
  annual_scans:    anchor.predicted_scans,
  recommended_price: recommended_contract.price,
  recommended_scans: recommended_contract.scans,
  cadence_layers:  anchor.cadence_by_layer,
}
```

## Proposal — `build_proposal.py <proposal.json> <out.docx>`

A comprehensive, rep-first ObservePoint-themed doc that SHOWS the full derivation and ends with a
strippable `[INTERNAL — REMOVE BEFORE SENDING]` section. Assemble `proposal.json`:

- `page_count` ← Stage-1 `rollup` (`low/anchor/high/confidence/url_total/defensible/discounted/census_id/crawl_status`) + `spiral_note` (the discount-transparency line).
- `consent_states` = `{count: <scenarios multiplier>, names: [Default/Opt-Out/GPC …]}`.
- `cadence_layers` ← Stage-2 `anchor.cadence_by_layer` verbatim.
- `usage` = `{pages_per_sweep: anchor.use_case_pages, annual_scans: anchor.predicted_scans}`.
- `pricing` = `{recommended_price: recommended_contract.price, recommended_scans: recommended_contract.scans, range_low_price: range.low.price_total, range_high_price: range.high.price_total, price_by_band: anchor.price.breakdown, pricing_source, modeled_scans: anchor.predicted_scans, modeled_price: anchor.price.total}` — the recommended pair is the **clean price ↔ exact scans** that reconcile in the calculator.
- `internal` = `{assumptions: <assumptions-to-verify list>, implied_frequency: anchor.implied_blended_frequency, thresholds_swept}`.
- plus `customer`, `prepared_by`, `date`, `use_case`, `domains`, `properties_note`, `regulations`, and a one-line `monitoring_summary` (NO internal terms — the generator rejects them).
