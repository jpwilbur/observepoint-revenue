# Scope of Work model (engine + workbook) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the deterministic engine and the workbook builder so the customer deliverable is the **Scope of Work** workbook from the Gallagher template — a domain-driven page total, per-domain in-scope/sample-size levers, a 4-layer + additive-buffer cadence, and an exact graduated price.

**Architecture:** `compute_scope.py` stays the single source of truth but switches the buffer from a multiplier to an additive cadence row and prices the predicted total directly (no purchased/contract split). `build_model.py` is rewritten to emit the template's 4-sheet layout (Scope Detail · Scope of Work · Pricing · Sample pages) with live Excel formulas. A dependency-free Python emulator of the workbook formulas is asserted equal to `compute_scope` at the anchor and under perturbations.

**Tech Stack:** Python 3, `openpyxl` (xlsx), `pytest`. Interpreter: `/opt/homebrew/bin/python3` (the only one with `openpyxl`/`pytest`).

**Scope of THIS plan:** Phases 1–2 only (engine + workbook). Phase 3 (Scope-of-Work-first flow, `.work/` relocation, docs) and Phase 4 (`read_scope_of_work.py` + integrity validation + `build_proposal` rework) are separate follow-on plans. This plan leaves `build_proposal.py` and its tests untouched and green.

**Spec:** `docs/superpowers/specs/2026-06-16-scope-of-work-first-redesign-design.md`

---

## File Structure

- **Modify** `observepoint-revenue/skills/scope-calculator/scripts/compute_scope.py` — additive-buffer model; add `total_pages_found`; remove `apply_buffer`, `purchased_scans`, `tier_changed_by_buffer`, `recommended_contract`/`_recommended_contract`. Keep `graduated_price`, `scans_for_price`, `classify_tier`, `use_case_pages`, `annual_scans`.
- **Modify** `observepoint-revenue/skills/scope-calculator/scripts/build_model.py` — full rewrite to the Scope of Work layout.
- **Modify** `observepoint-revenue/tests/test_compute_scope.py` — rework for the additive-buffer model.
- **Modify** `observepoint-revenue/tests/test_build_model.py` — rework for the new layout + new emulator.

Run all tests with: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q`

---

## Task 1: Engine — `total_pages_found` helper

**Files:**
- Modify: `observepoint-revenue/skills/scope-calculator/scripts/compute_scope.py`
- Test: `observepoint-revenue/tests/test_compute_scope.py`

- [ ] **Step 1: Add the failing test**

Add to `tests/test_compute_scope.py` (after the imports / before `test_baked_tiers_shape`):

```python
def test_total_pages_found_defaults_all_in_full_sample():
    per_domain = [
        {"hostname": "a.com", "defensible_pages": 1000},
        {"hostname": "b.com", "defensible_pages": 500},
    ]
    # no include/sample keys → default include=True, sample=1.0
    assert cs.total_pages_found(per_domain) == 1500


def test_total_pages_found_respects_include_and_sample():
    per_domain = [
        {"hostname": "a.com", "defensible_pages": 1000, "include": True,  "sample_size": 0.5},
        {"hostname": "b.com", "defensible_pages": 500,  "include": False, "sample_size": 1.0},
        {"hostname": "c.com", "defensible_pages": 200,  "include": True,  "sample_size": 1.0},
    ]
    # 1000*0.5 + (b excluded) + 200*1.0 = 700
    assert cs.total_pages_found(per_domain) == 700


