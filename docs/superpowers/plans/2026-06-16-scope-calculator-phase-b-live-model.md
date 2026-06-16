# Scope Calculator — Phase B: Live Excel Investment Model — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the static customer evidence workbook with a **live Excel "Investment Model"** — page count, geos, scenarios, environments, buffer, and each frequency layer's % + runs/yr are INPUT cells; pages-per-sweep, per-layer scans, total annual scans, and the graduated price are LIVE FORMULAS that recompute in plain Excel. A customer/AE can flip a frequency off or trim a % and watch the investment update.

**Architecture:** Honors the repo principle — `compute_scope.py` stays the single source of truth for every *quoted* number (chat + .docx). `build_model.py` only *renders* a workbook whose formulas, when Excel evaluates them, reproduce `compute_scope.compute()` exactly. The formulas mirror `compute_scope`'s arithmetic AND its per-step rounding. A dependency-free Python **emulator** (mirroring the exact cell formulas) asserted against `compute_scope` at the anchor + perturbed scenarios is the test gate; formula-string assertions catch a generator that writes the wrong formula.

**Tech Stack:** Python 3 (`/opt/homebrew/bin/python3`), `openpyxl` (formulas + cell protection), `pytest`. No new runtime deps. (Optional bonus: the `formulas` lib for real end-to-end eval if available — skipped if not.)

**Spec:** `docs/superpowers/specs/2026-06-15-scope-calculator-advisor-flow-design.md` §7 (live model), §7.2 (graduated price as formula), §7.4 (single source of truth), §10–§12. Builds on `main` (Phase A merged at `58e6ebb`).

**Run all tests:** `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q` (currently 205 passing).

**Decision (locked):** formula/output cells are LOCKED via sheet protection (no password); input cells are editable + highlighted (Task 4).

---

## Reference: exact sheet layouts & formulas (used by Tasks 1, 2, 4)

These mirror `compute_scope.py`: `use_case_pages = base × geos × scenarios × environments`; per layer `pages = ucp × pct`, `runs = round(pages × runs_per_year, 2)`; `predicted = round(Σ runs)`; `purchased = round(predicted × (1+buffer))`; `graduated_price(purchased)` where each tier `limit` is a band WIDTH.

### Sheet "Investment Model" (1-indexed rows; col A = label, B = value, plus cadence cols A–F)

```
R2  A: "Investment Model"  (title)
R3  A: "Prepared for {customer}"
R5  A: "INPUTS"  (section header; B-col cells in rows 6–9,19 are the editable inputs)
R6  A:"Validated pages"        B6: <anchor>        [INPUT]
R7  A:"Geographies"            B7: <geos>          [INPUT]
R8  A:"Consent scenarios"      B8: <scenarios>     [INPUT]
R9  A:"Environments"           B9: <environments>  [INPUT]
R10 A:"Pages per full sweep"   B10: =B6*B7*B8*B9               [FORMULA]
R12 A:"MONITORING CADENCE"
R13 header: A"Layer" B"Why" C"% of pages" D"Runs/yr" E"Pages each run" F"Scans/yr"
R14..R18  (5 layers, one per row N):
      A:name  B:why  C:<pct> [INPUT]  D:<runs_per_year> [INPUT]
      E{N}: =$B$10*C{N}                         [FORMULA]
      F{N}: =ROUND(E{N}*D{N},2)                 [FORMULA]
R19 A:"Buffer %"               B19: <buffer_pct, default 0>   [INPUT]
R20 A:"Total annual page-scans (predicted)"  F20: =ROUND(SUM(F14:F18),0)         [FORMULA]
R21 A:"Purchased page-scans"   F21: =ROUND(F20*(1+B19),0)     [FORMULA]
R23 A:"Recommended investment / year (USD)"  B23: ='Pricing'!E11   [FORMULA → Pricing total]
```
% cells (C14:C18) use number format `0.##%` (store pct as a fraction, e.g. 0.01); buffer B19 format `0%`. Pages/scan cells `#,##0`; price `$#,##0`.

