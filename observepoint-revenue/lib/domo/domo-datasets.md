# lib/domo — canonical Domo dataset map (read side) — library, not a skill

How the revenue-insights engine reads ObservePoint's Domo warehouse. The MODEL runs these
queries via the Domo MCP; `domo_io.py` only digests the returned JSON. **Read-only.** Referenced
by path (no `SKILL.md`). Discovered live, read-only, 2026-06-26.

## How the Domo MCP behaves (read before writing a query)

- **`DomoSqlQueryTool` is natural-language + RAG-routed, not raw SQL.** It takes a `userQuestion`
  and `dataSourceIds`, generates SQL, and returns results. **It picks "the most relevant dataset"
  from the question — passing a single `dataSourceId` does NOT reliably force that dataset.** A
  generic question ("return sample rows") routed to the ARR scorecard regardless of the id passed.
  **To target a dataset, name it in the question and list the columns you want**, e.g.
  *"From the \"Master - Opportunities\" dataset only, return … showing amount, CloseDate, Type."*
- **It returns only the columns its generated SQL selects** — not necessarily every column. Ask
  for the specific columns the recipe needs.
- **Result envelope = a plain JSON array of row dicts**: `[{"col": val, ...}, ...]`. No
  `{rows,columns}` wrapper. `domo_io.parse_query_result` handles this (list-of-dicts passthrough).
- **Empty / error** comes back as a non-array message (e.g. *"0 rows were returned"*), not an
  array — `domo_io` must treat a non-list/empty result as "no rows", and callers fall back cleanly.
- Numeric blanks arrive as empty string `""` (not null) for many computed columns — coerce with
  `domo_io.coerce_number` (→ None).

## Fiscal calendar (CONFIRMED 2026-06-26)

- **Fiscal year starts February** (month 2). The ARR scorecard carries `fiscal_year`,
  `fiscal_quarter`, `fiscal_period` (e.g. `"2026-Q2"`), `fiscal_month_num`,
  `isFiscalQuarterEndingMonth` (April row = 1 → Q1 = Feb–Apr), and the live anchors
  `current_fiscal_year` (2026), `current_fiscal_quarter` (2), `current_fiscal_quarter_end_date`
  (`2026-07-31`), `previous_fiscal_quarter_end_date` (`2026-04-30`).
- FY is **labeled by its start calendar year** (the FY containing today, started Feb 2026, is
  `current_fiscal_year` 2026 → "FY26"). This matches `periods.fiscal_quarter(date, fy_start_month=2)`
  and the proven report's "Q2 FY26 = May 1–Jul 31". **The engine should prefer the dataset's own
  `current_fiscal_*` / `fiscal_period` columns when present** rather than recomputing.

## Currency / FX (CONFIRMED)

- The ARR scorecard provides **FX-normalized USD columns** (`arr_usd_starting`, `*_arr_usd`,
  `fxUpsell_arr_usd`, `fxDownsell_arr_usd`, …) alongside native (`arr_starting`). **Domo already
  applies FX** for board metrics → the arr-nrr-bridge uses the `_usd` columns directly; no
  in-engine FX fabrication needed. (Deal-level native-currency handling stays in the SF recipes via
  `currency.sum_by_currency`.)

## Datasets (the ones that feed the seed recipes)

| Dataset | id | Authoritative for | Recipe |
|---|---|---|---|
| **arr scorecard metrics ALL SUBSCRIPTIONS** | `0f19647e-cc94-4aa0-89c4-dd655ab18b08` | ARR movement, NRR/GRR, logo retention, the full bridge | arr-nrr-bridge (Plan 3) |
| **Master - Opportunities** | `9a3c11e0-5252-4b62-860a-7a37aba70818` | Pipeline / bookings (Domo copy of SF opps) | pipeline-coverage (Plan 3) |
| **Master - Booking Metrics** | `0e5b5da5-2439-42dc-9a1f-de72300cf3b6` | Bookings roll-ups | pipeline-coverage / finance |
| **Actual vs Plan by quarter** | `b244b7e1-0cef-4231-98c7-53abc941f488` | **Plan / target (quota candidate)** | pipeline-coverage (Plan 3) |
| **Corporate Scorecard** | `9e16f3b8-99a7-47be-a712-fe123ac5c5b9` | Company plan/target metrics (quota candidate) | board / pipeline-coverage |
| **Gong Forecast History** | `f1e1b2fc-42a8-479c-a3fd-762bdeaefb55` | Forecast-category history | pipeline-coverage |
| **Master - Renewal Opportunities** | `789f9dcd-e5c0-4c59-8c09-82b6eb0e3aa7` | Renewal opps (Domo copy; cross-check the SF-sourced renewals recipe) | renewals cross-check |
| **FACT TABLE - Account** | `62d467ad-0ed7-49be-b16e-8170dfecd931` | Account fact roll-up | consumption-pacing / CSM |
| **APP Data: Audits, Journeys and Rules by Account** | `22de7bc7-fc3f-4b5c-8440-29ae91780e93` | ObservePoint platform usage by account | consumption-pacing (Plan 3) |
| **Master - Whitespace Google Sheet** | `f3f416e3-5aad-4545-a6d5-a122d6762828` | Expansion whitespace | expansion radar (future) |