def test_total_pages_found_accepts_pages_alias():
    # the reader may pass 'pages' instead of 'defensible_pages'
    assert cs.total_pages_found([{"hostname": "a.com", "pages": 300}]) == 300
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_compute_scope.py -q -k total_pages_found`
Expected: FAIL — `AttributeError: module 'compute_scope' has no attribute 'total_pages_found'`

- [ ] **Step 3: Implement `total_pages_found`**

In `compute_scope.py`, add this function right after `use_case_pages` (around line 90):

```python
def total_pages_found(per_domain):
    """Σ over domains of (in_scope ? pages × sample_size : 0).

    Drives the Scope of Work's 'Total Pages Found' (the workbook does this as a SUMPRODUCT).
    Defaults: include=True, sample_size=1.0 (so the total equals the anchor when untouched).
    Accepts 'defensible_pages' or 'pages' as the per-domain count key."""
    total = 0.0
    for d in per_domain:
        if not d.get("include", True):
            continue
        pages = d.get("defensible_pages", d.get("pages", 0)) or 0
        total += pages * d.get("sample_size", 1.0)
    return round(total)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_compute_scope.py -q -k total_pages_found`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
git add observepoint-revenue/skills/scope-calculator/scripts/compute_scope.py observepoint-revenue/tests/test_compute_scope.py
git commit -m "feat(compute_scope): add total_pages_found derivation helper"
```

---

## Task 2: Engine — additive-buffer model

Switch the buffer from a multiplier to an additive cadence component, price the predicted total directly, and remove the purchased/contract split.

**Files:**
- Modify: `observepoint-revenue/skills/scope-calculator/scripts/compute_scope.py`
- Test: `observepoint-revenue/tests/test_compute_scope.py`

- [ ] **Step 1: Rework the engine tests (failing)**

In `tests/test_compute_scope.py`:

(a) **Delete** these now-obsolete tests entirely: `test_apply_buffer`, `test_apply_buffer_zero_scans`, `test_compute_buffer_changes_purchased`, `test_compute_recommended_contract`, `test_tier_changed_by_buffer_true_when_buffer_straddles_boundary`, `test_tier_changed_by_buffer_false_same_tier`, `test_tier_changed_by_buffer_false_when_buffer_stays_in_tier`.

(b) **Replace** `test_compute_anchor_calibration` with:

```python
def test_compute_anchor_calibration():
    out = cs.compute(BASE_INPUTS)
    a = out["anchor"]
    assert a["combined_pages"] == 1_182_000
    assert a["predicted_scans"] == 1_664_256        # buffer_pct=0 → predicted == layer sum
    assert "purchased_scans" not in a               # retired
    assert a["tier"] == "professional"
    assert a["price"]["total"] == 133_030.24
    assert a["implied_blended_frequency"] == round(1_664_256 / 1_182_000, 3)
    assert out["recommended_quote"]["price_total"] == 133_030.24
    assert out["recommended_quote"]["predicted_scans"] == 1_664_256
    assert "recommended_contract" not in out        # retired
    assert out["pricing_source"].startswith("baked")
```

(c) **Replace** `test_compute_range_is_monotonic` with:

```python
def test_compute_range_is_monotonic():
    out = cs.compute(BASE_INPUTS)
    lo, hi = out["range"]["low"], out["range"]["high"]
    assert lo["predicted_scans"] < out["anchor"]["predicted_scans"] < hi["predicted_scans"]
    assert lo["price_total"] < out["anchor"]["price"]["total"] < hi["price_total"]
```

(d) **Add** the additive-buffer test:

```python
def test_buffer_is_additive_not_a_multiplier():
    # combined = 1,182,000; layer sum (calibration) = 1,664,256.
    # additive buffer adds round(combined * 0.15) = 177,300 → predicted 1,841,556.
    out = cs.compute(dict(BASE_INPUTS, buffer_pct=0.15))
    a = out["anchor"]
    assert a["buffer_scans"] == round(1_182_000 * 0.15)     # 177,300
    assert a["predicted_scans"] == 1_664_256 + 177_300       # 1,841,556
    assert a["price"]["total"] > 133_030.24                  # more scans → higher price
```

