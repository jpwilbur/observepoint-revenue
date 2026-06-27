# revenue-insights — Plan 3: remaining recipes (arr-nrr-bridge, pipeline-coverage, consumption-pacing) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the other three seed recipes to the `revenue-insights` engine — arr-nrr-bridge (Board/Domo), pipeline-coverage & forecast-pacing (VP Sales/SF), consumption-pacing (CSM/OP usage + SF contract) — reusing the proven recipe pattern (gather → normalize → compute → render via `viz_kit`).

**Architecture:** Same as Plans 1–2. The model gathers via MCP (SF `soqlQuery`, Domo `DomoSqlQueryTool`, OP usage tools); deterministic Python computes every number and renders branded HTML. No Python calls a source; no LLM math; no LLM state; read-only. Each recipe is a new script in `skills/revenue-insights/scripts/`, importing the shared helpers (`currency`, `periods`, `risk_weight` where relevant) + `viz_kit`, and `sf_io`/`domo_io` from `lib/`.

**Tech Stack:** Python 3 (stdlib only in compute/render), pytest, `branding-guide/brand_kit`, the SF/Domo/OP MCPs.

## Global Constraints

- **Interpreter:** `/opt/homebrew/bin/python3` for tests. SKILL recipe commands use `python3` (stdlib-only recipes ship to reps).
- **Test command:** `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q` (must stay green; baseline at Plan 3 start = **374**). Never pipe pytest through `| tail` in an `&&` chain.
- **Architecture rule:** no Python calls SF/Domo/OP; no model arithmetic; no model-held state. **Read-only.**
- **Brand values from `branding-guide`/`brand_kit` only** — no hardcoded hex/font in any renderer (reuse `viz_kit`).
- **Currency:** keep currencies separate; the Domo `arr scorecard` `_usd` columns are already FX-normalized (use them directly). Deal-level SF stays native via `currency.sum_by_currency`.
- **Fiscal:** FY starts Feb (`fy_start_month=2`); prefer the Domo dataset's own `current_fiscal_*`/`fiscal_period` columns when present.
- **Never fabricate** a number; missing input → labeled default / "none found".
- **Output location:** `~/Documents/ObservePoint Revenue/revenue-insights/`.
- **Commit email:** `16406437+jpwilbur@users.noreply.github.com`.
- **Confirmed sources (Plan 1 + Plan 3 discovery):**
  - arr-nrr-bridge → Domo `arr scorecard metrics ALL SUBSCRIPTIONS` (`0f19647e-cc94-4aa0-89c4-dd655ab18b08`); fixture `tests/fixtures/domo/arr_scorecard_sample.json` exists. Bridge columns + `quarterly_net_revenue_retention_rate`/`quarterly_gross_revenue_retention_rate` + `fiscal_period`/`current_fiscal_quarter`/`isFiscalQuarterEndingMonth` are pre-computed.
  - pipeline-coverage → SF `Opportunity` (`Amount`, `CloseDate`, `StageName`, `ForecastCategoryName` ∈ {Omitted, Pipeline, Best Case, Expect, Commit, Closed}, `IsClosed`, `IsWon`, `Acquisition_Segment__c`, `CurrencyIsoCode`, `Owner.Name`) + SF `Quota__c` (`Month_Quota__c`, `Month_Start__c`, `Department__c`, `Type__c`, `OwnerId`, `CurrencyIsoCode`).
  - consumption-pacing → OP usage (OP MCP) + SF contract terms — **discovered in Task 3 Step 1** (not yet pinned).

---

### Task 1: arr-nrr-bridge recipe (Board/CRO; Domo `arr scorecard`)

The highest-altitude deliverable. Domo pre-computes the bridge; the recipe selects the current fiscal quarter's monthly rows, sums the movement components into a waterfall, and reads the quarter-ending NRR/GRR. All values are USD (FX-normalized by Domo).

**Files:**
- Create: `observepoint-revenue/skills/revenue-insights/scripts/arr_nrr_bridge.py`
- Create: `observepoint-revenue/tests/test_arr_nrr_bridge.py`
- Modify: `observepoint-revenue/skills/revenue-insights/references/recipe-catalog.md` (status shipped) + `metrics-canon.md` (NRR/GRR methodology)