### Sheet "Pricing" (graduated tiers; references Investment Model purchased-scans `'Investment Model'!$F$21`)

```
R2  A:"ObservePoint published pricing — graduated tiers"
R4  header: A"Band" B"From (scans)" C"To (scans)" D"Rate / scan" E"Cost"
R5..R10  (6 bands; cumulative lower/upper from the tier WIDTHS; last upper = a large sentinel for ∞):
      B{N}=Lo  C{N}=Hi  D{N}=rate
      E{N}: =MAX(0, MIN('Investment Model'!$F$21, C{N}) - B{N}) * D{N}     [FORMULA]
R11 A:"Recommended investment / year"  E11: =ROUND(SUM(E5:E10),2)         [FORMULA]
```
Band rows derived from `tiers` (the fetched/baked widths) by cumulative sum:

| Band | From (Lo) | To (Hi) | Rate |
|---|---|---|---|
| 1 | 0 | 1,000 | 0.00 |
| 2 | 1,000 | 51,000 | 0.17 |
| 3 | 51,000 | 551,000 | 0.12 |
| 4 | 551,000 | 1,551,000 | 0.06 |
| 5 | 1,551,000 | 6,551,000 | 0.04 |
| 6 | 6,551,000 | 1,000,000,000,000 | 0.03 |

The last `Hi` is a large sentinel (1e12) so `MIN(purchased, Hi)` never truncates real inputs — this captures both the final defined band and `graduated_price`'s "tail at the last rate" rule (same rate, 0.03). **Generate Lo/Hi/Rate programmatically from `tiers`** (don't hardcode) so a pricing change flows through: `Lo[0]=0; Hi[i]=Lo[i]+tiers[i].limit; Lo[i+1]=Hi[i]; Hi[last]=10**12`.

### The emulator (mirrors the cells EXACTLY — used in tests, lives in the test file)

```python
def emulate_model(base, geos, scenarios, env, layers, buffer_pct, tiers):
    """Reproduce the Investment Model + Pricing cell formulas in pure Python, including
    compute_scope's per-step rounding. layers: [{pct, runs_per_year}, ...]."""
    sweep = base * geos * scenarios * env                 # =B6*B7*B8*B9
    scans_per_layer = [round((sweep * L["pct"]) * L["runs_per_year"], 2) for L in layers]  # E,F
    predicted = round(sum(scans_per_layer))               # F20
    purchased = round(predicted * (1 + buffer_pct))       # F21
    # graduated price via cumulative Lo/Hi (last Hi = 1e12)
    los, his, rates, lo = [], [], [], 0
    for t in tiers:
        los.append(lo); his.append(lo + t["limit"]); rates.append(t["pricePerPage"]); lo += t["limit"]
    his[-1] = 10**12
    price = round(sum(max(0, min(purchased, his[i]) - los[i]) * rates[i] for i in range(len(tiers))), 2)
    return {"sweep": sweep, "predicted": predicted, "purchased": purchased, "price": price}
```

The invariant test asserts `emulate_model(...) == compute_scope.compute(...)` for the anchor and for perturbations (drop daily layer → its pct=0; halve quarterly pct). Because the emulator is a line-for-line mirror of the cells and equals the engine, the workbook's formulas equal the engine.

---

## File structure (Phase B)

```
skills/scope-calculator/
├── scripts/
│   ├── build_model.py               [NEW]    the live customer workbook (Investment Model + Pricing + Scope detail + Sample pages)
│   ├── build_evidence_appendix.py   [DELETE in Task 5] superseded by build_model.py
│   ├── customer_clean.py            [REUSE]
│   ├── compute_scope.py             [REUSE]  (source of truth; not modified)
│   └── fetch_pricing.py             [REUSE]  (supplies tiers)
├── references/
│   └── deliverables-mapping.md      [MODIFY in Task 5] customer workbook = build_model.py
└── SKILL.md                         [MODIFY in Task 5] Stage 3 invokes build_model.py
tests/
├── test_build_model.py              [NEW]
└── test_build_evidence_appendix.py  [DELETE in Task 5]
```