- [ ] **Step 2: Run to verify the new/edited tests fail**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_compute_scope.py -q`
Expected: FAILs on `combined_pages`/`buffer_scans`/`recommended_quote["predicted_scans"]` not present (and the removed names are gone).

- [ ] **Step 3: Rework `_compute_one` and `compute`**

In `compute_scope.py`:

(a) **Delete** `apply_buffer` (the `def apply_buffer(...)` block) and `_recommended_contract` (the `def _recommended_contract(...)` block).

(b) **Replace** `_compute_one` with:

```python
def _compute_one(base, multipliers, layers, buffer_pct, tiers):
    combined = use_case_pages(base, multipliers.get("geographies", 1),
                              multipliers.get("scenarios", 1),
                              multipliers.get("environments", 1))
    sc = annual_scans(combined, layers)
    # Buffer is ADDITIVE (mirrors the workbook's Buffer row = combined × buffer%, one pass).
    # Sum the per-layer 2dp runs + the buffer, then round once — matches G19=ROUND(SUM(G14:G18),0).
    layer_sum = sum(l["runs"] for l in sc["by_layer"])
    predicted = round(layer_sum + combined * buffer_pct)
    return {
        "base_pages": base,
        "combined_pages": round(combined),
        "buffer_pct": buffer_pct,
        "buffer_scans": round(combined * buffer_pct),
        "predicted_scans": predicted,
        "cadence_by_layer": sc["by_layer"],
        "implied_blended_frequency": round(predicted / combined, 3) if combined else 0,
        "tier": classify_tier(predicted),
        "price": graduated_price(predicted, tiers),
    }
```

(c) In `compute`, **replace** the `range`, `recommended_quote`, and `recommended_contract` block (the `return {...}` body from `"range":` through `"recommended_contract": ...`) with:

```python
        "range": {
            "low": {"predicted_scans": low["predicted_scans"],
                    "price_total": low["price"]["total"]},
            "high": {"predicted_scans": high["predicted_scans"],
                     "price_total": high["price"]["total"]},
        },
        "recommended_quote": {
            "predicted_scans": anchor["predicted_scans"],
            "price_total": anchor["price"]["total"],
            "tier": anchor["tier"],
        },
    }
```

(Leave the `customer`/`use_case`/`pricing_source`/`confidence`/`multipliers`/`anchor` keys above `range` unchanged.)

- [ ] **Step 4: Run the full engine suite**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_compute_scope.py -q`
Expected: PASS. (`test_scans_for_price_*`, `test_graduated_*`, `test_classify_tier_boundaries`, `test_use_case_pages`, `test_annual_scans_*`, the friendly-error and why-passthrough tests all still pass; `scans_for_price`/`classify_tier`/`graduated_price` are unchanged.)

- [ ] **Step 5: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
git add observepoint-revenue/skills/scope-calculator/scripts/compute_scope.py observepoint-revenue/tests/test_compute_scope.py
git commit -m "feat(compute_scope): additive buffer; price predicted total directly; retire purchased/contract/tier-flag"
```

---

## Task 3: Workbook — rewrite tests for the Scope of Work layout (failing)

Replace `tests/test_build_model.py` wholesale with the new-layout suite + new emulator. (The old file asserts the retired Investment Model layout.)

**Files:**
- Test: `observepoint-revenue/tests/test_build_model.py` (full replace)

- [ ] **Step 1: Replace the test file**

Overwrite `tests/test_build_model.py` with:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_build_model.py -q`
Expected: many FAILs (the current `build_model.py` emits the old "Investment Model" layout).