**Interfaces:**
- Consumes: `domo_io` (lib/domo), `currency`, `viz_kit`; fixture `tests/fixtures/domo/arr_scorecard_sample.json`.
- Produces: `arr_nrr_bridge.current_quarter_rows(rows, *, fy_year=None, fy_quarter=None) -> list`, `compute_from_rows(rows) -> dict`, `compute(domo_result) -> dict`, `render(result) -> str`, `main(argv)`. Result shape: `{period:{fy_label,quarter,start,end}, starting_arr, new_logo, expansion, contraction, churn, ending_arr, nrr, grr, net_new_arr}`.

- [ ] **Step 1: Write the failing tests**

Create `observepoint-revenue/tests/test_arr_nrr_bridge.py`:

```python
import json, pathlib
import arr_nrr_bridge as bridge

FIX = pathlib.Path(__file__).parent / "fixtures" / "domo" / "arr_scorecard_sample.json"


def test_compute_bridge_from_fixture():
    rows = json.loads(FIX.read_text())
    r = bridge.compute(rows)
    # fixture: May + Jul rows, both fiscal_period 2026-Q2, current_fiscal_quarter 2
    assert r["period"]["quarter"] == "Q2" and r["period"]["fy_label"] == "FY26"
    # movement sums across the quarter's rows (USD, FX-normalized)
    assert r["new_logo"] == 70000.0          # 40000 + 30000
    assert r["expansion"] == 68000.0         # (25000+15000) + (18000+10000)
    assert r["contraction"] == 13000.0       # 8000 + 5000 (downsell)
    assert r["churn"] == 21000.0             # 12000 + 9000
    # NRR/GRR read from the quarter-ending month row (isFiscalQuarterEndingMonth==1 -> Jul)
    assert r["nrr"] == 1.08
    assert r["grr"] == 0.91


def test_current_quarter_rows_filters_by_current_fiscal_flags():
    rows = json.loads(FIX.read_text())
    q = bridge.current_quarter_rows(rows)
    assert len(q) == 2 and all(x["fiscal_period"] == "2026-Q2" for x in q)


def test_render_is_branded():
    rows = json.loads(FIX.read_text())
    out = bridge.render(bridge.compute(rows))
    assert "ARR" in out and "var(--op-bg)" in out and "<!DOCTYPE html>" in out
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_arr_nrr_bridge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'arr_nrr_bridge'`.

- [ ] **Step 3: Implement `arr_nrr_bridge.py`**

Create `observepoint-revenue/skills/revenue-insights/scripts/arr_nrr_bridge.py`:

