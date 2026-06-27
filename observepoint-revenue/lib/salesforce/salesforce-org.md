# ObservePoint Salesforce — canonical org map (read side)

How this plugin reads the ObservePoint SF org. The MODEL runs these queries via the
Salesforce MCP; scripts only digest the JSON. **Read-only** — no write queries here yet.

## Field hygiene (read before writing SOQL)
- `Account.Region__c` is labeled **"Region (OLD DONT USE)"** → use `Country_Region__c`
  (label "Region"), `Continental_Region__c`, or `Sub_Region__c`.
- Confirm the canonical ARR field (`ARR__c` vs `Calc_ARR__c`) via `getObjectSchema` admin
  guidance before trusting either. (Not used by find-accounts.)
- `getObjectSchema` returns admin-authored guidance — read it before constructing queries.

## Territories — `OP_Territories__c`
Only **AEs and ADMs** have territories. Accounts link via `Account.OP_Territory__c`.
Fields: `AE__c`, `ADM__c`, `CSM__c` (User refs), `Segment__c` (Enterprise/Corporate/Partner),
`World_Region__c`, `Sub_Region__c`, `Country__c`, `State__c`, `Name`/`Name__c`.

**Named query — a target's territory** (key on the target's *actual* role; never assume AE≡ADM):
```sql
SELECT Id, Name, Name__c, Segment__c, World_Region__c, Sub_Region__c,
       Country__c, State__c, AE__r.Name, ADM__r.Name, CSM__r.Name
FROM OP_Territories__c
WHERE AE__c = :targetUserId          -- or ADM__c = :targetUserId
```

