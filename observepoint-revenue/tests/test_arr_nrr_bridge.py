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