- [ ] **Step 3: Commit the failing tests**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
git add observepoint-revenue/tests/test_build_model.py
git commit -m "test(build_model): new Scope of Work layout suite + additive-buffer emulator (red)"
```

---

## Task 4: Workbook — rewrite `build_model.py` to the Scope of Work layout

**Files:**
- Modify: `observepoint-revenue/skills/scope-calculator/scripts/build_model.py` (full replace)
- Test: (Task 3's suite)

- [ ] **Step 1: Replace `build_model.py`**

Overwrite `skills/scope-calculator/scripts/build_model.py` with:

```python
"""Live Excel **Scope of Work** workbook (.xlsx) for the scope-calculator.

Customer-facing workbook driven by the Scope Detail tab: Total Pages Found is a SUMPRODUCT over
in-scope domains × sample size; Combined = × geographies × consent × environments; a 4-(or N-)layer
priority cadence plus an additive Buffer row; price = graduated tiers on the predicted total.
Yellow cells mark the editable levers; sheets are NOT protected (integrity is validated at
proposal-generation time instead). The formulas reproduce compute_scope.py exactly on recalc, and
a dependency-free emulator asserts that in the tests.

Sheets (in order): Scope Detail · Scope of Work · Pricing · Sample pages.
"""
import pathlib
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.formula import ArrayFormula

import customer_clean

# ---------- theme ----------
FONT = "Montserrat"
DARK, YELLOW, LIGHT, GRAY, WHITE = "1E1E1E", "F2CD14", "F2F2F2", "5C5C5C", "FFFFFF"
INPUT_FILL = "FFF7CC"   # pale yellow — marks the editable levers
LOGO = pathlib.Path(__file__).resolve().parent.parent / "assets" / "op-logo.png"

_THIN = Side(style="thin", color="D9D9D9")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_YBAR = Side(style="thick", color=YELLOW)

TOP_N = 20   # individual domains listed; the rest collapse into one bottom aggregate row

# Runs/yr → customer-facing cadence word.
_CADENCE_WORD = {1: "Yearly", 4: "Quarterly", 12: "Monthly", 26: "Bi-weekly", 52: "Weekly", 365: "Daily"}


def _cadence_word(runs):
    return _CADENCE_WORD.get(runs, f"{runs}×/yr")


def _f(bold=False, color=DARK, size=10):
    return Font(name=FONT, bold=bold, color=color, size=size)


def _fill(hexc):
    return PatternFill("solid", fgColor=hexc)


def _widths(ws, widths):
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w


def _title(ws, text, span, row):
    c = ws.cell(row, 1, text)
    c.font = _f(bold=True, size=15)
    for i in range(span):
        ws.cell(row, i + 1).border = Border(bottom=_YBAR)
    ws.row_dimensions[row].height = 22
    return row + 2


def _headers(ws, headers, row):
    for i, h in enumerate(headers):
        c = ws.cell(row, i + 1, h)
        c.font = _f(bold=True, color=WHITE)
        c.fill = _fill(DARK)
        c.border = _BORDER
        c.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[row].height = 26
    return row + 1


def _lever(cell, fmt):
    """Style a cell as an editable yellow lever (no protection — sheets are unprotected)."""
    cell.fill = _fill(INPUT_FILL)
    cell.number_format = fmt
    cell.font = _f()


# ---------- Scope Detail (first sheet) ----------

def _scope_detail(wb, data):
    ws = wb.active
    ws.title = "Scope Detail"
    _widths(ws, [44, 14, 12, 16, 12, 30])
    r = _title(ws, "Scope detail", 6, 1)
    hdr_row = r
    r = _headers(ws, ["Property (domain)", "Pages", "% of total",
                      "Include in scope?", "Sample Size", "Notes"], r)
    ws.freeze_panes = ws.cell(r, 1)

    ordered = sorted(data["per_domain"], key=lambda x: -x["defensible_pages"])
    individual = ordered[:TOP_N]
    tail = ordered[TOP_N:]
    rows = [(d["hostname"], d["defensible_pages"]) for d in individual]
    if tail:
        rows.append((f"({len(tail)} additional domains — long tail, aggregated)",
                     sum(d["defensible_pages"] for d in tail)))

    first = r
    last = r + len(rows) - 1
    for i, (host, pages) in enumerate(rows):
        n = r + i
        alt = (i % 2 == 1)
        fill = LIGHT if alt else WHITE
        c = ws.cell(n, 1, host); c.font = _f(); c.fill = _fill(fill); c.border = _BORDER
        c = ws.cell(n, 2, pages); c.font = _f(); c.fill = _fill(fill); c.border = _BORDER
        c.number_format = "#,##0"
        c = ws.cell(n, 3, f"=B{n}/SUM($B${first}:$B${last})")
        c.font = _f(); c.fill = _fill(fill); c.border = _BORDER; c.number_format = "0.0%"
        c = ws.cell(n, 4, True); c.border = _BORDER; c.alignment = Alignment(horizontal="center")
        _lever(c, "General")
        c = ws.cell(n, 5, 1.0); c.border = _BORDER
        _lever(c, "0%")
        c = ws.cell(n, 6, None); c.border = _BORDER; c.fill = _fill(fill)
    return {"first": first, "last": last}


