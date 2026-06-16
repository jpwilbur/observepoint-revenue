# tests/test_build_model.py
import json, pathlib
import pytest

import build_model as bm
import compute_scope as cs

ROOT = pathlib.Path(__file__).resolve().parent.parent
TIERS = cs.BAKED_TIERS

# The new default ladder: 4 priority layers (buffer is separate, additive).
LAYERS = [
    {"name": "Baseline inventory",       "why": "A full sweep so nothing on the site is invisible — your lay of the land.",
     "pct": 1.0,   "runs_per_year": 1},
    {"name": "High Priority",            "why": "Aligned to release cadence — catches tags/consent breaking shortly after a deploy.",
     "pct": 0.015, "runs_per_year": 52},
    {"name": "Moderate Priority Pages",  "why": "Monthly audit of the meaningful body of the site for tag health & consent compliance.",
     "pct": 0.075, "runs_per_year": 12},
    {"name": "Low Priority Pages",       "why": "A quarterly sweep of the long tail so low-traffic pages don't become blind spots.",
     "pct": 0.20,  "runs_per_year": 4},
]
_PAGES = [9000, 8000, 7000, 6000, 5000, 4000, 3000, 2000, 1000, 900,
          800, 700, 600, 500, 400, 300, 200, 100, 90, 80, 70, 60, 50]   # 23 domains
PER_DOMAIN = [{"hostname": f"d{i}.com", "defensible_pages": p, "url_samples": [f"https://d{i}.com/"]}
              for i, p in enumerate(_PAGES)]
BASE = sum(_PAGES)   # 49,850 — Total Pages Found at defaults (all in-scope, 100% sample) == anchor
DATA = {
    "customer": "Acme Corp", "date": "2026-06-16",
    "page_count": {"low": BASE - 5_000, "anchor": BASE, "high": BASE + 7_000},
    "multipliers": {"geographies": 1, "scenarios": 3, "environments": 1},
    "cadence_layers": LAYERS, "buffer_pct": 0.15, "tiers": TIERS,
    "per_domain": PER_DOMAIN,
    "rollup": {"spiral_adjusted_anchor": BASE},
}


# ---- emulator: pure-Python mirror of the workbook formulas (no openpyxl recalc) ----
def emulate(base, geos, scenarios, env, layers, buffer_pct, tiers):
    combined = base * geos * scenarios * env
    layer_runs = [round((combined * L["pct"]) * L["runs_per_year"], 2) for L in layers]
    predicted = round(sum(layer_runs) + combined * buffer_pct)
    los, his, rates, lo = [], [], [], 0
    for t in tiers:
        los.append(lo); his.append(lo + t["limit"]); rates.append(t["pricePerPage"]); lo += t["limit"]
    his[-1] = 10**12
    price = round(sum(max(0, min(predicted, his[i]) - los[i]) * rates[i] for i in range(len(tiers))), 2)
    return {"combined": combined, "predicted": predicted, "price": price}


def _cs_anchor(data):
    out = cs.compute({"page_count": data["page_count"], "multipliers": data["multipliers"],
                      "cadence_layers": data["cadence_layers"], "buffer_pct": data["buffer_pct"],
                      "tiers": data["tiers"]})
    return out["anchor"]


# ---- sheet order / names ----
def test_sheet_order_and_names():
    assert bm.build_workbook(DATA).sheetnames == ["Scope Detail", "Scope of Work", "Pricing", "Sample pages"]


# ---- Scope Detail ----
def test_scope_detail_headers_and_levers():
    ws = bm.build_workbook(DATA)["Scope Detail"]
    hdr = [c.value for c in ws[3]]
    assert hdr[:6] == ["Property (domain)", "Pages", "% of total", "Include in scope?", "Sample Size", "Notes"]
    # first data row: Include? defaults TRUE, Sample Size defaults 1.0 (100%), % of total is a live formula
    assert ws["D4"].value is True
    assert ws["E4"].value == 1.0
    assert str(ws["C4"].value).startswith("=B4/SUM(")


def test_scope_detail_top20_then_aggregate_at_bottom():
    ws = bm.build_workbook(DATA)["Scope Detail"]
    # 20 individual domains (rows 4..23) + 1 aggregate row at the BOTTOM (row 24)
    assert ws["A4"].value == "d0.com"          # largest first
    assert ws["A23"].value == "d19.com"        # 20th largest
    agg = ws["A24"].value
    assert agg.startswith("(") and "additional domains" in agg and "aggregated" in agg
    assert "3 additional" in agg               # 23 - 20 = 3 aggregated
    assert ws["B24"].value == 70 + 60 + 50     # summed pages of the 3 smallest = 180


# ---- Scope of Work ----
def test_total_pages_found_is_sumproduct():
    ws = bm.build_workbook(DATA)["Scope of Work"]
    f = ws["B6"].value
    text = getattr(f, "text", f)               # ArrayFormula or str
    assert "SUMPRODUCT" in text and "'Scope Detail'!D4:D24" in text and "B4:B24" in text and "E4:E24" in text


def test_multiplier_inputs_and_combined():
    ws = bm.build_workbook(DATA)["Scope of Work"]
    assert ws["B7"].value == 1 and ws["B8"].value == 3 and ws["B9"].value == 1
    assert ws["B10"].value == "=B6*B7*B8*B9"