```python
"""arr-nrr-bridge recipe (Board/CRO): Domo arr-scorecard monthly rows -> the current fiscal
quarter's ARR movement waterfall + NRR/GRR. Domo pre-computes the components (USD, FX-normalized)
and the quarterly retention rates; this script selects the quarter, sums the waterfall, and reads
the quarter-ending rates. No Domo calls, no model math."""
import argparse
import json
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[3] / "lib" / "domo"))
import domo_io  # noqa: E402
import currency  # noqa: E402
import viz_kit  # noqa: E402


def _num(r, k):
    return currency.to_number(r.get(k)) or 0.0


def current_quarter_rows(rows, *, fy_year=None, fy_quarter=None):
    """The monthly rows belonging to the target fiscal quarter. Defaults to the dataset's own
    `current_fiscal_year`/`current_fiscal_quarter` (Domo stamps these on every row)."""
    if not rows:
        return []
    fy_year = fy_year if fy_year is not None else currency.to_number(rows[0].get("current_fiscal_year"))
    fy_quarter = fy_quarter if fy_quarter is not None else currency.to_number(rows[0].get("current_fiscal_quarter"))
    return [r for r in rows
            if currency.to_number(r.get("fiscal_year")) == fy_year
            and currency.to_number(r.get("fiscal_quarter")) == fy_quarter]


def compute_from_rows(q):
    """q = the quarter's monthly rows (already filtered). Sums the waterfall; reads NRR/GRR from
    the quarter-ending month (isFiscalQuarterEndingMonth==1), else the last row."""
    starting = _num(q[0], "arr_usd_starting") if q else 0.0
    new_logo = sum(_num(r, "new_logo_arr_usd") for r in q)
    expansion = sum(_num(r, "expansion_arr_usd") + _num(r, "upsell_arr_usd") for r in q)
    contraction = sum(_num(r, "downsell_arr_usd") for r in q)
    churn = sum(_num(r, "churn_arr_usd") for r in q)
    ending = _num(q[-1], "ending_arr_usd_carryover") if q else 0.0
    end_rows = [r for r in q if currency.to_number(r.get("isFiscalQuarterEndingMonth")) == 1] or q[-1:]
    er = end_rows[-1] if end_rows else {}
    return {
        "starting_arr": starting,
        "new_logo": new_logo,
        "expansion": expansion,
        "contraction": contraction,
        "churn": churn,
        "ending_arr": ending,
        "net_new_arr": new_logo + expansion - contraction - churn,
        "nrr": currency.to_number(er.get("quarterly_net_revenue_retention_rate")),
        "grr": currency.to_number(er.get("quarterly_gross_revenue_retention_rate")),
    }


def _period(q):
    if not q:
        return {"fy_label": "FY?", "quarter": "Q?", "start": "", "end": ""}
    r0 = q[0]
    fy = currency.to_number(r0.get("fiscal_year"))
    quarter = currency.to_number(r0.get("fiscal_quarter"))
    return {
        "fy_label": f"FY{int(fy) % 100:02d}" if fy else "FY?",
        "quarter": f"Q{int(quarter)}" if quarter else "Q?",
        "start": str(q[0].get("start_of_month") or "")[:10],
        "end": str(r0.get("current_fiscal_quarter_end_date") or "")[:10],
    }


def compute(domo_result, *, fy_year=None, fy_quarter=None):
    rows = domo_io.parse_query_result(domo_result)
    q = current_quarter_rows(rows, fy_year=fy_year, fy_quarter=fy_quarter)
    return {"period": _period(q), **compute_from_rows(q)}


def _usd(n):
    return currency.format_money(n, "USD")


def _pct(x):
    return f"{x * 100:.0f}%" if x is not None else "—"


def render(result):
    p = result["period"]
    cards = '<div class="cards">' + "".join([
        viz_kit.stat_card("Net New ARR", _usd(result["net_new_arr"]), "this quarter"),
        viz_kit.stat_card("NRR", _pct(result["nrr"]), "net revenue retention"),
        viz_kit.stat_card("GRR", _pct(result["grr"]), "gross revenue retention"),
    ]) + "</div>"
    bridge_rows = [
        {"k": "Starting ARR", "v": _usd(result["starting_arr"])},
        {"k": "+ New logo", "v": _usd(result["new_logo"])},
        {"k": "+ Expansion", "v": _usd(result["expansion"])},
        {"k": "− Contraction", "v": _usd(-result["contraction"])},
        {"k": "− Churn", "v": _usd(-result["churn"])},
        {"k": "Ending ARR", "v": _usd(result["ending_arr"])},
    ]
    table = viz_kit.section_header("ARR bridge") + viz_kit.ranked_table(
        [("MOVEMENT", "k"), ("ARR (USD)", "v")], bridge_rows)
    return viz_kit.page("ARR / NRR Bridge", cards + table,
                        kicker=f'{p["quarter"]} {p["fy_label"]} · {p["start"]} – {p["end"]}',
                        subtitle="Source: Domo arr scorecard (USD, FX-normalized) · gross-renewal methodology")


def main(argv=None):
    ap = argparse.ArgumentParser(description="arr-nrr-bridge recipe -> branded HTML")
    ap.add_argument("scorecard_json", help="Domo arr-scorecard result JSON")
    ap.add_argument("--out", default="arr-nrr-bridge.html")
    a = ap.parse_args(argv)
    data = json.loads(pathlib.Path(a.scorecard_json).read_text())
    try:
        result = compute(data)
    except domo_io.DomoResultError as e:
        sys.exit(f"scorecard result unusable: {e}")
    pathlib.Path(a.out).write_text(render(result))
    print(a.out)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests — verify pass**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_arr_nrr_bridge.py -v`
Expected: PASS (3 tests). The fixture's two rows (May, Jul; both fiscal_year 2026, fiscal_quarter 2) drive the sums; Jul has `isFiscalQuarterEndingMonth=1` with NRR 1.08 / GRR 0.91.

- [ ] **Step 5: Update canon + catalog**