**Sequencing:** Task 1 (Investment Model + scan invariant) → Task 2 (Pricing + price invariant) → Task 3 (Scope detail + Sample pages, migrated clean) → Task 4 (cell locking) → Task 5 (wire-up + retire appendix). Each task commits independently.

---

## Task 1: `build_model.py` — Investment Model sheet (inputs + scan formulas)

**Files:**
- Create: `skills/scope-calculator/scripts/build_model.py`
- Test: `tests/test_build_model.py`

- [ ] **Step 1: Write the failing tests** (scan side — input cells, key formula strings, and the emulator-vs-engine invariant for scans)

```python
# tests/test_build_model.py
import json, pathlib, sys
import pytest
from openpyxl import load_workbook

import build_model as bm
import compute_scope as cs

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "scope-calculator" / "scripts" / "build_model.py"

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
```

- [ ] **Step 2: Run to verify failure**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_build_model.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'build_model'`.

- [ ] **Step 3: Write `build_model.py` — Investment Model sheet**

Create the module with the openpyxl scaffolding (reuse the theme constants/helpers pattern from the now-deleted-later `build_evidence_appendix.py`: `FONT`, `DARK`/`YELLOW`/`LIGHT`, `_f`, `_fill`, logo embed). Implement `_investment_model(wb, data)` exactly per the layout reference above. Key generator code:

```python
INPUT_FILL = "FFF7CC"   # pale yellow — marks editable input cells

def _investment_model(wb, data):
    ws = wb.active
    ws.title = "Investment Model"
    pc = data["page_count"]; m = data.get("multipliers", {})
    layers = data["cadence_layers"]
    # title
    ws["A2"] = "Investment Model"; ws["A2"].font = _f(bold=True, size=16)
    ws["A3"] = f"Prepared for {data.get('customer','')}"; ws["A3"].font = _f(color=GRAY, size=10)
    ws["A5"] = "INPUTS"; ws["A5"].font = _f(bold=True, size=11)
    def _input(cell, label_row, label, value, fmt="#,##0"):
        ws[f"A{label_row}"] = label; ws[f"A{label_row}"].font = _f(bold=True)
        c = ws[cell]; c.value = value; c.fill = _fill(INPUT_FILL); c.number_format = fmt
        c.font = _f(); return c
    _input("B6", 6, "Validated pages", pc["anchor"])
    _input("B7", 7, "Geographies", m.get("geographies", 1))
    _input("B8", 8, "Consent scenarios", m.get("scenarios", 1))
    _input("B9", 9, "Environments", m.get("environments", 1))
    ws["A10"] = "Pages per full sweep"; ws["A10"].font = _f(bold=True)
    ws["B10"] = "=B6*B7*B8*B9"; ws["B10"].number_format = "#,##0"
    # cadence
    ws["A12"] = "MONITORING CADENCE"; ws["A12"].font = _f(bold=True, size=11)
    for i, h in enumerate(["Layer", "Why", "% of pages", "Runs/yr", "Pages each run", "Scans/yr"]):
        cc = ws.cell(13, i + 1, h); cc.font = _f(bold=True, color=WHITE); cc.fill = _fill(DARK)
    for idx, L in enumerate(layers[:5]):
        n = 14 + idx
        ws.cell(n, 1, L["name"]).font = _f()
        ws.cell(n, 2, L.get("why", "")).font = _f()
        cpct = ws.cell(n, 3, L["pct"]); cpct.fill = _fill(INPUT_FILL); cpct.number_format = "0.##%"
        crun = ws.cell(n, 4, L["runs_per_year"]); crun.fill = _fill(INPUT_FILL); crun.number_format = "#,##0"
        ws.cell(n, 5).value = f"=$B$10*C{n}"; ws.cell(n, 5).number_format = "#,##0"
        ws.cell(n, 6).value = f"=ROUND(E{n}*D{n},2)"; ws.cell(n, 6).number_format = "#,##0"
    # NOTE: this layout fixes 5 cadence rows (14-18). If fewer than 5 layers are supplied,
    # leave the unused rows blank with pct 0 so SUM(F14:F18) stays correct. Assert exactly the
    # 5 canonical layers in normal use (the frequency advisor always supplies 5; dropped = pct 0).
    ws["A19"] = "Buffer %"; ws["A19"].font = _f(bold=True)
    b19 = ws["B19"]; b19.value = data.get("buffer_pct", 0.0); b19.fill = _fill(INPUT_FILL); b19.number_format = "0%"
    ws["A20"] = "Total annual page-scans (predicted)"; ws["A20"].font = _f(bold=True)
    ws["F20"] = "=ROUND(SUM(F14:F18),0)"; ws["F20"].number_format = "#,##0"
    ws["A21"] = "Purchased page-scans"; ws["A21"].font = _f(bold=True)
    ws["F21"] = "=ROUND(F20*(1+B19),0)"; ws["F21"].number_format = "#,##0"
    ws["A23"] = "Recommended investment / year (USD)"; ws["A23"].font = _f(bold=True, size=12)
    ws["B23"] = "='Pricing'!E11"; ws["B23"].number_format = "$#,##0"; ws["B23"].fill = _fill(YELLOW)
    _widths(ws, [34, 30, 14, 12, 16, 14])