# ---------- Scope of Work tab ----------

def _scope_of_work(wb, data, detail):
    ws = wb.create_sheet("Scope of Work")
    m = data.get("multipliers", {})
    layers = data["cadence_layers"]
    f, l = detail["first"], detail["last"]

    if LOGO.exists():
        try:
            from openpyxl.drawing.image import Image as XLImage
            img = XLImage(str(LOGO)); img.width, img.height = 200, 31
            ws.add_image(img, "A1")
        except Exception:
            pass
    ws.row_dimensions[1].height = 30
    ws["A2"] = "Scope of Work"; ws["A2"].font = _f(bold=True, size=16)
    ws["A3"] = f"Prepared for {data.get('customer', '')}"; ws["A3"].font = _f(color=GRAY, size=10)

    ws["A5"] = "INPUTS"; ws["A5"].font = _f(bold=True, size=11)

    def label(row, text, note):
        ws[f"A{row}"] = text; ws[f"A{row}"].font = _f(bold=True)
        ws[f"C{row}"] = note; ws[f"C{row}"].font = _f(color=GRAY, size=9)

    label(6, "Total Pages Found", "Sum of in-scope domain pages, linked from Scope detail")
    b6 = ws["B6"]
    b6.value = ArrayFormula("B6", f"=SUMPRODUCT(--'Scope Detail'!D{f}:D{l},"
                                  f"'Scope Detail'!B{f}:B{l},'Scope Detail'!E{f}:E{l})")
    b6.number_format = "#,##0"; b6.font = _f()

    label(7, "Geographies", "State / Country / Jurisdiction")
    _lever(ws["B7"], '"× "0'); ws["B7"].value = m.get("geographies", 1)
    label(8, "Consent scenarios", "Opt-out/GPC/Default consent/etc.")
    _lever(ws["B8"], '"× "0'); ws["B8"].value = m.get("scenarios", 1)
    label(9, "Environments", "Prod / Pre-Prod / Authenticated / etc.")
    _lever(ws["B9"], '"× "0'); ws["B9"].value = m.get("environments", 1)

    ws["A10"] = "Combined Page Total"; ws["A10"].font = _f(bold=True)
    ws["B10"] = "=B6*B7*B8*B9"; ws["B10"].number_format = "#,##0"
    ws["C10"] = '=TEXT(B6,"#,##0")&" × "&B7&" × "&B8&" × "&B9&" = "&TEXT(B10,"#,##0")'
    ws["C10"].font = _f(color=GRAY, size=9)

    ws["A12"] = "MONITORING CADENCE"; ws["A12"].font = _f(bold=True, size=11)
    _headers(ws, ["Recommended Monitor Layer", "Recommended Cadence", "Why",
                  "% of combined pages", "Runs/yr", "Pages each run", "Scans/yr"], 13)

    row = 14
    for L in layers:
        ws.cell(row, 1, L["name"]).font = _f()
        ws.cell(row, 2, _cadence_word(L["runs_per_year"])).font = _f()
        c = ws.cell(row, 3, L.get("why", "")); c.font = _f(); c.alignment = Alignment(wrap_text=True)
        _lever(ws.cell(row, 4, L["pct"]), "0.##%")
        _lever(ws.cell(row, 5, L["runs_per_year"]), "#,##0")
        ws.cell(row, 6, f"=$B$10*D{row}").number_format = "#,##0"
        ws.cell(row, 7, f"=ROUND(F{row}*E{row},2)").number_format = "#,##0"
        row += 1

    buf = row
    ws.cell(buf, 1, "Buffer %").font = _f(bold=True)
    c = ws.cell(buf, 3, "Ad-hoc testing and projects regularly push scanning needs past the "
                        "scheduled monitoring."); c.font = _f(); c.alignment = Alignment(wrap_text=True)
    _lever(ws.cell(buf, 4, data.get("buffer_pct", 0.0)), "0%")
    ws.cell(buf, 6, f"=$B$10*D{buf}").number_format = "#,##0"
    ws.cell(buf, 7, f"=F{buf}").number_format = "#,##0"

    total = buf + 1
    ws.cell(total, 1, "Total annual page-scans (predicted)").font = _f(bold=True)
    g = ws.cell(total, 7, f"=ROUND(SUM(G14:G{buf}),0)"); g.font = _f(bold=True); g.number_format = "#,##0"

    import compute_scope as _cs
    tiers = data.get("tiers") or _cs.BAKED_TIERS
    price_total_row = 5 + len(tiers)
    inv = total + 2
    ws.cell(inv, 1, "Recommended investment / year (USD)").font = _f(bold=True, size=12)
    b = ws.cell(inv, 2, f"='Pricing'!E{price_total_row}")
    b.number_format = "$#,##0"; b.fill = _fill(YELLOW); b.font = _f(bold=True, size=12)

    ws.cell(inv + 2, 1, "Yellow cells are editable — change them and the totals/price "
                        "update automatically.").font = _f(color=GRAY, size=9)
    _widths(ws, [34, 16, 46, 18, 10, 14, 14])
    return {"predicted_row": total}