In `references/metrics-canon.md`, add an "ARR / NRR bridge" subsection: starting → +new logo → +expansion → −contraction → −churn → ending; **NRR/GRR are read from Domo's pre-computed `quarterly_net/gross_revenue_revenue_retention_rate` (USD, FX-normalized)** — the engine does not recompute FX. In `references/recipe-catalog.md`, set arr-nrr-bridge status to **shipped** with its run command (`arr_nrr_bridge.py <scorecard.json> --out <path>`).

- [ ] **Step 6: Run full suite + commit**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q` → PASS (374 + 3).

```bash
cd "observepoint-revenue"
git add skills/revenue-insights/scripts/arr_nrr_bridge.py tests/test_arr_nrr_bridge.py \
        skills/revenue-insights/references/metrics-canon.md skills/revenue-insights/references/recipe-catalog.md
git -c user.email="16406437+jpwilbur@users.noreply.github.com" commit -m "feat(revenue-insights): arr-nrr-bridge recipe (Domo arr scorecard -> ARR waterfall + NRR/GRR)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: pipeline-coverage & forecast-pacing recipe (VP Sales; SF opps + Quota__c)

Open pipeline vs quota (coverage ratio) + the forecast-category pacing ladder. Two SF gathers (open opps in the quarter; quota rows for the quarter), joined deterministically.

**Files:**
- Create: `observepoint-revenue/skills/revenue-insights/scripts/pipeline_coverage.py`
- Create: `observepoint-revenue/tests/test_pipeline_coverage.py`
- Create: `observepoint-revenue/tests/fixtures/sf/pipeline_sample.json` + `tests/fixtures/sf/quota_sample.json` (synthetic; real fields)
- Modify: `references/recipe-catalog.md`, `metrics-canon.md`; `lib/salesforce/salesforce-org.md` (add "Pipeline + quota" section)

**Interfaces:**
- Consumes: `sf_io`, `currency`, `periods`, `viz_kit`.
- Produces: `pipeline_coverage.normalize_opps(records) -> list`, `quota_total(quota_records, *, types=("New ACV","New Logo ACV","Expansion ACV")) -> dict`, `compute(opp_records, quota_records, *, today_iso, fy_start_month=2) -> dict`, `render(result) -> str`, `main(argv)`. Result: `{period, coverage_ratio (by currency), open_pipeline (by currency), quota (by currency), forecast:{Commit,Expect,"Best Case",Pipeline,Omitted (by currency)}, gap_to_quota (by currency)}`.

- [ ] **Step 1: Write the failing tests**

Create `observepoint-revenue/tests/test_pipeline_coverage.py`:

```python
import pipeline_coverage as pc

OPPS = [
    {"Amount": 100000, "CurrencyIsoCode": "USD", "ForecastCategoryName": "Commit",
     "StageName": "Negotiation", "IsClosed": False, "CloseDate": "2026-07-01",
     "Acquisition_Segment__c": "Sales", "Owner": {"Name": "Rep A"}},
    {"Amount": 50000, "CurrencyIsoCode": "USD", "ForecastCategoryName": "Best Case",
     "StageName": "Discovery", "IsClosed": False, "CloseDate": "2026-07-10",
     "Acquisition_Segment__c": "Sales", "Owner": {"Name": "Rep B"}},
    {"Amount": 999999, "CurrencyIsoCode": "USD", "ForecastCategoryName": "Closed",
     "StageName": "Closed Won", "IsClosed": True, "CloseDate": "2026-05-02",
     "Acquisition_Segment__c": "Sales", "Owner": {"Name": "Rep A"}},  # closed -> excluded from open pipeline
]
QUOTA = [
    {"Month_Quota__c": 50000, "Month_Start__c": "2026-05-01", "Type__c": "New ACV", "CurrencyIsoCode": "USD"},
    {"Month_Quota__c": 50000, "Month_Start__c": "2026-06-01", "Type__c": "New ACV", "CurrencyIsoCode": "USD"},
    {"Month_Quota__c": 50000, "Month_Start__c": "2026-07-01", "Type__c": "New ACV", "CurrencyIsoCode": "USD"},
    {"Month_Quota__c": 9999, "Month_Start__c": "2026-07-01", "Type__c": "MQL", "CurrencyIsoCode": "USD"},  # wrong type -> excluded
]


def test_open_pipeline_excludes_closed():
    r = pc.compute(OPPS, QUOTA, today_iso="2026-06-26")
    assert r["open_pipeline"]["USD"] == 150000.0   # 100k + 50k; the closed 999999 excluded


def test_quota_total_sums_in_window_and_type():
    r = pc.compute(OPPS, QUOTA, today_iso="2026-06-26")
    assert r["quota"]["USD"] == 150000.0           # 3x 50k New ACV; MQL excluded


def test_coverage_ratio_and_gap():
    r = pc.compute(OPPS, QUOTA, today_iso="2026-06-26")
    assert round(r["coverage_ratio"]["USD"], 2) == 1.0   # 150k pipeline / 150k quota
    assert r["gap_to_quota"]["USD"] == 0.0               # quota - committed/closed coverage (see canon)


def test_forecast_pacing_buckets():
    r = pc.compute(OPPS, QUOTA, today_iso="2026-06-26")
    assert r["forecast"]["Commit"]["USD"] == 100000.0
    assert r["forecast"]["Best Case"]["USD"] == 50000.0


def test_render_is_branded():
    out = pc.render(pc.compute(OPPS, QUOTA, today_iso="2026-06-26"))
    assert "Pipeline Coverage" in out and "var(--op-bg)" in out
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_pipeline_coverage.py -v` → FAIL (`No module named 'pipeline_coverage'`).

