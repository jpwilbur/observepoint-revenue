# Pricing model — ObservePoint's live graduated pricing

Reference for scope-calculator's **usage + price stage** (Stage 2). **The live ObservePoint pricing calculator is the sole
source of truth. There is no in-skill price override** — if a rep needs bespoke/negotiated pricing,
they take this skill's output and adjust it themselves (uncommon).

## 1. Graduated audit page-scan tiers

Pricing is **graduated/marginal**: each band's width is priced at its own rate, then summed.

| Band | Width (pages) | Covers pages | Rate / page |
|---|---|---|---|
| 1 | first 1,000 | 1 – 1,000 | $0.00 (free) |
| 2 | next 50,000 | 1,001 – 51,000 | $0.17 |
| 3 | next 500,000 | 51,001 – 551,000 | $0.12 |
| 4 | next 1,000,000 | 551,001 – 1,551,000 | $0.06 |
| 5 | next 5,000,000 | 1,551,001 – 6,551,000 | $0.04 |
| 6 | next 50,000,000 | 6,551,001 – 56,551,000 | $0.03 |

(The "Covers pages" column is cumulative — e.g. the 500,001st page sits in band 3 at $0.12.)

`compute_scope.py` applies this exactly: `Σ over bands of min(band_width, remaining) × rate`. Example:
1,664,256 scans → 0 + 50,000×.17 + 500,000×.12 + 1,000,000×.06 + 113,256×.04 = **$133,030.24**
(avg ≈ $0.0799/page).

## 2. Tier classifier

`annual_scans < 600,000` → **starter**; `≤ 6,000,000` → **professional**; else **enterprise**.
(Tier is classified on `predicted_scans` — the single sized total, buffer already folded in — since that's what's bought.)

## 3. Buffer (additive)

The buffer is **additive**, not a multiplier. A single extra pass over `combined_pages` is added on
top of the cadence layers: `buffer_scans = round(combined_pages × buffer_pct)`, and
`predicted_scans = Σ over layers (combined_pages × layer_pct × runs) + buffer_scans`. Default
`buffer_pct = 15%`. There is no separate "purchased" number — `predicted_scans` is the one sized
total, and **both pricing and tier classification use `predicted_scans`** via the exact
`graduated_price(predicted_scans)`. Show the buffer as a contributing line in the scope breakdown
(e.g. "Buffer 15% → +N scans") so the rep can see what it adds, but do not present a second
grand total.

## 4. Journeys (v1)

Journeys (funnel/login runs) are a separate ObservePoint meter, priced on flat tiers (≤100 free,
≤1,500 $2.5K, ≤6,000 $5K, ≤36,000 $15K, else $30K). **v1 default = free tier ($0), not metered.** Note
it in output; do not scope it. (Future extension.)

## 5. Live fetch + fallback

`scripts/fetch_pricing.py` fetches the live tiers from ObservePoint's public pricing-app JS bundle
(`https://app.observepoint.com/www-pricing/main.js`), validates them, and returns `{tiers, source}`.

- Pass BOTH `tiers` and `source` straight into `compute_scope.py`'s inputs (it accepts `source` as an
  alias for `pricing_source`).
- If `source` starts with **`"fallback"`**, the live fetch failed and the baked last-known-good table
  was used — **the skill MUST surface a visible "pricing may be stale, verify/refresh" warning** in the
  rep-facing output.
- Always show the `source` stamp in the rep-facing breakdown (internal only — it must NOT appear in the
  customer proposal).

## 6. Refresh / verify path

The baked fallback lives in `compute_scope.py` as `BAKED_TIERS` + `BAKED_AS_OF`. To verify or refresh:
run `python3 scripts/fetch_pricing.py` and compare; if the live table has changed, update `BAKED_TIERS`
and `BAKED_AS_OF` in `compute_scope.py` so the fallback stays current.

## 7. Hard rules

- Live calculator is the sole source of truth; **no in-skill override / no flat-rate shortcuts** (the
  old spreadsheet's $0.135/page is dead — ignore it).
- **Never do LLM arithmetic** — `fetch_pricing.py` + `compute_scope.py` compute the numbers; the skill
  orchestrates and presents.