```

(Also write `build_workbook(data)` that creates the wb and calls `_investment_model`; Tasks 2–3 add the other sheets to it. For now `build_workbook` builds only the Investment Model so the Task-1 tests pass.)

- [ ] **Step 4: Run to verify pass**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_build_model.py -q`
Expected: PASS (5 tests). If `test_emulator_matches_engine_*` fails, the rounding in the formulas/emulator doesn't match `compute_scope` — re-check `ROUND(...,2)` per layer and `ROUND(SUM,0)` for the total against `compute_scope.annual_scans`.

- [ ] **Step 5: Commit**

```bash
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" add observepoint-revenue/skills/scope-calculator/scripts/build_model.py observepoint-revenue/tests/test_build_model.py
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" commit -m "feat(scope-calculator): live Investment Model sheet (input cells + scan formulas)"
```

---

## Task 2: Pricing helper sheet + live graduated price

**Files:**
- Modify: `skills/scope-calculator/scripts/build_model.py`
- Test: `tests/test_build_model.py`

- [ ] **Step 1: Write failing tests** (append)

```python
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
```

- [ ] **Step 2: Run to verify failure** — `KeyError: 'Pricing'` (sheet not yet created).

- [ ] **Step 3: Implement `_pricing(wb, data)`** in `build_model.py` (derive Lo/Hi/Rate from `data["tiers"]`, write the per-band cost formula + total):

```python
def _pricing(wb, data):
    tiers = data.get("tiers") or __import__("compute_scope").BAKED_TIERS
    ws = wb.create_sheet("Pricing")
    ws["A2"] = "ObservePoint published pricing — graduated tiers"; ws["A2"].font = _f(bold=True, size=12)
    for i, h in enumerate(["Band", "From (scans)", "To (scans)", "Rate / scan", "Cost"]):
        c = ws.cell(4, i + 1, h); c.font = _f(bold=True, color=WHITE); c.fill = _fill(DARK)
    lo = 0
    for i, t in enumerate(tiers):
        n = 5 + i
        hi = lo + t["limit"]
        if i == len(tiers) - 1:
            hi = 10**12     # ∞ sentinel: captures the final band + graduated_price's tail (same rate)
        ws.cell(n, 1, i + 1).font = _f()
        ws.cell(n, 2, lo).number_format = "#,##0"
        ws.cell(n, 3, hi).number_format = "#,##0"
        ws.cell(n, 4, t["pricePerPage"]).number_format = "$#,##0.00"
        ws.cell(n, 5).value = f"=MAX(0, MIN('Investment Model'!$F$21, C{n}) - B{n}) * D{n}"
        ws.cell(n, 5).number_format = "$#,##0.00"
        lo = lo + t["limit"]
    total_row = 5 + len(tiers)            # = 11 for 6 tiers
    ws.cell(total_row, 1, "Recommended investment / year").font = _f(bold=True)
    ws.cell(total_row, 5).value = f"=ROUND(SUM(E5:E{total_row - 1}),2)"
    ws.cell(total_row, 5).number_format = "$#,##0"
    _widths(ws, [22, 16, 16, 14, 16])
```

