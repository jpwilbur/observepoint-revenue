# Pricing model — ObservePoint's live graduated pricing

Reference for the `size-and-price` skill. **The live ObservePoint pricing calculator is the sole
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
(Tier is classified on the **purchased** number — after buffer — since that's what's bought.)

## 3. Buffer (purchased vs predicted)

Optional `buffer_pct` (default 0). `purchased_scans = round(predicted_scans × (1 + buffer_pct))`.
**Pricing and tier classification use `purchased_scans`.** Always show BOTH numbers in the output,
e.g. "110,000 purchased = 100,000 predicted + 10% buffer." A buffer can push a deal across a tier
boundary — make that visible if it happens.

## 3b. Recommended contract — clean price ↔ exact scans

`compute_scope.py` exposes `scans_for_price(target_price, tiers)` (the inverse of `graduated_price`)
and emits `recommended_contract = {price, scans, exact_price}` on every `compute()`. It rounds the
anchor price to the nearest $1,000 and **back-solves the exact page-scans that price to it**, so the
two numbers a customer sees (price and page-scans) always reconcile in ObservePoint's published
calculator. Present the clean price and the exact scans together; show the precise modeled
pair (`predicted_scans` / `anchor.price.total`) in the internal/rep view. Never round one of the
pair independently — that produces figures the customer can't verify in the calculator.

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
