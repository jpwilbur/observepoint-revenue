# Recipe catalog (revenue-insights)

Vetted, tested recipes. Each: altitude · sources · compute script · queries · viz.
A request with no matching recipe uses the **ad-hoc fallback** (see SKILL.md).

| Recipe | Altitude | Sources | Compute script | Status |
|---|---|---|---|---|
| renewals-at-risk | RevOps / CSM | SF renewal forecast + Domo health | `scripts/renewals_at_risk.py` | shipped |
| pipeline-coverage | VP Sales | SF open opps + Quota__c | `scripts/pipeline_coverage.py` | shipped |
| arr-nrr-bridge | Board / CRO | Domo | `scripts/arr_nrr_bridge.py` | shipped |
| consumption-pacing | CSM | OP usage + SF | `scripts/consumption_pacing.py` | Plan 3 |

## arr-nrr-bridge
- **Queries:** Domo `arr scorecard metrics ALL SUBSCRIPTIONS` dataset — save result JSON.
- **Run:** `arr_nrr_bridge.py <scorecard.json> --out <path>` → branded HTML.
- **Viz:** 3 KPI cards (Net New ARR / NRR / GRR) + ARR bridge waterfall table.

## renewals-at-risk
- **Queries:** the renewal SOQL in `lib/salesforce/salesforce-org.md` ("Renewals") + the account-
  health query in `lib/domo/domo-datasets.md` ("Account health"). Save each result to JSON.
- **Run:** `renewals_at_risk.py <renewals.json> --health <health.json> --today <ISO> [--out <path>]`
  → branded HTML.
- **Viz:** 3 KPI cards (Will Renew / Undetermined / Will Not Renew) + Will-Not-Renew table
  + Undetermined risk-weighted table + caveats footnote.

## pipeline-coverage
- **Queries:** the open-opp SOQL + quota SOQL in `lib/salesforce/salesforce-org.md`
  ("Pipeline + quota"). Save each result to JSON.
- **Run:** `pipeline_coverage.py <opps.json> --quota <quota.json> --today <ISO> [--out <path>]`
  → branded HTML.
- **Viz:** 3 KPI cards (Open pipeline / Quota / Coverage ratio) + Forecast pacing table
  (Commit/Expect/Best Case/Pipeline) + Gap-to-quota table.
