"""renewals-at-risk recipe (RevOps/CSM): SF renewal opps + Domo account health -> bucketed
at-risk view. The MODEL runs the renewal SOQL (lib/salesforce/salesforce-org.md) and the Domo
health query (lib/domo/domo-datasets.md "Account health"); this script joins them and computes
every number. No SF/Domo calls, no model math."""
import argparse
import json
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[3] / "lib" / "salesforce"))
sys.path.insert(0, str(_HERE.parents[3] / "lib" / "domo"))
import sf_io  # noqa: E402
import domo_io  # noqa: E402
import currency  # noqa: E402  (same scripts dir, on sys.path at runtime + via conftest)
import periods  # noqa: E402
import risk_weight  # noqa: E402
import viz_kit  # noqa: E402

# Undetermined-bucket risk weights — see metrics-canon.md (matches the proven report).
RENEWAL_WEIGHTS = {"red": 0.25, "yellow": 0.5}

# SF renewal fields -> normalized keys (confirmed Plan 1; health is NOT here — joined from Domo).
DEFAULT_FIELD_MAP = {
    "account": "Account.Name",
    "status": "Renewal_Forecast__c",
    "arr": "Renewable_ARR__c",
    "currency": "CurrencyIsoCode",
    "close_date": "CloseDate",
}

_HEALTH_COLORS = ("green", "yellow", "red", "blue", "black")


def _get(rec, path):
    cur = rec
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _norm_acct(name):
    return str(name or "").strip().lower()


def health_token(s):
    """Extract the color token from a Domo account_health_score string (e.g. 'Red - At Risk'
    -> 'red'). Returns None if no known color is present."""
    low = str(s or "").lower()
    for c in _HEALTH_COLORS:
        if c in low:
            return c
    return None


def normalize_sf_records(records, field_map=DEFAULT_FIELD_MAP):
    """SF renewal records -> normalized rows (account/status/arr/currency/close_date). No health."""
    out = []
    for r in records:
        out.append({
            "account": _get(r, field_map["account"]),
            "status": _get(r, field_map["status"]),
            "arr": _get(r, field_map["arr"]),
            "currency": _get(r, field_map["currency"]) or "USD",
            "close_date": _get(r, field_map["close_date"]),
        })
    return out


def health_by_account(domo_health_records):
    """Domo health rows -> {normalized account_name: color token}."""
    out = {}
    for r in domo_health_records:
        acct = _norm_acct(r.get("account_name"))
        tok = health_token(r.get("account_health_score"))
        if acct and tok:
            out[acct] = tok
    return out


def join_health(sf_rows, health_map):
    """Add a `health` color token to each SF row from the Domo health map (None if no match)."""
    return [{**r, "health": health_map.get(_norm_acct(r["account"]))} for r in sf_rows]


def _bucket(status):
    s = str(status or "").strip().lower()
    if "not" in s:                      # 'Will Not Renew', 'WNR'
        return "will_not_renew"
    if "undeterm" in s or "unknown" in s:
        return "undetermined"
    if "renew" in s:
        return "will_renew"
    return "undetermined"               # unmapped -> conservative


def _sort(rows):
    return sorted(rows, key=lambda r: currency.to_number(r["arr"]) or 0.0, reverse=True)


def compute_from_normalized(rows, *, today_iso, fy_start_month=2, weights=None):
    weights = weights or RENEWAL_WEIGHTS
    buckets = {"will_renew": [], "undetermined": [], "will_not_renew": []}
    for r in rows:
        buckets[_bucket(r["status"])].append(r)

    def _summ(brows):
        return {"count": len(brows), "arr": currency.sum_by_currency(brows)}

    und = []
    for r in buckets["undetermined"]:
        rw = risk_weight.risk_weighted(currency.to_number(r["arr"]), r.get("health"), weights)
        und.append({**r, "risk_weighted": rw,
                    "weight": weights.get(str(r.get("health") or "").strip().lower())})

    caveats = [
        f"{r['account']} is flagged Will Not Renew despite a Green health score — worth verifying."
        for r in buckets["will_not_renew"]
        if str(r.get("health") or "").strip().lower() == "green"
    ]

    return {
        "period": periods.fiscal_quarter(today_iso, fy_start_month),
        "summary": {
            "will_renew": _summ(buckets["will_renew"]),
            "undetermined": {**_summ(buckets["undetermined"]),
                             "risk_weighted": currency.sum_by_currency(und, amount_key="risk_weighted")},
            "will_not_renew": _summ(buckets["will_not_renew"]),
        },
        "will_not_renew_rows": _sort(buckets["will_not_renew"]),
        "undetermined_rows": _sort(und),
        "caveats": caveats,
    }