- [ ] **Step 3: Implement `pipeline_coverage.py`**

Create `observepoint-revenue/skills/revenue-insights/scripts/pipeline_coverage.py`:

```python
"""pipeline-coverage & forecast-pacing recipe (VP Sales): SF open opps vs SF Quota__c for the
current fiscal quarter -> coverage ratio + the forecast-category pacing ladder. Two SF gathers
(open opps; quota), joined here. No SF calls, no model math."""
import argparse
import json
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[3] / "lib" / "salesforce"))
import sf_io  # noqa: E402
import currency  # noqa: E402
import periods  # noqa: E402
import viz_kit  # noqa: E402

FORECAST_ORDER = ["Commit", "Expect", "Best Case", "Pipeline", "Omitted"]
DEFAULT_QUOTA_TYPES = ("New ACV", "New Logo ACV", "Expansion ACV")


def normalize_opps(records):
    out = []
    for r in records:
        owner = r.get("Owner") or {}
        out.append({
            "amount": r.get("Amount"),
            "currency": r.get("CurrencyIsoCode") or "USD",
            "forecast": r.get("ForecastCategoryName"),
            "stage": r.get("StageName"),
            "is_closed": bool(r.get("IsClosed")),
            "close_date": r.get("CloseDate"),
            "segment": r.get("Acquisition_Segment__c"),
            "owner": owner.get("Name") if isinstance(owner, dict) else None,
        })
    return out


def quota_total(quota_records, *, start_iso, end_iso, types=DEFAULT_QUOTA_TYPES):
    rows = [r for r in quota_records
            if (r.get("Type__c") in types)
            and periods.in_window(str(r.get("Month_Start__c"))[:10], start_iso, end_iso)]
    return currency.sum_by_currency(rows, amount_key="Month_Quota__c", currency_key="CurrencyIsoCode")


def compute(opp_records, quota_records, *, today_iso, fy_start_month=2, quota_types=DEFAULT_QUOTA_TYPES):
    period = periods.fiscal_quarter(today_iso, fy_start_month)
    opps = normalize_opps(sf_io.parse_records(opp_records))
    in_q = [o for o in opps if periods.in_window(str(o["close_date"])[:10], period["start"], period["end"])]
    open_opps = [o for o in in_q if not o["is_closed"]]

    open_pipeline = currency.sum_by_currency(open_opps, amount_key="amount")
    quota = quota_total(sf_io.parse_records(quota_records),
                        start_iso=period["start"], end_iso=period["end"], types=quota_types)

    forecast = {}
    for cat in FORECAST_ORDER:
        forecast[cat] = currency.sum_by_currency(
            [o for o in open_opps if o["forecast"] == cat], amount_key="amount")

    coverage_ratio, gap = {}, {}
    for cur, q in quota.items():
        pipe = open_pipeline.get(cur, 0.0)
        coverage_ratio[cur] = (pipe / q) if q else None
        committed = forecast.get("Commit", {}).get(cur, 0.0)
        gap[cur] = max(0.0, q - committed)

    return {
        "period": period,
        "open_pipeline": open_pipeline,
        "quota": quota,
        "coverage_ratio": coverage_ratio,
        "gap_to_quota": gap,
        "forecast": forecast,
    }


def _money_map(m):
    return " + ".join(currency.format_money(v, c) for c, v in sorted(m.items())) or "—"


def render(result):
    p = result["period"]
    cov = result["coverage_ratio"]
    cov_str = " · ".join(f"{c} {v:.1f}x" for c, v in sorted(cov.items()) if v is not None) or "—"
    cards = '<div class="cards">' + "".join([
        viz_kit.stat_card("Open pipeline", _money_map(result["open_pipeline"]), "in-quarter, open"),
        viz_kit.stat_card("Quota", _money_map(result["quota"]), "this quarter"),
        viz_kit.stat_card("Coverage", cov_str, "pipeline ÷ quota"),
    ]) + "</div>"
    frows = [{"cat": cat, "amt": _money_map(result["forecast"].get(cat, {}))}
             for cat in FORECAST_ORDER if result["forecast"].get(cat)]
    table = viz_kit.section_header("Forecast pacing") + viz_kit.ranked_table(
        [("CATEGORY", "cat"), ("OPEN ARR", "amt")], frows)
    gap = viz_kit.section_header("Gap to quota (quota − Commit)") + viz_kit.ranked_table(
        [("CURRENCY", lambda r: r["c"]), ("GAP", lambda r: currency.format_money(r["v"], r["c"]))],
        [{"c": c, "v": v} for c, v in sorted(result["gap_to_quota"].items())])
    return viz_kit.page("Pipeline Coverage & Forecast Pacing", cards + table + gap,
                        kicker=f'{p["quarter"]} {p["fy_label"]} · {p["start"]} – {p["end"]}',
                        subtitle="Source: Salesforce open opportunities + Quota__c · currencies kept separate")


def main(argv=None):
    ap = argparse.ArgumentParser(description="pipeline-coverage recipe -> branded HTML")
    ap.add_argument("opps_json", help="SF open-opportunity SOQL result JSON")
    ap.add_argument("--quota", required=True, help="SF Quota__c SOQL result JSON")
    ap.add_argument("--today", required=True, help="ISO date anchoring the fiscal quarter")
    ap.add_argument("--fy-start-month", type=int, default=2)
    ap.add_argument("--out", default="pipeline-coverage.html")
    a = ap.parse_args(argv)
    opps = json.loads(pathlib.Path(a.opps_json).read_text())
    quota = json.loads(pathlib.Path(a.quota).read_text())
    try:
        result = compute(opps, quota, today_iso=a.today, fy_start_month=a.fy_start_month)
    except sf_io.SalesforceResultError as e:
        sys.exit(f"pipeline/quota result unusable: {e}")
    pathlib.Path(a.out).write_text(render(result))
    print(a.out)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Author synthetic fixtures**

Create `tests/fixtures/sf/pipeline_sample.json` (a `{"records":[...]}` SOQL envelope of open + closed opps across Commit/Best Case/Expect/Pipeline, mixed currency, in/out of the Q2-FY26 window) and `tests/fixtures/sf/quota_sample.json` (Quota__c rows with `Month_Quota__c`/`Month_Start__c`/`Type__c`/`CurrencyIsoCode` spanning the quarter, incl. a non-target `Type__c` to exercise the filter). Synthetic — real field names, fake values.

- [ ] **Step 5: Run tests — verify pass**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_pipeline_coverage.py -v` → PASS (5 tests).