Add `_pricing(wb, data)` to `build_workbook` AFTER `_investment_model` (so `'Pricing'!E11` exists for the model's B23 reference). **Note:** the tests assume 6 tiers → total row 11 and `B23='Pricing'!E11`. If the tier count differs, `B23` must reference the computed total row. For robustness, compute the total-row reference in `_investment_model` from `len(tiers)` OR assert 6 tiers. Keep it simple: the baked/live tiers are 6 bands; assert that and use E11.

- [ ] **Step 4: Run to verify pass** — `pytest tests/test_build_model.py -q` → PASS. The `test_price_emulator_matches_engine_*` is the key invariant: the live price equals `compute_scope` at the anchor and under frequency changes.

- [ ] **Step 5 (optional bonus): real-eval check.** If `formulas` is importable (`/opt/homebrew/bin/python3 -c "import formulas"`), add a test that saves the workbook, loads + evaluates it with `formulas`, and asserts the computed `Investment Model!F20`/`B23` equal `compute_scope`'s anchor scans/price. If `formulas` is NOT available, `pytest.importorskip("formulas")` to skip cleanly. This is bonus airtightness on top of the emulator gate — do not block on it.

- [ ] **Step 6: Commit**

```bash
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" add observepoint-revenue/skills/scope-calculator/scripts/build_model.py observepoint-revenue/tests/test_build_model.py
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" commit -m "feat(scope-calculator): live graduated-price Pricing sheet (formula mirrors compute_scope)"
```

---

## Task 3: Scope detail + Sample pages sheets (migrate clean, from the appendix)

**Files:**
- Modify: `skills/scope-calculator/scripts/build_model.py`
- Test: `tests/test_build_model.py`

Bring the two *static* customer sheets from `build_evidence_appendix.py` into `build_model.py` so it's the complete customer workbook: **Scope detail** (= the appendix's clean "Pages by Domain": `Property (domain) | Pages | % of total | Include in scope? | Priority | Notes`, sorted desc, fillable cols empty) and **Sample pages** (= the appendix's "Sample Pages"). Apply the `customer_clean` guard over agent-composed cadence strings (layer name/why) — NOT per-domain `why`.

- [ ] **Step 1: Write failing tests** (append) — sheets present; clean (scan for the FORBIDDEN set); Scope detail header + fillable cols empty; samples render; guard rejects an internal term in a layer name.

```python
def test_all_customer_sheets_present_and_clean():
    wb = bm.build_workbook(DATA)
    assert wb.sheetnames == ["Investment Model", "Pricing", "Scope detail", "Sample pages"]
    import customer_clean
    text = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            text += [str(v) for v in row if v is not None]
    blob = "\n".join(text)
    for term in customer_clean.FORBIDDEN:
        assert term not in blob.lower(), f"internal term leaked: {term}"   # DATA fixture is clean (Acme/acme.com)

def test_scope_detail_header_and_fillable_empty():
    ws = bm.build_workbook(DATA)["Scope detail"]
    # header row + first data row exist; fillable Include/Priority/Notes empty
    hdr = [c.value for c in ws[3]] if ws[3][0].value else [c.value for c in ws[1]]
    assert "Pages" in hdr and "Spiral?" not in hdr

def test_sample_pages_render():
    blob = "\n".join(str(c.value) for ws in [bm.build_workbook(DATA)["Sample pages"]] for row in ws.iter_rows() for c in row if c.value)
    assert "https://acme.com/" in blob

def test_guard_rejects_internal_layer_name():
    d = json.loads(json.dumps(DATA)); d["cadence_layers"][0]["name"] = "Spiral baseline"
    with pytest.raises(ValueError):
        bm.build_workbook(d)
```

- [ ] **Step 2: Run to verify failure** (sheets missing / guard not wired).

- [ ] **Step 3: Implement** `_scope_detail(wb, data)` and `_sample_pages(wb, data)` (port the clean logic from `build_evidence_appendix.py` `_pages_by_domain` + `_sample_pages`, renamed sheets "Scope detail" / "Sample pages"). Add the `customer_clean` guard to `build_workbook`:

```python
def build_workbook(data):
    import customer_clean
    strings = [L.get("name", "") for L in data.get("cadence_layers", [])] + \
              [L.get("why", "") for L in data.get("cadence_layers", [])]
    customer_clean.assert_clean(strings, where="investment model")
    wb = Workbook()
    _investment_model(wb, data)
    _pricing(wb, data)
    _scope_detail(wb, data)
    _sample_pages(wb, data)
    return wb
```

Sort `per_domain` by `defensible_pages` desc; `% of total` = `defensible_pages / rollup.spiral_adjusted_anchor`. Reuse `_title`/`_headers`/`_row`/`FILL_COLS` helpers (copy them into `build_model.py`).

- [ ] **Step 4: Run to verify pass.** Full suite too: `pytest tests -q`.

- [ ] **Step 5: Commit** — `feat(scope-calculator): scope-detail + sample-pages sheets in the model (clean, guarded)`.

---

## Task 4: Lock formula cells, keep inputs editable

**Files:**
- Modify: `skills/scope-calculator/scripts/build_model.py`
- Test: `tests/test_build_model.py`

Per the locked decision: sheet protection ON (no password); only input cells editable; formula/label cells locked. openpyxl: by default all cells are `locked=True` and protection is off; turn on `ws.protection.sheet = True` and set `Protection(locked=False)` on the input cells.

- [ ] **Step 1: Write failing tests** (append)

```python
from openpyxl.styles import Protection  # noqa

def test_model_inputs_unlocked_outputs_locked():
    ws = bm.build_workbook(DATA)["Investment Model"]
    assert ws.protection.sheet is True
    for cell in ("B6", "B7", "B8", "B9", "B19", "C14", "D14", "C18", "D18"):   # inputs
        assert ws[cell].protection.locked is False, f"{cell} should be editable"
    for cell in ("B10", "E14", "F14", "F20", "F21", "B23"):                     # formulas
        assert ws[cell].protection.locked is True, f"{cell} should be locked"

def test_pricing_sheet_protected():
    assert bm.build_workbook(DATA)["Pricing"].protection.sheet is True
```

- [ ] **Step 2: Run to verify failure** (protection not set; inputs still locked-by-default True).

- [ ] **Step 3: Implement.** In each input-cell write, set `cell.protection = Protection(locked=False)`. After building each sheet, set `ws.protection.sheet = True` (no `password` — so a user can unprotect via the Excel UI if they truly need to). Add a one-line note cell on the Investment Model: "Yellow cells are editable — change them and the totals/price update automatically." Add a helper to centralize unlocking:

```python
from openpyxl.styles import Protection
_EDITABLE = Protection(locked=False)
# when writing an input cell: c.protection = _EDITABLE
# after all sheets built, in build_workbook: for ws in (model, pricing, scope, samples): ws.protection.sheet = True
```
Leave Scope detail's fillable Include/Priority/Notes columns editable too (`_EDITABLE`) so the customer can fill them under protection.

- [ ] **Step 4: Run to verify pass.** Full suite green.

- [ ] **Step 5: Commit** — `feat(scope-calculator): lock model formulas, keep inputs editable (sheet protection)`.

---

## Task 5: Wire-up + retire the static appendix

**Files:**
- Modify: `skills/scope-calculator/SKILL.md`, `references/deliverables-mapping.md`
- Delete: `skills/scope-calculator/scripts/build_evidence_appendix.py`, `tests/test_build_evidence_appendix.py`

- [ ] **Step 1: Update `SKILL.md` Stage 3** — the customer workbook is now produced by `build_model.py` (the live Investment Model), not `build_evidence_appendix.py`. Update the invocation line: `python3 "$SCRIPTS/build_model.py" <model.json> "<Customer> - investment model.xlsx"`. Update the script list (line 10): replace `build_evidence_appendix.py` with `build_model.py`. Keep proposal + internal-evidence lines. Note that the model is live (customer can flex inputs).

- [ ] **Step 2: Update `deliverables-mapping.md`** — Output 2 is now `build_model.py` (the live investment model: input cells + live scans/price formulas + scope detail + sample pages). Document `model.json` schema: `{customer, date?, page_count{low,anchor,high}, multipliers{geographies,scenarios,environments}, cadence_layers[{name,why,pct,runs_per_year}], buffer_pct?, tiers, per_domain[{hostname,defensible_pages,url_samples}], rollup{spiral_adjusted_anchor}}`. Remove the `build_model.py`-supersedes-Phase-B note (it's now done) and the references to `build_evidence_appendix.py`.

- [ ] **Step 3: Delete the superseded files**

```bash
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" rm \
  observepoint-revenue/skills/scope-calculator/scripts/build_evidence_appendix.py \
  observepoint-revenue/tests/test_build_evidence_appendix.py
```

- [ ] **Step 4: Run the FULL suite** — `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q`. Expected: green. The deleted appendix tests are gone; `build_model.py`'s tests cover the customer-workbook behaviors (scope detail, samples, clean). Confirm no other test imports `build_evidence_appendix` (grep; fix/remove any stragglers).

- [ ] **Step 5: Subagent behavioral check (controller-run, not implementer):** generate a sample `investment model.xlsx` from a realistic `model.json` and confirm it opens with formulas intact and the input cells editable. (A live Excel/LibreOffice recalc is ideal if available.)

- [ ] **Step 6: Commit** — `feat(scope-calculator): wire customer workbook to live build_model.py; retire static appendix`.

---

## Self-review (against spec §7)

- **§7.1 Investment Model (inputs + formulas)** → Task 1. ✓
- **§7.2 graduated price as a formula mirroring compute_scope** → Task 2 (cumulative Lo/Hi from tier widths, ∞ sentinel for the tail). ✓
- **§7.3 clean scope detail + sample pages** → Task 3. ✓
- **§7.4 single source of truth / tested invariant** → emulator-vs-`compute_scope` at anchor + perturbations (Tasks 1, 2); `compute_scope.py` unmodified. ✓
- **Cell locking (locked decision)** → Task 4. ✓
- **Retire appendix / wire SKILL.md + mapping** → Task 5. ✓

**Placeholder scan:** none — generator code, emulator, and tests are complete. The one latitude point (≤5 layers → pad with pct 0; 6-tier assumption → total row 11) is called out explicitly in Tasks 1 and 2.

**Type/reference consistency:** `build_workbook(data)`, `emulate_model(...)`, the cell coordinates (B6–B9 inputs, B10 sweep, C/D inputs + E/F formulas rows 14–18, F20/F21 totals, B23 price, Pricing E5:E10 costs + E11 total) are consistent across Tasks 1–4 and the tests. `model.json` schema consistent between Task 5 mapping and the Task-1 DATA fixture.

**Risk note:** the emulator + formula-string assertions are the dependency-free gate; they prove the formulas equal the engine for our simple arithmetic (`*`,`+`,`SUM`,`MIN`,`MAX`,`ROUND`). The optional `formulas`-eval test (Task 2 Step 5) adds real-Excel-semantics confidence when the lib is present. A one-time manual open-in-Excel is recommended before first customer use.