# ---------- Pricing ----------

def _pricing(wb, data, sow):
    import compute_scope as _cs
    tiers = data.get("tiers") or _cs.BAKED_TIERS
    pr = sow["predicted_row"]
    ws = wb.create_sheet("Pricing")
    ws["A2"] = "ObservePoint published pricing — graduated tiers"
    ws["A2"].font = _f(bold=True, size=12)
    _headers(ws, ["Band", "From (scans)", "To (scans)", "Rate / scan", "Cost"], 4)
    lo = 0
    for i, t in enumerate(tiers):
        n = 5 + i
        hi = 10 ** 12 if i == len(tiers) - 1 else lo + t["limit"]
        ws.cell(n, 1, i + 1).font = _f()
        ws.cell(n, 2, lo).number_format = "#,##0"
        ws.cell(n, 3, hi).number_format = "#,##0"
        ws.cell(n, 4, t["pricePerPage"]).number_format = "$#,##0.00"
        ws.cell(n, 5, f"=MAX(0, MIN('Scope of Work'!$G${pr}, C{n}) - B{n}) * D{n}").number_format = "$#,##0.00"
        lo += t["limit"]
    total_row = 5 + len(tiers)
    ws.cell(total_row, 1, "Recommended investment / year").font = _f(bold=True)
    ws.cell(total_row, 5, f"=ROUND(SUM(E5:E{total_row - 1}),2)").number_format = "$#,##0"
    ws.cell(total_row + 2, 1, "Tier bands and per-scan rates mirror ObservePoint's published "
                              "pricing model.").font = _f(color=GRAY, size=9)
    _widths(ws, [8, 16, 16, 14, 16])


# ---------- Sample pages ----------