- [ ] **Step 6: Document + commit**

Add a "Pipeline + quota (revenue-insights)" section to `lib/salesforce/salesforce-org.md` (the open-opp query: `SELECT Amount, CurrencyIsoCode, ForecastCategoryName, StageName, IsClosed, IsWon, CloseDate, Acquisition_Segment__c, Owner.Name FROM Opportunity WHERE IsClosed = false AND CloseDate >= :qStart AND CloseDate <= :qEnd`; the quota query: `SELECT Month_Quota__c, Month_Start__c, Type__c, Department__c, OwnerId, CurrencyIsoCode FROM Quota__c WHERE Month_Start__c >= :qStart AND Month_Start__c <= :qEnd`). Set pipeline-coverage to **shipped** in the catalog; add a "Pipeline coverage" canon subsection (coverage = open in-quarter pipeline ÷ quota for the New/Expansion ACV types; gap = quota − Commit; forecast ladder = Commit/Expect/Best Case/Pipeline). Then:

```bash
cd "observepoint-revenue"
git add skills/revenue-insights/scripts/pipeline_coverage.py tests/test_pipeline_coverage.py \
        tests/fixtures/sf/pipeline_sample.json tests/fixtures/sf/quota_sample.json \
        skills/revenue-insights/references/recipe-catalog.md skills/revenue-insights/references/metrics-canon.md \
        lib/salesforce/salesforce-org.md
git -c user.email="16406437+jpwilbur@users.noreply.github.com" commit -m "feat(revenue-insights): pipeline-coverage & forecast-pacing recipe (SF opps + Quota__c)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: consumption-pacing recipe (CSM; OP usage + SF contract) — discovery THEN build

The only recipe needing live discovery: OP page-scan usage vs the contracted allowance. Step 1 pins the OP usage tool + the SF contract source (controller-run, read-only); the rest mirrors the recipe pattern on normalized rows.

**Files:**
- Create: `observepoint-revenue/skills/revenue-insights/scripts/consumption_pacing.py`
- Create: `observepoint-revenue/tests/test_consumption_pacing.py`
- Create: `observepoint-revenue/tests/fixtures/op/usage_sample.json` + `tests/fixtures/sf/contract_sample.json` (synthetic; real fields from Step 1)
- Modify: `references/recipe-catalog.md`, `metrics-canon.md`; `lib/salesforce/salesforce-org.md` (contract section); `lib/domo/domo-datasets.md` or a new OP-usage note.

**Interfaces:**
- Consumes: `sf_io` (+ an OP-usage parser — likely `domo_io`-style or a small local parser), `currency`/`periods`, `viz_kit`.
- Produces: `consumption_pacing.compute_from_normalized(rows, *, period_fraction) -> dict` where each row is `{account, used, contracted}`; `compute(usage_result, contract_result, *, today_iso) -> dict`; `render`; `main`. Result: per-account `{account, used, contracted, pace_pct, status}` with `status ∈ {over, on, under}` and portfolio rollups. **Pure page-scan counts (no $).**

- [ ] **Step 1: Discovery (controller-run, read-only) — pin the OP usage + SF contract sources**

Determine, live: (a) the OP usage source for **page-scans per account per period** — try the OP MCP usage tools (`get_usage_overview` / `get_usage_summary` / `get_usage_trends`) and/or the Domo `APP Data: Audits, Journeys and Rules by Account` (`22de7bc7`) / `FACT TABLE - Account` (`62d467ad`); (b) the **contracted page-scan allowance** per account — check SF `Subscription__c` (OP Subscription) and `SaaSOptics_Contract__c`, and the `OP_Account_ID__c`/`OP_App_ID__c` bridge that joins OP usage ↔ SF account. Record the exact fields + the join key in the lib maps. **Capture the result shapes and author synthetic fixtures** (`tests/fixtures/op/usage_sample.json`, `tests/fixtures/sf/contract_sample.json`) — real fields, fake values, engineered to include an over-pacing, an on-pace, and an under-pacing account. **Never fabricate** a field name; if a source isn't found, record "not found — confirm with rev ops" and narrow scope (e.g. usage-only with a manual contract input).

- [ ] **Step 2: Write the failing tests** (on the normalized shape, source-agnostic)

Create `observepoint-revenue/tests/test_consumption_pacing.py`:

```python
import consumption_pacing as cp