### Confirmed columns

**arr scorecard metrics ALL SUBSCRIPTIONS** (the bridge — USD columns are FX-normalized):
`start_of_month`, `arr_usd_starting`, `new_logo_arr_usd`, `expansion_arr_usd`, `upsell_arr_usd`,
`downsell_arr_usd`, `churn_arr_usd`, `lost_arr_usd`, `attrition_arr_usd`, `ending_arr_usd_carryover`,
`ending_arr_usd_from_trx`, `gross_retention_rate`, `net_retention_rate`, `logo_retention_rate`,
`quarterly_gross_revenue_retention_rate`, `quarterly_net_revenue_retention_rate`,
`logo_count_starting`, `ending_logo_count`, `churn_count`, `new_count`, `fiscal_year`,
`fiscal_quarter`, `fiscal_period`, `fiscal_month_num`, `isFiscalQuarterEndingMonth`,
`current_fiscal_year`, `current_fiscal_quarter`, `current_fiscal_quarter_end_date`,
`previous_fiscal_quarter_end_date`. (Many rate/cost/ttm columns are `""` when not yet computed.)

**Master - Opportunities** (confirmed subset): `amount`, `CloseDate`, `Type`
(New Business / Existing Business), `Acquisition_Segment__c`, `IsWon` (**string** `"true"`/`"false"`),
`isSQO`. **NOT yet confirmed** (the NL tool didn't surface them on the probe — confirm in Plan 3 via
a column-named question): stage name, forecast category, owner, account name, currency.

## Account health (the renewals-recipe health join)

The renewal report's **Green/Yellow/Red/Black/Blue** health is a **Domo** field (not SF, no Gainsight
in the org). Source columns (from the production health Beast Mode):
- `account_name` — join key to SF `Account.Name`.
- `account_health_score` — **string containing the color word** (matched case-insensitively, e.g.
  `LIKE '%green%'`); five states: **green, yellow, red, black, blue**.
- `days_in_current_health` — integer, how long in the current band.

Domo's own presentation colors (for reference only — **our in-chat viz uses brand tokens, not these**):
black `#333333`, red `#d40000`, yellow `#f2cd14`, blue `#0055d4`, green `#5aa02c`. The
`revenue-insights` viz kit maps the five states to **brand** colors via `brand_kit`
(green→semantic success, red→semantic alert, yellow→brand_yellow, blue→semantic link, black→muted).

**⚠️ Health is a card-level Beast Mode, NOT a queryable column (found in the 2026-06-26 live smoke
test).** The `account_health_score` / `days_in_current_health` fields the production health Beast Mode
references live on the **"Master - Renewal Opportunities" card** (dataset `789f9dcd-e5c0-4c59-8c09-82b6eb0e3aa7`),
which is a raw ~100-column Opportunity dump with **no stored `account_health_score` column** — those are
themselves derived Beast Modes computed in the card layer. **The Domo SQL MCP (`DomoSqlQueryTool`)
cannot read card Beast Modes**, and worse, when asked for a non-existent column name it **silently
aliases the name onto a wrong source column** (it returned `AccountId` as `account_name` and `Amount` as
`account_health_score`, yielding a 0/77 health-join). So the renewals recipe's health source is **TBD —
pick one:** (a) the raw column(s) `account_health_score` derives from (then the recipe computes the
color band deterministically), (b) a different Domo dataset that stores health as a real column, or
(c) the OP platform `get_account_health`. Until resolved, the recipe renders real buckets + ARR with
`health = None` (no risk-weighting). Fixture `tests/fixtures/domo/account_health_sample.json` is the
intended shape (synthetic) once a real source is wired.

**Domo SQL MCP caveat (general):** it aliases requested column names onto best-guess source columns
rather than erroring on unknown columns — always confirm returned VALUES look right, not just that
columns came back named as asked.

## Named queries (phrase to route to the right dataset)

- **ARR/NRR bridge (current fiscal quarter):**
  *"From the \"arr scorecard metrics ALL SUBSCRIPTIONS\" dataset, return the monthly rows for the
  current fiscal quarter with new_logo_arr_usd, expansion_arr_usd, upsell_arr_usd, downsell_arr_usd,
  churn_arr_usd, lost_arr_usd, arr_usd_starting, ending_arr_usd_carryover, net_retention_rate,
  gross_retention_rate, fiscal_period, current_fiscal_quarter_end_date."*
- **Pipeline (open opps by stage/forecast):** *"From the \"Master - Opportunities\" dataset only,
  return open opportunities with amount, CloseDate, Type, stage, forecast category, owner, account,
  segment."* (Confirm the stage/forecast/owner column names from the result.)

## Open items for Plan 3 (never fabricate — confirm live)

- **Quota/target location:** `Actual vs Plan by quarter` returned 0 rows on a generic probe;
  confirm its columns + grain (company vs rep) with a targeted question, and compare with
  `Corporate Scorecard`. Record the authoritative quota source here once confirmed.
- **Master - Opportunities** stage / forecast-category / owner / account / currency column names.
- **Consumption usage** column names in `APP Data: Audits, Journeys and Rules by Account` /
  `FACT TABLE - Account`, and the account key that joins to SF (`OP_Account_ID__c`/`OP_App_ID__c`).
