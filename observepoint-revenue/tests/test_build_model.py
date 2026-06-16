# tests/test_build_model.py
import json, pathlib, sys
import pytest

import build_model as bm
import compute_scope as cs

ROOT = pathlib.Path(__file__).resolve().parent.parent

TIERS = cs.BAKED_TIERS
LAYERS = [
    {"name": "Baseline inventory", "why": "A full sweep so nothing is invisible.", "pct": 1.0, "runs_per_year": 1},
    {"name": "Inventory refresh", "why": "Quarterly keeps the picture current.", "pct": 0.50, "runs_per_year": 4},
    {"name": "Compliance audit", "why": "Monthly audit of the key body.", "pct": 0.15, "runs_per_year": 12},
    {"name": "Release catch", "why": "Weekly, aligned to releases.", "pct": 0.05, "runs_per_year": 52},
    {"name": "Critical watch", "why": "Daily on crown-jewel pages.", "pct": 0.01, "runs_per_year": 365},
]
DATA = {
    "customer": "Acme Corp", "date": "2026-06-16",
    "page_count": {"low": 88_000, "anchor": 95_000, "high": 105_000},
    "multipliers": {"geographies": 1, "scenarios": 3, "environments": 1},
    "cadence_layers": LAYERS, "buffer_pct": 0.0, "tiers": TIERS,
    "per_domain": [{"hostname": "acme.com", "defensible_pages": 95_000, "url_samples": ["https://acme.com/"]}],
    "rollup": {"spiral_adjusted_anchor": 95_000},
}


def emulate_model(base, geos, scenarios, env, layers, buffer_pct, tiers):
    sweep = base * geos * scenarios * env
    spl = [round((sweep * L["pct"]) * L["runs_per_year"], 2) for L in layers]
    predicted = round(sum(spl))
    purchased = round(predicted * (1 + buffer_pct))
    los, his, rates, lo = [], [], [], 0
    for t in tiers:
        los.append(lo); his.append(lo + t["limit"]); rates.append(t["pricePerPage"]); lo += t["limit"]
    his[-1] = 10**12
    price = round(sum(max(0, min(purchased, his[i]) - los[i]) * rates[i] for i in range(len(tiers))), 2)
    return {"sweep": sweep, "predicted": predicted, "purchased": purchased, "price": price}


def _cs_anchor(data):
    out = cs.compute({"page_count": data["page_count"], "multipliers": data["multipliers"],
                      "cadence_layers": data["cadence_layers"], "buffer_pct": data["buffer_pct"],
                      "tiers": data["tiers"]})
    return out["anchor"]


def test_input_cells_present_and_editable_values():
    ws = bm.build_workbook(DATA)["Investment Model"]
    assert ws["B6"].value == 95_000          # validated pages
    assert ws["B7"].value == 1 and ws["B8"].value == 3 and ws["B9"].value == 1
    assert ws["C14"].value == 1.0 and ws["D14"].value == 1     # first layer pct + runs/yr
    assert ws["A14"].value == "Baseline inventory" and ws["B14"].value.startswith("A full sweep")


def test_scan_formulas_are_formulas_not_values():
    ws = bm.build_workbook(DATA)["Investment Model"]
    assert ws["B10"].value == "=B6*B7*B8*B9"
    assert ws["E14"].value == "=$B$10*C14"
    assert ws["F14"].value == "=ROUND(E14*D14,2)"
    assert ws["F20"].value == "=ROUND(SUM(F14:F18),0)"
    assert ws["F21"].value == "=ROUND(F20*(1+B19),0)"


def test_emulator_matches_engine_at_anchor():
    a = _cs_anchor(DATA)
    e = emulate_model(95_000, 1, 3, 1, LAYERS, 0.0, TIERS)
    assert e["predicted"] == a["predicted_scans"]
    assert e["purchased"] == a["purchased_scans"]