def _sample_pages(wb, data):
    ws = wb.create_sheet("Sample pages")
    _widths(ws, [34, 70])
    r = _title(ws, "Sample pages — real examples found on each property", 2, 1)
    note = ws.cell(r, 1, "A handful of real example pages per property (the largest by page count) "
                         "— so you can see these are genuine pages.")
    note.font = _f(color=GRAY, size=9); note.alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
    ws.row_dimensions[r].height = 26
    r = _headers(ws, ["Property (domain)", "Example page URL"], r + 1)
    ws.freeze_panes = ws.cell(r, 1)
    any_rows, alt = False, False
    for d in sorted(data["per_domain"], key=lambda x: -x["defensible_pages"]):
        for s in d.get("url_samples", []):
            fill = LIGHT if alt else WHITE
            ws.cell(r, 1, d["hostname"]).fill = _fill(fill)
            ws.cell(r, 2, s).fill = _fill(fill)
            for col in (1, 2):
                ws.cell(r, col).font = _f(); ws.cell(r, col).border = _BORDER
            r += 1; any_rows = True
        if d.get("url_samples"):
            alt = not alt
    if not any_rows:
        ws.cell(r, 1, "(no per-URL samples captured)").font = _f()


# ---------- public API ----------

def build_workbook(data):
    """Build the live Scope of Work workbook. Sheets: Scope Detail · Scope of Work · Pricing · Sample pages.
    No sheet protection — yellow cells mark the levers; integrity is validated at proposal time."""
    layers = data.get("cadence_layers", [])
    if not (1 <= len(layers) <= 6):
        raise ValueError(f"scope of work: expected 1–6 cadence layers; got {len(layers)}.")
    strings = [L.get("name", "") for L in layers] + [L.get("why", "") for L in layers]
    customer_clean.assert_clean(strings, where="scope of work")

    wb = Workbook()
    detail = _scope_detail(wb, data)
    sow = _scope_of_work(wb, data, detail)
    _pricing(wb, data, sow)
    _sample_pages(wb, data)
    return wb


_DOC_REF = "see references/deliverables-mapping.md"
_REQUIRED = {
    "page_count": "{low, anchor, high}",
    "cadence_layers": "[{name, pct, runs_per_year}, …]",
    "per_domain": "[{hostname, defensible_pages}, …]",
}


def _validate(data):
    if not isinstance(data, dict):
        sys.exit(f"scope-calculator: malformed model inputs — expected a JSON object; {_DOC_REF}")
    for key, shape in _REQUIRED.items():
        if key not in data or data[key] in (None, {}, []):
            sys.exit(f"scope-calculator: missing/malformed '{key}' — expected {shape}; {_DOC_REF}")
    pc = data["page_count"]
    if not isinstance(pc, dict) or any(k not in pc for k in ("low", "anchor", "high")):
        sys.exit(f"scope-calculator: missing/malformed 'page_count' — expected "
                 f"{_REQUIRED['page_count']}; {_DOC_REF}")


def main(argv):
    import json
    if len(argv) > 1:
        with open(argv[1]) as fh:
            raw = fh.read()
    else:
        raw = sys.stdin.read()
    out = argv[2] if len(argv) > 2 else "scope-of-work.xlsx"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f"scope-calculator: model inputs are not valid JSON ({e}); {_DOC_REF}")
    _validate(data)
    build_workbook(data).save(out)
    print(out)


if __name__ == "__main__":
    main(sys.argv)
```

- [ ] **Step 2: Run the build_model suite**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_build_model.py -q`
Expected: PASS (all tests from Task 3).

- [ ] **Step 3: Run the FULL suite (no regressions elsewhere)**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q`
Expected: PASS. (`build_proposal`, `build_internal_evidence`, `anchor_guard`, etc. are untouched. `build_internal_evidence` reads `pricing` with `.get` defaults so the engine change doesn't break it.)

- [ ] **Step 4: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
git add observepoint-revenue/skills/scope-calculator/scripts/build_model.py
git commit -m "feat(build_model): rewrite to the Scope of Work layout (Scope Detail levers, SUMPRODUCT total, additive buffer row, no protection)"
```

---

## Task 5: Smoke-build a real workbook and eyeball it