NORM = [
    {"account": "Acme", "used": 600000, "contracted": 1000000},   # 60% used at 50% through period -> over
    {"account": "Globex", "used": 480000, "contracted": 1000000}, # ~on pace
    {"account": "Initech", "used": 200000, "contracted": 1000000},# under
]


def test_pace_and_status_at_half_period():
    r = cp.compute_from_normalized(NORM, period_fraction=0.5)
    by = {x["account"]: x for x in r["accounts"]}
    assert by["Acme"]["status"] == "over"      # used 60% vs 50% elapsed
    assert by["Initech"]["status"] == "under"  # used 20% vs 50% elapsed
    # pace_pct = used / (contracted * period_fraction)
    assert round(by["Acme"]["pace_pct"], 2) == 1.2


def test_rollup_counts():
    r = cp.compute_from_normalized(NORM, period_fraction=0.5)
    assert r["summary"]["over"] == 1 and r["summary"]["under"] == 1
```

- [ ] **Step 3: Implement `consumption_pacing.py`** (compute_from_normalized + a Step-1-driven mapper + render/main)

`compute_from_normalized(rows, *, period_fraction, on_band=0.1)`: for each row, `expected = contracted * period_fraction`; `pace_pct = used / expected` (None-safe); `status = "over" if pace_pct > 1+on_band, "under" if < 1-on_band, else "on"`. Roll up counts + total used/contracted by status. `render` → KPI cards (over / on / under counts) + a ranked table (account · used · contracted · pace% · status badge — reuse `viz_kit.health_badge`-style coloring: over=red, under=yellow, on=green via a small status→token map). `compute(usage_result, contract_result, ...)` joins OP usage ↔ SF contract on the Step-1 key (e.g. `OP_Account_ID__c`), computes `period_fraction` from `periods.fiscal_quarter` + `today_iso`. `main`: `consumption_pacing.py <usage.json> --contract <contract.json> --today <ISO> --out <path>`.

- [ ] **Step 4: Run tests + author fixtures-backed integration test, verify pass**

Run the unit tests (Step 2) → PASS. Add one end-to-end test using the Step-1 fixtures through `compute(...)` (mirrors renewals' e2e). Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_consumption_pacing.py -v` → PASS.

