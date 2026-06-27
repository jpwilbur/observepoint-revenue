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
