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
