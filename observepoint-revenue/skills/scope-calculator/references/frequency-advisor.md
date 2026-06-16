# Frequency advisor (the cadence ladder)

Cadence is proposed like an advisor, not "plopped." Open with all five layers at the anchor-high
default; walk the rep through each (keep / adjust % / drop). Every retained layer carries its
customer-facing **"why"** into the proposal and the model. The customer negotiates DOWN from the
anchor — in the live model they can do it themselves.

| Layer (`name`) | Cadence (`runs_per_year`) | The "why" (customer-facing) | Anchor-high default `pct` | Targets |
|---|---|---|---|---|
| Baseline inventory | Annual · 1 | A full sweep so nothing on the site is invisible — your lay of the land. | 100% | Entire footprint |
| Inventory refresh | Quarterly · 4 | Sites drift — new sections, campaigns, redirects. Quarterly keeps the full picture current. | 50% | Broad cross-section |
| Compliance / quality audit | Monthly · 12 | Monthly audit of the meaningful body of the site for tag health & consent compliance. | 15% | Key templates & high-value sections |
| Release catch | Weekly · 52 | Aligned to release cadence — catches tags/consent breaking shortly after a deploy. | 5% | Actively-changing / recently-released |
| Critical watch | Daily · 365 | Crown-jewel pages — highest traffic, revenue, visibility. A failure here is most expensive, so check daily. | 1% | Top revenue / traffic / consent-critical |

**Blend:** Σ(pct × runs_per_year) ≈ **11 scans/footprint-page/year** at the default (× geo × scenario
× environment multipliers). A deliberately strong anchor.

**Layers are additive** — a daily page is also in the annual baseline; `compute_scope.py` sums them.
Cadence layers feed `compute_scope.py` as `[{name, pct, runs_per_year, why}]` (the `why` rides along
to the deliverables; it is not used in math).

**Pulling back (when the customer can't fund the anchor):** trim in this order — (1) drop *Critical
watch* to fewer pages or remove it; (2) reduce *Release catch* %; (3) reduce *Inventory refresh* to
quarterly-of-a-smaller-slice; keep *Baseline inventory* (the floor — always recommend ≥1 full sweep/yr).

**"I don't know" →** keep the default for that layer and add an assumption-to-verify.