- [ ] **Step 5: Document + commit**

Canon "Consumption pacing" subsection (pace = used ÷ (contracted × period-fraction); over/on/under bands; page-scans only, no $). Catalog → **shipped**. Record the OP usage + SF contract sources + join key in the lib maps. Commit:

```bash
cd "observepoint-revenue"
git add skills/revenue-insights/scripts/consumption_pacing.py tests/test_consumption_pacing.py \
        tests/fixtures/op/ tests/fixtures/sf/contract_sample.json \
        skills/revenue-insights/references/recipe-catalog.md skills/revenue-insights/references/metrics-canon.md \
        lib/salesforce/salesforce-org.md lib/domo/domo-datasets.md
git -c user.email="16406437+jpwilbur@users.noreply.github.com" commit -m "feat(revenue-insights): consumption-pacing recipe (OP usage vs SF contract)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage (Plan 3 scope):**
- *arr-nrr-bridge (Board/Domo)* → Task 1, fully coded against the confirmed `arr scorecard` columns + existing fixture; NRR/GRR from Domo's pre-computed rates (no FX recompute). ✓
- *pipeline-coverage & forecast-pacing (VP Sales/SF)* → Task 2, coded against confirmed `Opportunity` + `Quota__c` fields; coverage = open pipeline ÷ quota, forecast ladder, gap-to-quota; currencies separate. ✓
- *consumption-pacing (CSM/OP+SF)* → Task 3, discovery-first (OP usage + SF contract not yet pinned) then compute/render on a normalized shape. ✓
- *All recipes reuse the engine* (`viz_kit`, `currency`, `periods`, `sf_io`/`domo_io`) and the gather→compute→render pattern; read-only; no LLM math. ✓
- *Each recipe → canon + catalog entry* → Steps in every task. ✓

**Placeholder scan:** Tasks 1–2 are code-complete (sources confirmed). Task 3's compute logic is concrete; its *source field names* are the one genuine unknown, isolated to Step 1 discovery (the normalized-shape tests don't depend on it) — not a TODO. No "TBD"/"add validation"/"similar to".

**Type consistency:** `currency.sum_by_currency(rows, amount_key=, currency_key=)`, `periods.fiscal_quarter`/`in_window`, `viz_kit.*`, `sf_io.parse_records`, `domo_io.parse_query_result` used consistently with their Plan-2 signatures. Each recipe's result keys are used identically in its compute/render/tests.

## Execution Handoff

Plan 3 of 3. After all tasks: a whole-branch review of the full revenue-insights increment, then `finishing-a-development-branch` (decide review/merge/broadcast per the release strategy). Health for renewals-at-risk remains a fast-follow (the rep is tracing `Health_Score__c`'s source).
