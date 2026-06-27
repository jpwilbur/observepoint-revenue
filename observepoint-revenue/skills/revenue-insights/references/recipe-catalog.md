# Recipe catalog (revenue-insights)

Vetted, tested recipes. Each: altitude · sources · compute script · queries · viz.
A request with no matching recipe uses the **ad-hoc fallback** (see SKILL.md).

| Recipe | Altitude | Sources | Compute script | Status |
|---|---|---|---|---|
| renewals-at-risk | RevOps / CSM | SF renewal forecast + Domo health | `scripts/renewals_at_risk.py` | shipped |
| pipeline-coverage | VP Sales | SF + Domo | `scripts/pipeline_coverage.py` | Plan 3 |
| arr-nrr-bridge | Board / CRO | Domo | `scripts/arr_nrr_bridge.py` | Plan 3 |
| consumption-pacing | CSM | OP usage + SF | `scripts/consumption_pacing.py` | Plan 3 |

## renewals-at-risk
- **Queries:** the renewal SOQL in `lib/salesforce/salesforce-org.md` ("Renewals") + the account-
  health query in `lib/domo/domo-datasets.md` ("Account health"). Save each result to JSON.
- **Run:** `renewals_at_risk.py <renewals.json> --health <health.json> --today <ISO> [--out <path>]`
  → branded HTML.
- **Viz:** 3 KPI cards (Will Renew / Undetermined / Will Not Renew) + Will-Not-Renew table
  + Undetermined risk-weighted table + caveats footnote.