A non-test sanity check that the workbook opens and the headline numbers are right.

**Files:** none (manual verification)

- [ ] **Step 1: Generate a workbook from a fixture**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin/observepoint-revenue/skills/scope-calculator/scripts"
/opt/homebrew/bin/python3 - <<'PY'
import json, build_model as bm
data = {
  "customer": "Smoke Test", "date": "2026-06-16",
  "page_count": {"low": 44850, "anchor": 49850, "high": 56850},
  "multipliers": {"geographies": 1, "scenarios": 3, "environments": 1},
  "buffer_pct": 0.15, "tiers": __import__("compute_scope").BAKED_TIERS,
  "cadence_layers": [
    {"name":"Baseline inventory","why":"A full sweep so nothing on the site is invisible — your lay of the land.","pct":1.0,"runs_per_year":1},
    {"name":"High Priority","why":"Aligned to release cadence — catches tags/consent breaking shortly after a deploy.","pct":0.015,"runs_per_year":52},
    {"name":"Moderate Priority Pages","why":"Monthly audit of the meaningful body of the site for tag health & consent compliance.","pct":0.075,"runs_per_year":12},
    {"name":"Low Priority Pages","why":"A quarterly sweep of the long tail so low-traffic pages don't become blind spots.","pct":0.20,"runs_per_year":4}],
  "per_domain": [{"hostname": f"d{i}.com", "defensible_pages": p, "url_samples":[f"https://d{i}.com/"]}
                 for i,p in enumerate([9000,8000,7000,6000,5000,4000,3000,2000,1000,900,800,700,600,500,400,300,200,100,90,80,70,60,50])],
  "rollup": {"spiral_adjusted_anchor": 62270},
}
bm.build_workbook(data).save("/tmp/smoke - Scope of Work.xlsx")
print("wrote /tmp/smoke - Scope of Work.xlsx")
PY
```

- [ ] **Step 2: Confirm formulas + engine number agree**

Run:
```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin/observepoint-revenue/skills/scope-calculator/scripts"
/opt/homebrew/bin/python3 - <<'PY'
import compute_scope as cs
out = cs.compute({
  "page_count":{"low":44850,"anchor":49850,"high":56850},
  "multipliers":{"geographies":1,"scenarios":3,"environments":1},
  "buffer_pct":0.15, "tiers":cs.BAKED_TIERS,
  "cadence_layers":[
    {"name":"Baseline inventory","pct":1.0,"runs_per_year":1},
    {"name":"High Priority","pct":0.015,"runs_per_year":52},
    {"name":"Moderate Priority Pages","pct":0.075,"runs_per_year":12},
    {"name":"Low Priority Pages","pct":0.20,"runs_per_year":4}]})
a = out["anchor"]
print("combined:", a["combined_pages"], "predicted:", a["predicted_scans"], "price:", a["price"]["total"])
PY
```
Expected: prints `combined: 149550 predicted: <N> price: <$>` (149,550 = 49,850 × 3). (Open `/tmp/smoke - Scope of Work.xlsx` in Excel; `Scope of Work!G19` and `B21` should match `predicted` and `price` once Excel recalculates.)

- [ ] **Step 3: No commit** (verification only).

---

## Self-review notes (already folded in)

- **Spec coverage:** additive buffer (Task 2), Total Pages Found / SUMPRODUCT (Tasks 1, 4), Scope Detail levers + bottom aggregate (Task 4 / tests Task 3), Recommended Cadence column + 4-layer default (Task 4), no protection (Task 4), price = predicted total (Task 2). Flow/outputs/docs and the proposal reader are explicitly out of scope (Phases 3–4).
- **Type consistency:** `combined_pages`/`predicted_scans`/`buffer_scans` used identically in engine + emulator; `total_pages_found` signature matches its callers; Pricing references `'Scope of Work'!$G${predicted_row}` everywhere.
- **No placeholders:** every code step is complete.