def test_cadence_table_columns_and_recommended_cadence_word():
    ws = bm.build_workbook(DATA)["Scope of Work"]
    hdr = [c.value for c in ws[13]]
    assert hdr == ["Recommended Monitor Layer", "Recommended Cadence", "Why",
                   "% of combined pages", "Runs/yr", "Pages each run", "Scans/yr"]
    assert ws["A14"].value == "Baseline inventory" and ws["B14"].value == "Yearly"
    assert ws["A15"].value == "High Priority" and ws["B15"].value == "Weekly"
    assert ws["D14"].value == 1.0 and ws["E14"].value == 1
    assert ws["F14"].value == "=$B$10*D14"
    assert ws["G14"].value == "=ROUND(F14*E14,2)"


def test_buffer_is_a_row_and_total_includes_it():
    ws = bm.build_workbook(DATA)["Scope of Work"]
    # 4 layers → rows 14..17; buffer row 18; total row 19
    assert ws["A18"].value == "Buffer %"
    assert ws["D18"].value == 0.15
    assert ws["F18"].value == "=$B$10*D18"
    assert ws["G18"].value == "=F18"
    assert ws["A19"].value == "Total annual page-scans (predicted)"
    assert ws["G19"].value == "=ROUND(SUM(G14:G18),0)"
    # no separate purchased row
    blob = "\n".join(str(c.value) for row in ws.iter_rows() for c in row if c.value)
    assert "Purchased page-scans" not in blob


def test_investment_references_pricing_total():
    ws = bm.build_workbook(DATA)["Scope of Work"]
    assert ws["B21"].value == "='Pricing'!E11"   # 6 tiers → total at E11


# ---- Pricing ----
def test_pricing_table_and_reference_to_predicted_total():
    ws = bm.build_workbook(DATA)["Pricing"]
    assert ws["B5"].value == 0 and ws["C5"].value == 1_000 and ws["D5"].value == 0.0
    assert ws["B6"].value == 1_000 and ws["C6"].value == 51_000 and ws["D6"].value == 0.17
    assert ws["C10"].value == 10**12 and ws["D10"].value == 0.03
    assert ws["E5"].value == "=MAX(0, MIN('Scope of Work'!$G$19, C5) - B5) * D5"
    assert ws["E11"].value == "=ROUND(SUM(E5:E10),2)"


# ---- emulator-vs-engine invariant ----
def test_emulator_matches_engine_at_anchor():
    a = _cs_anchor(DATA)
    e = emulate(BASE, 1, 3, 1, LAYERS, 0.15, TIERS)
    assert e["combined"] == a["combined_pages"]
    assert e["predicted"] == a["predicted_scans"]
    assert e["price"] == a["price"]["total"]


def test_emulator_matches_engine_under_perturbations():
    for mutate, buf in (
        (lambda L: L, 0.0),
        (lambda L: [{**l, "pct": 0.0} if l["name"] == "Low Priority Pages" else l for l in L], 0.15),
        (lambda L: [{**l, "pct": 0.30} if l["name"] == "Moderate Priority Pages" else l for l in L], 0.10),
    ):
        layers = mutate(json.loads(json.dumps(LAYERS)))
        d = json.loads(json.dumps(DATA)); d["cadence_layers"] = layers; d["buffer_pct"] = buf
        a = _cs_anchor(d)
        e = emulate(BASE, 1, 3, 1, layers, buf, TIERS)
        assert e["predicted"] == a["predicted_scans"], f"predicted mismatch {layers} buf={buf}"
        assert e["price"] == a["price"]["total"], f"price mismatch {layers} buf={buf}"


def test_total_row_and_pricing_track_layer_and_tier_counts():
    # 3 layers + 5 tiers → buffer row 17, total row 18; pricing total at E10
    d = json.loads(json.dumps(DATA))
    d["cadence_layers"] = json.loads(json.dumps(LAYERS))[:3]
    d["tiers"] = cs.BAKED_TIERS[:-1]
    wb = bm.build_workbook(d)
    sow = wb["Scope of Work"]
    assert sow["A17"].value == "Buffer %"
    assert sow["G18"].value == "=ROUND(SUM(G14:G17),0)"
    assert sow["B21"].value == "='Pricing'!E10"
    assert wb["Pricing"]["E10"].value == "=ROUND(SUM(E5:E9),2)"
    assert wb["Pricing"]["E5"].value == "=MAX(0, MIN('Scope of Work'!$G$18, C5) - B5) * D5"


# ---- clean by construction ----
def test_all_sheets_clean_of_internal_terms():
    import customer_clean
    wb = bm.build_workbook(DATA)
    blob = "\n".join(str(v) for ws in wb.worksheets for row in ws.iter_rows(values_only=True)
                     for v in row if v is not None).lower()
    for term in customer_clean.FORBIDDEN:
        assert term not in blob, f"internal term leaked: {term}"


def test_guard_rejects_internal_layer_name():
    d = json.loads(json.dumps(DATA)); d["cadence_layers"][0]["name"] = "Spiral baseline"
    with pytest.raises(ValueError):
        bm.build_workbook(d)


# ---- no protection ----
def test_sheets_are_not_protected():
    wb = bm.build_workbook(DATA)
    for name in ("Scope Detail", "Scope of Work"):
        assert wb[name].protection.sheet is False


# ---- sample pages ----
def test_sample_pages_render():
    ws = bm.build_workbook(DATA)["Sample pages"]
    blob = "\n".join(str(c.value) for row in ws.iter_rows() for c in row if c.value)
    assert "https://d0.com/" in blob