def test_emulator_matches_engine_when_daily_dropped_and_quarterly_halved():
    layers = json.loads(json.dumps(LAYERS))
    layers[4]["pct"] = 0.0           # drop "Critical watch" (daily)
    layers[1]["pct"] = 0.25          # halve "Inventory refresh" (quarterly)
    d = json.loads(json.dumps(DATA)); d["cadence_layers"] = layers
    a = _cs_anchor(d)
    e = emulate_model(95_000, 1, 3, 1, layers, 0.0, TIERS)
    assert e["predicted"] == a["predicted_scans"] and e["purchased"] == a["purchased_scans"]


# ---------- Fix 1: 5-layer guard ----------

def test_six_layers_raises():
    d = json.loads(json.dumps(DATA))
    d["cadence_layers"] = json.loads(json.dumps(LAYERS)) + [
        {"name": "Extra", "why": "Should not exist.", "pct": 0.001, "runs_per_year": 1}
    ]
    with pytest.raises(ValueError, match="expected exactly 5 cadence layers"):
        bm.build_workbook(d)


def test_four_layers_raises():
    d = json.loads(json.dumps(DATA))
    d["cadence_layers"] = json.loads(json.dumps(LAYERS))[:4]
    with pytest.raises(ValueError, match="expected exactly 5 cadence layers"):
        bm.build_workbook(d)


# ---------- Fix 2: buffer formula with non-zero buffer ----------

def test_emulator_matches_engine_with_nonzero_buffer():
    d = json.loads(json.dumps(DATA))
    d["buffer_pct"] = 0.15
    a = _cs_anchor(d)
    e = emulate_model(95_000, 1, 3, 1, LAYERS, 0.15, TIERS)
    assert e["predicted"] == a["predicted_scans"]
    assert e["purchased"] == a["purchased_scans"]
    assert e["purchased"] != e["predicted"]   # proves the buffer path is exercised


# ---------- Task 2: Pricing sheet ----------

def test_pricing_band_table_derived_from_tiers():
    ws = bm.build_workbook(DATA)["Pricing"]
    # cumulative Lo/Hi from BAKED_TIERS widths; last Hi is the 1e12 sentinel
    assert ws["B5"].value == 0 and ws["C5"].value == 1_000 and ws["D5"].value == 0.0
    assert ws["B6"].value == 1_000 and ws["C6"].value == 51_000 and ws["D6"].value == 0.17
    assert ws["C10"].value == 10**12 and ws["D10"].value == 0.03


def test_price_cost_formula_references_purchased_scans():
    ws = bm.build_workbook(DATA)["Pricing"]
    assert ws["E5"].value == "=MAX(0, MIN('Investment Model'!$F$21, C5) - B5) * D5"
    assert ws["E11"].value == "=ROUND(SUM(E5:E10),2)"


def test_price_emulator_matches_engine_anchor_and_perturbations():
    for mutate in (lambda L: L,
                   lambda L: ([{**l, "pct": 0.0} if l["name"] == "Critical watch" else l for l in L]),
                   lambda L: ([{**l, "pct": 0.25} if l["name"] == "Inventory refresh" else l for l in L])):
        layers = mutate(json.loads(json.dumps(LAYERS)))
        d = json.loads(json.dumps(DATA)); d["cadence_layers"] = layers
        a = _cs_anchor(d)
        e = emulate_model(95_000, 1, 3, 1, layers, 0.0, TIERS)
        assert e["price"] == a["price"]["total"], f"price mismatch for {layers}"


# ---------- Fix 1 (code-review): dynamic model→pricing total-row reference ----------

def test_investment_model_b23_and_pricing_total_row_track_tier_count():
    """5-tier custom set: B23 must reference E10; Pricing!E10 must sum E5:E9."""
    five_tiers = cs.BAKED_TIERS[:-1]   # drop last band → 5 tiers
    d = json.loads(json.dumps(DATA))
    d["tiers"] = five_tiers

    wb = bm.build_workbook(d)

    # (a) Investment Model B23 references the correct total row for 5 tiers
    assert wb["Investment Model"]["B23"].value == "='Pricing'!E10"

    # (b) Pricing total cell at E10 sums the 5 band rows (E5:E9)
    assert wb["Pricing"]["E10"].value == "=ROUND(SUM(E5:E9),2)"