def compute(sf_records, health_records, *, today_iso, fy_start_month=2, weights=None,
            field_map=DEFAULT_FIELD_MAP):
    """SF renewal JSON + Domo health JSON -> the renewals-at-risk result. Joins health on account."""
    sf_rows = normalize_sf_records(sf_io.parse_records(sf_records), field_map)
    hmap = health_by_account(domo_io.parse_query_result(health_records))
    rows = join_health(sf_rows, hmap)
    return compute_from_normalized(rows, today_iso=today_iso,
                                   fy_start_month=fy_start_month, weights=weights)


def _arr_str(arrmap):
    return " + ".join(currency.format_money(v, c) for c, v in sorted(arrmap.items())) or "—"


def render(result):
    s, p = result["summary"], result["period"]
    cards = '<div class="cards">' + "".join([
        viz_kit.stat_card("Will Renew", s["will_renew"]["count"],
                          f'opps · {_arr_str(s["will_renew"]["arr"])} ARR'),
        viz_kit.stat_card("Undetermined", s["undetermined"]["count"],
                          f'opps · {_arr_str(s["undetermined"]["arr"])} ARR'),
        viz_kit.stat_card("Will Not Renew", s["will_not_renew"]["count"],
                          f'opps · {_arr_str(s["will_not_renew"]["arr"])} at risk'),
    ]) + "</div>"

    money = lambda r: currency.format_money(currency.to_number(r["arr"]), r["currency"])
    wnr = viz_kit.section_header(
        f'Will Not Renew · {_arr_str(s["will_not_renew"]["arr"])} confirmed lost'
    ) + viz_kit.ranked_table(
        [("ACCOUNT", "account"),
         ("HEALTH", lambda r: viz_kit.health_badge(r["health"])),
         ("RENEWABLE ARR", money),
         ("CLOSE DATE", "close_date")],
        result["will_not_renew_rows"])

    und = viz_kit.section_header("Undetermined · risk-weighted") + viz_kit.ranked_table(
        [("ACCOUNT", "account"),
         ("HEALTH", lambda r: viz_kit.health_badge(r["health"])),
         ("RENEWABLE ARR", money),
         ("RISK-WEIGHTED", lambda r: currency.format_money(r["risk_weighted"], r["currency"])),
         ("CLOSE DATE", "close_date")],
        result["undetermined_rows"])

    body = cards + wnr + und + viz_kit.caveats(result["caveats"])
    return viz_kit.page(
        "Renewals at Risk", body,
        kicker=f'{p["quarter"]} {p["fy_label"]} · {p["start"]} – {p["end"]}',
        subtitle="Source: Salesforce renewal forecast · undetermined risk-weighted by health score")


def main(argv=None):
    ap = argparse.ArgumentParser(description="renewals-at-risk recipe -> branded HTML")
    ap.add_argument("renewals_json", help="SF renewal SOQL result JSON")
    ap.add_argument("--health", required=True, help="Domo account-health result JSON")
    ap.add_argument("--today", required=True, help="ISO date anchoring the fiscal quarter")
    ap.add_argument("--fy-start-month", type=int, default=2)
    ap.add_argument("--out", default="renewals-at-risk.html", help="HTML output path")
    a = ap.parse_args(argv)
    sf_data = json.loads(pathlib.Path(a.renewals_json).read_text())
    health_data = json.loads(pathlib.Path(a.health).read_text())
    try:
        result = compute(sf_data, health_data, today_iso=a.today, fy_start_month=a.fy_start_month)
    except (sf_io.SalesforceResultError, domo_io.DomoResultError) as e:
        sys.exit(f"renewal/health result unusable: {e}")
    pathlib.Path(a.out).write_text(render(result))
    print(a.out)


if __name__ == "__main__":
    main()