**Named query — resolve a target user by email** (when the runner isn't the target):
```sql
SELECT Id, Name, Email FROM User WHERE Email = :email AND IsActive = true
```

## Accounts (overlap-guard)
`Account.Type` ∈ {Customer, Prospect, Previous Customer, Partner, Prospective Partner,
Previous Partner, Defunct}. `OwnerId`/`Owner.Name`, `Website`, `OP_Territory__c`, `Industry`.
**AEs can own named accounts outside their territory** → match on `OwnerId`, not just territory.

**Named query — match swept candidates to existing accounts** (domain-first):
```sql
SELECT Id, Name, Website, Type, OwnerId, Owner.Name, OP_Territory__c, Industry
FROM Account
WHERE Website IN (:candidateDomains)
```
For candidates with no website match, fall back to a name search:
```
FIND {"Acme*"} IN NAME FIELDS RETURNING Account(Id, Name, Website, Type, OwnerId, OP_Territory__c)
```

## Bridges (reserved for later items — NOT used by find-accounts)
- `Account.OP_Account_ID__c` / `OP_App_ID__c` → the ObservePoint platform account.
- Gong is synced into SF (`Gong__Gong_Call__c`, `Gong__Note__c`, `Gong__Gong_Scorecard__c`, …).
- `Product_Adoption_Whitespace__c` + `Account.OP_Product_Lines__c` for expansion.

## Renewals (revenue-insights — renewals-at-risk recipe)

Renewals live on **`Opportunity`** (confirmed live, read-only, 2026-06-26 via `getObjectSchema`).
Confirmed fields:
- `Renewal_Forecast__c` — picklist, **exactly** `['Undetermined', 'Will Not Renew', 'Will Renew']`
  (the three at-risk buckets; matches the proven report).
- `Renewable_ARR__c` — currency (the at-risk ARR).
- `CurrencyIsoCode` — picklist `['AUD','GBP','CAD','EUR','SGD','USD']` (multi-currency org →
  keep currencies separate; `currency.sum_by_currency`).
- `CloseDate` — date; `Renewal_Date__c` — date (renewal-specific).
- `Account.Name`, `Account.Health_Score__c`, `OwnerId`/`Owner.Name`.

**Account health** is **`Account.Health_Score__c`** — a restricted picklist populated by ChurnZero:
`1- Black / 2- Red / 3- Yellow / 4- Blue / 5- Green`. Normalized to a color token via
`health_token` (e.g. `"3- Yellow"` → `"yellow"`). **⚠️ The connector currently lacks field-level
Read on it (rev-ops must grant Read on `Account.Health_Score__c`); confirmed via a direct SOQL
returning INVALID_FIELD while sibling Account custom fields read fine.** The recipe and fixtures
are built and unit-tested; wire live when access is granted.

**Named query — renewals in a window (single SF gather; includes health):**
```sql
SELECT Account.Name, Account.Health_Score__c,
       Renewal_Forecast__c, Renewable_ARR__c, CurrencyIsoCode,
       CloseDate, Renewal_Date__c, Owner.Name
FROM Opportunity
WHERE Renewal_Forecast__c != null
  AND CloseDate >= :quarterStart AND CloseDate <= :quarterEnd
```
**FLS fallback:** if this SOQL returns `INVALID_FIELD` for `Account.Health_Score__c` (Read not yet
granted), drop that one field from the SELECT and re-run — the recipe runs health-less
(`health=None`; Undetermined rows carry zero risk-weighting) until rev-ops grants access.

**Normalized field map** (all from SF — single query, no Domo join):
`Account.Name`→`account`, `Account.Health_Score__c`→`health` (via `health_token`),
`Renewal_Forecast__c`→`status`, `Renewable_ARR__c`→`arr`, `CurrencyIsoCode`→`currency`,
`CloseDate`→`close_date`. The renewal *risk-weighting* (Undetermined: Red 0.25 / Yellow 0.50)
uses the SF-sourced health token — see `revenue-insights/references/metrics-canon.md`.

## Contract / subscription (consumption-pacing recipe)

Contracted page-scan allowances live on **`Subscription__c`** (confirmed fields, read-only).
Confirmed fields:
- `Account__r.Name` — the customer account name (lookup → Account).
- `Page_Scans_per_Month__c` — double; contracted page-scan allowance. **⚠️ Name implies a monthly rate, but consumption-pacing currently uses it as the total allowance over the contract window — verify the true unit with rev-ops before production use.**
- `Limit_Type__c` — picklist: `'Yearly'` | `'Monthly'`.
- `Status__c` — picklist; filter to `'Active'` (exclude Expired, etc.).
- `App_Id__c` — OP platform bridge (the OP account id).
- `Subscription_Start_Date__c` — date (contract window start).
- `Subscription_End_Date__c` — date (contract window end).
- `CurrencyIsoCode` — picklist (multi-currency org).

**Named query — active subscriptions:**
```sql
SELECT Account__r.Name, Page_Scans_per_Month__c, Limit_Type__c, Status__c,
       App_Id__c, Subscription_Start_Date__c, Subscription_End_Date__c
FROM Subscription__c
WHERE Status__c = 'Active'
```

**Normalized field map:** `Account__r.Name`→`account`, `Page_Scans_per_Month__c`→`contracted`,
`Subscription_Start_Date__c`→`start`, `Subscription_End_Date__c`→`end`.

**Usage (page scans consumed)** is NOT in SF — it comes from the OP platform via
`get_usage_overview` (returns formatted TEXT, not JSON). Parse with
`consumption_pacing.parse_usage_overview`. The recipe joins on account name.

## Pipeline + quota (revenue-insights — pipeline-coverage recipe)

Open opportunities and quota targets live in **`Opportunity`** and **`Quota__c`** respectively.
Pipeline coverage = open in-quarter pipeline ÷ quota for New/Expansion ACV types.
Gap = quota − Commit (open Commit bucket only; closed-won subtraction is a future enhancement).

**Named query — open opportunities in a fiscal quarter:**
```sql
SELECT Amount, CurrencyIsoCode, ForecastCategoryName, StageName, IsClosed, IsWon,
       CloseDate, Acquisition_Segment__c, Owner.Name
FROM Opportunity
WHERE IsClosed = false
  AND CloseDate >= :qStart AND CloseDate <= :qEnd
```

**Named query — quota rows for a fiscal quarter:**
```sql
SELECT Month_Quota__c, Month_Start__c, Type__c, Department__c, OwnerId, CurrencyIsoCode
FROM Quota__c
WHERE Month_Start__c >= :qStart AND Month_Start__c <= :qEnd
```

Filter `Quota__c` to `Type__c ∈ ('New ACV', 'New Logo ACV', 'Expansion ACV')` in the script —
other types (e.g. MQL) are excluded deterministically. Currencies stay separate; no FX conversion.
Closed-won opportunities are excluded from both open-pipeline totals and the gap calculation
(the gather query is `WHERE IsClosed = false`; gap = quota − Commit only).
