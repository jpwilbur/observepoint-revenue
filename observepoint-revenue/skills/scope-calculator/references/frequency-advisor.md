# Frequency advisor (the cadence ladder)

Cadence is proposed like an advisor, not "plopped." Open with all four layers at the recommended
default plus the additive buffer; walk the rep through each (keep / adjust % / drop). Every retained
layer carries its customer-facing **"why"** into the proposal and the model. The recommendation is the
starting point — the rep and customer adjust the per-layer sample % (and the buffer) right in the live
model.

| Layer (`name`) | Cadence (`runs_per_year`) | The "why" (customer-facing) | Default `pct` | Targets |
|---|---|---|---|---|
| Baseline inventory | Yearly · 1 | A full sweep so nothing on the site is invisible — your lay of the land. | 100% | Entire footprint |
| High Priority | Weekly · 52 | Crown-jewel pages — highest traffic, revenue, consent exposure. A failure here is most expensive, so check weekly. | 1.5% | Top revenue / traffic / consent-critical |
| Moderate Priority Pages | Monthly · 12 | Monthly audit of the meaningful body of the site for tag health & consent compliance. | 7.5% | Key templates & high-value sections |
| Low Priority Pages | Quarterly · 4 | Sites drift — new sections, campaigns, redirects. A quarterly pass keeps the long tail current. | 20% | Broad cross-section / long tail |

**Buffer %** = **15%**, *additive*. It is **not** a cadence layer — it is one extra pass over the
sample-weighted footprint (`combined × 15%`, rounded), added on top of the layer scans to absorb growth,
re-crawls, and ad-hoc checks. The rep can raise or lower it in the model alongside the layer %s.

**How scans are computed:** `predicted_scans = Σ(combined × pct × runs_per_year)` over the four
layers, **plus** `round(combined × buffer%)` as one additive buffer pass — where `combined` is the
sample-weighted page count after the geo / scenario / environment multipliers. Price is the exact
`graduated_price(predicted_scans)`. At the default 4-layer + 15%-buffer blend this is a deliberately
strong, defensible recommendation the customer can dial down.

**Layers are additive** — a weekly High-Priority page is also counted in the yearly Baseline sweep;
`compute_scope.py` sums every layer and then adds the buffer pass on top. Cadence layers feed
`compute_scope.py` as `[{name, pct, runs_per_year, why}]` and the buffer feeds it as the separate
`buffer%` (the `why` rides along to the deliverables; it is not used in math).

**Pulling back (when the customer can't fund the recommendation):** trim in this order — (1) lower the
*Buffer %* (or drop it to 0); (2) drop *High Priority* to fewer pages or reduce its %; (3) reduce
*Moderate Priority Pages* %; (4) reduce *Low Priority Pages* to a smaller slice; keep *Baseline
inventory* (the floor — always recommend ≥1 full sweep/yr).

**"I don't know" →** keep the default for that layer and add an assumption-to-verify.
