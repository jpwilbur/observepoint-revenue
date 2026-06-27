# Revenue metrics canon (revenue-insights)

The encoded methodology so every report computes a metric the same way. The MODEL gathers
(SF/Domo/OP MCP) and judges; deterministic scripts compute. Read-only.

## Cross-cutting rules
- **Currency:** never fabricate FX. Sum each currency separately (`currency.sum_by_currency`);
  show native (`currency.format_money`). Cross-currency totals only when Domo supplies an FX
  rate (not assumed in Phase 1).
- **Fiscal periods:** `periods.fiscal_quarter`, FY starts month 2 (Feb) — FY labeled by its
  start calendar year (Feb 2026 → FY26). Confirmed in Plan 1.
- **Source of truth per metric:** SF = live deal-level; Domo = curated/aggregate; OP = usage.
  When SF and Domo disagree, show both labeled — never silently pick.

## ARR / NRR bridge (arr-nrr-bridge)

The board-altitude view: how ARR moved during the fiscal quarter and what the retention rates are.

- **Waterfall:** Starting ARR → + New logo → + Expansion → − Contraction → − Churn → Ending ARR.
  All components are **USD, FX-normalized** — Domo pre-computes them on the `arr scorecard metrics
  ALL SUBSCRIPTIONS` dataset; this engine does **not** recompute FX.
- **NRR / GRR** are read directly from Domo's pre-computed fields
  `quarterly_net_revenue_retention_rate` and `quarterly_gross_revenue_retention_rate` on the
  **quarter-ending month row** (`isFiscalQuarterEndingMonth == 1`). If no such row exists, the last
  row in the quarter is used.
- **Expansion** = `expansion_arr_usd` + `upsell_arr_usd` (summed across all monthly rows).
- **Contraction** = `downsell_arr_usd` (summed); **Churn** = `churn_arr_usd` (summed).
- **Net New ARR** = New logo + Expansion − Contraction − Churn (derived; not a Domo field).
- Quarter selection defaults to the dataset's own `current_fiscal_year` / `current_fiscal_quarter`
  stamps; override via `fy_year` / `fy_quarter` kwargs.

## Pipeline coverage (pipeline-coverage)

The VP-Sales-altitude view: how much open pipeline stands behind the quarter's quota, and where
deals sit in the forecast-category ladder.

- **Pipeline coverage** = open in-quarter pipeline ÷ quota for `Type__c ∈ ('New ACV', 'New Logo
  ACV', 'Expansion ACV')`. Currencies kept separate; no FX conversion. A coverage ratio below 3x
  is typically considered thin for a quarter still in progress.
- **Quota** = sum of `Month_Quota__c` from `Quota__c` where `Month_Start__c` falls within the
  fiscal quarter and `Type__c` is one of the target types. MQL and other non-pipeline types are
  excluded deterministically.
- **Open pipeline** = `Opportunity.Amount` where `IsClosed = false` and `CloseDate` is in the
  fiscal quarter. Closed-won deals are excluded from open pipeline but included in gap calculation.
- **Forecast pacing ladder** (in priority order): Commit / Expect / Best Case / Pipeline / Omitted.
  Each bucket = sum of `Amount` for open opps in that `ForecastCategoryName`.
- **Gap to quota** = `max(0, quota − Commit − closed_won_in_quarter)`. Commit (open) plus
  already-closed-won ARR represents the most conservative "booked + highly likely" view against
  quota; the gap is what remains to be covered.
- **Source:** SF `Opportunity` (open opps) + `Quota__c` (quota targets). Both gathered by the
  model via MCP; `pipeline_coverage.py` computes deterministically on the JSON.

## Renewals (renewals-at-risk)
- **Renewable ARR** = `Renewable_ARR__c` on the SF renewal Opportunity (Plan 1 schema).
- **Forecast buckets** from `Renewal_Forecast__c`: Will Renew / Undetermined / Will Not Renew.
- **Will Not Renew** = confirmed churn (at-risk ARR booked as lost).
- **Account health** is NOT in SF — it is a **Domo** field `account_health_score` (string → color
  token: green/yellow/red/blue/black), joined onto SF renewals by account name. See
  `lib/domo/domo-datasets.md` → "Account health" and `lib/salesforce/salesforce-org.md` → "Renewals".
- **Undetermined risk-weighting** = Renewable ARR × health weight: **Red 0.25, Yellow 0.50**
  (the gross-renewal methodology; matches the proven report). Other states are not in the
  undetermined bucket, so they carry no undetermined weight.
- **Auto-caveat:** any Will-Not-Renew row whose joined health is Green is flagged "verify"
  (status/health contradiction).
- **Known limitation:** `health_token` matches a color word by substring (the documented
  `account_health_score` is a clean 5-state color string). If that field ever carries free-text
  status phrases, tighten the match to whole words — it's the join helper recipes reuse.

## Consumption pacing (consumption-pacing)

The CSM-altitude view: is each account consuming its OP page-scan allowance at the expected
rate given how far through its contract window it is?

- **Pace** = `used ÷ (contracted × period_fraction)`.
  - `used` = Audit Pages consumed, from OP `get_usage_overview` text (parsed by
    `parse_usage_overview`; strips commas from the formatted integer).
  - `contracted` = `Page_Scans_per_Month__c` on SF `Subscription__c` (Active only). (⚠️ unit unverified — used as the full-window allowance; confirm monthly-vs-window with rev-ops).
  - `period_fraction` = elapsed days ÷ total contract days, clamped to [0, 1], from
    `Subscription_Start_Date__c` / `Subscription_End_Date__c`.
- **Bands (±10%):** pace > 1.10 → "over"; pace < 0.90 → "under"; else "on".
- **Unknown:** contracted, period_fraction, or used missing → status "unknown" (no math).
- **Page scans only** — no currency, no $. Each account is independent (no cross-account total).
- **Source:** contracted allowance from SF `Subscription__c.Page_Scans_per_Month__c`;
  usage from OP `get_usage_overview` (formatted text, not JSON — needs `parse_usage_overview`).
- **Compute script:** `skills/revenue-insights/scripts/consumption_pacing.py`.
