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

    # Closed-won in quarter counts against quota for gap purposes
    closed_won = [o for o in in_q if o["is_closed"]]
    closed_won_total = currency.sum_by_currency(closed_won, amount_key="amount")

    coverage_ratio, gap = {}, {}
    for cur, q in quota.items():
        pipe = open_pipeline.get(cur, 0.0)
        coverage_ratio[cur] = (pipe / q) if q else None
        committed = forecast.get("Commit", {}).get(cur, 0.0)
        closed = closed_won_total.get(cur, 0.0)
        gap[cur] = max(0.0, q - committed - closed)

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
