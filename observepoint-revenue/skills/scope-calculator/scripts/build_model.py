"""Live Excel Investment Model workbook (.xlsx) for the scope-calculator.

Builds a customer-facing workbook with INPUT cells (yellow) and FORMULA cells
that reproduce compute_scope.py's arithmetic exactly when Excel recalculates.
The formulas are tested by a dependency-free Python emulator asserted against
compute_scope.compute() at the anchor and under perturbations.

Sheets (built incrementally across Phase B Tasks):
  Task 1 — Investment Model   (inputs + scan formulas)
  Task 2 — Pricing            (graduated tiers + live price formula)
"""
import pathlib
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import customer_clean

# ---------- theme constants (mirror build_evidence_appendix.py) ----------
FONT = "Montserrat"
DARK, YELLOW, LIGHT, GRAY, WHITE = "1E1E1E", "F2CD14", "F2F2F2", "5C5C5C", "FFFFFF"
INPUT_FILL = "FFF7CC"   # pale yellow — marks editable input cells
LOGO = pathlib.Path(__file__).resolve().parent.parent / "assets" / "op-logo.png"

_THIN = Side(style="thin", color="D9D9D9")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_YBAR = Side(style="thick", color=YELLOW)


def _f(bold=False, color=DARK, size=10):
    return Font(name=FONT, bold=bold, color=color, size=size)


def _fill(hexc):
    return PatternFill("solid", fgColor=hexc)


def _widths(ws, widths):
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w


def _input(ws, cell_addr, label_row, label, value, fmt="#,##0"):
    """Write a labelled INPUT cell (pale-yellow fill) to *ws*.

    Shared by Investment Model (Task 1) and Pricing sheet (Task 2+).
    """
    ws[f"A{label_row}"] = label
    ws[f"A{label_row}"].font = _f(bold=True)
    c = ws[cell_addr]
    c.value = value
    c.fill = _fill(INPUT_FILL)
    c.number_format = fmt
    c.font = _f()
    return c


# ---------- Investment Model sheet ----------

def _investment_model(wb, data):
    ws = wb.active
    ws.title = "Investment Model"

    pc = data["page_count"]
    m = data.get("multipliers", {})
    layers = data["cadence_layers"]

    # Logo
    if LOGO.exists():
        try:
            from openpyxl.drawing.image import Image as XLImage
            img = XLImage(str(LOGO))
            img.width, img.height = 200, 31
            ws.add_image(img, "A1")
        except Exception:
            pass
    ws.row_dimensions[1].height = 30

    # Title
    ws["A2"] = "Investment Model"
    ws["A2"].font = _f(bold=True, size=16)
    ws["A3"] = f"Prepared for {data.get('customer', '')}"
    ws["A3"].font = _f(color=GRAY, size=10)

    # INPUTS header
    ws["A5"] = "INPUTS"
    ws["A5"].font = _f(bold=True, size=11)

    _input(ws, "B6", 6, "Validated pages", pc["anchor"])
    _input(ws, "B7", 7, "Geographies", m.get("geographies", 1))
    _input(ws, "B8", 8, "Consent scenarios", m.get("scenarios", 1))
    _input(ws, "B9", 9, "Environments", m.get("environments", 1))

    ws["A10"] = "Pages per full sweep"
    ws["A10"].font = _f(bold=True)
    ws["B10"] = "=B6*B7*B8*B9"
    ws["B10"].number_format = "#,##0"

    # MONITORING CADENCE section
    ws["A12"] = "MONITORING CADENCE"
    ws["A12"].font = _f(bold=True, size=11)

    headers = ["Layer", "Why", "% of pages", "Runs/yr", "Pages each run", "Scans/yr"]
    for i, h in enumerate(headers):
        cc = ws.cell(13, i + 1, h)
        cc.font = _f(bold=True, color=WHITE)
        cc.fill = _fill(DARK)

    for idx, L in enumerate(layers[:5]):
        n = 14 + idx
        ws.cell(n, 1, L["name"]).font = _f()
        ws.cell(n, 2, L.get("why", "")).font = _f()

        cpct = ws.cell(n, 3, L["pct"])
        cpct.fill = _fill(INPUT_FILL)
        cpct.number_format = "0.##%"
        cpct.font = _f()

        crun = ws.cell(n, 4, L["runs_per_year"])
        crun.fill = _fill(INPUT_FILL)
        crun.number_format = "#,##0"
        crun.font = _f()

        ws.cell(n, 5).value = f"=$B$10*C{n}"
        ws.cell(n, 5).number_format = "#,##0"

        ws.cell(n, 6).value = f"=ROUND(E{n}*D{n},2)"
        ws.cell(n, 6).number_format = "#,##0"

    # Buffer %
    ws["A19"] = "Buffer %"
    ws["A19"].font = _f(bold=True)
    b19 = ws["B19"]
    b19.value = data.get("buffer_pct", 0.0)
    b19.fill = _fill(INPUT_FILL)
    b19.number_format = "0%"
    b19.font = _f()

    # Totals
    ws["A20"] = "Total annual page-scans (predicted)"
    ws["A20"].font = _f(bold=True)
    ws["F20"] = "=ROUND(SUM(F14:F18),0)"
    ws["F20"].number_format = "#,##0"

    ws["A21"] = "Purchased page-scans"
    ws["A21"].font = _f(bold=True)
    ws["F21"] = "=ROUND(F20*(1+B19),0)"
    ws["F21"].number_format = "#,##0"

    # Investment reference (points to Pricing sheet total; Task 2 adds that sheet)
    # Derive the total row the same way _pricing does so this stays in sync for
    # any tier count (e.g. 5 tiers → E10, 6 tiers → E11).
    import compute_scope as _cs
    tiers = data.get("tiers") or _cs.BAKED_TIERS
    total_row = 5 + len(tiers)
    ws["A23"] = "Recommended investment / year (USD)"
    ws["A23"].font = _f(bold=True, size=12)
    ws["B23"] = f"='Pricing'!E{total_row}"
    ws["B23"].number_format = "$#,##0"
    ws["B23"].fill = _fill(YELLOW)

    _widths(ws, [34, 30, 14, 12, 16, 14])


# ---------- Pricing sheet ----------

def _pricing(wb, data):
    """Build the 'Pricing' sheet with graduated-tier band table and live price formula.

    Derives Lo/Hi/Rate from data['tiers'] (cumulative widths) so a pricing change
    flows through automatically. The last band's Hi is set to 10**12 (∞ sentinel)
    to capture the final defined band AND graduated_price's tail-at-last-rate rule.

    For 6 tiers the total is written to row 11 (E11); B23 in Investment Model
    references '=Pricing'!E11 (written in Task 1 / _investment_model).
    """
    import compute_scope as _cs
    tiers = data.get("tiers") or _cs.BAKED_TIERS

    ws = wb.create_sheet("Pricing")
    ws["A2"] = "ObservePoint published pricing — graduated tiers"
    ws["A2"].font = _f(bold=True, size=12)

    # Header row 4
    for i, h in enumerate(["Band", "From (scans)", "To (scans)", "Rate / scan", "Cost"]):
        c = ws.cell(4, i + 1, h)
        c.font = _f(bold=True, color=WHITE)
        c.fill = _fill(DARK)

    # Band rows (rows 5 … 4+len(tiers))
    lo = 0
    for i, t in enumerate(tiers):
        n = 5 + i
        hi = lo + t["limit"]
        if i == len(tiers) - 1:
            hi = 10 ** 12   # ∞ sentinel: captures final band + tail at last rate
        ws.cell(n, 1, i + 1).font = _f()
        ws.cell(n, 2, lo).number_format = "#,##0"
        ws.cell(n, 3, hi).number_format = "#,##0"
        ws.cell(n, 4, t["pricePerPage"]).number_format = "$#,##0.00"
        ws.cell(n, 5).value = f"=MAX(0, MIN('Investment Model'!$F$21, C{n}) - B{n}) * D{n}"
        ws.cell(n, 5).number_format = "$#,##0.00"
        lo += t["limit"]

    # Total row (row 11 for 6 tiers; computed from len(tiers) for robustness)
    total_row = 5 + len(tiers)   # = 11 for 6 tiers
    ws.cell(total_row, 1, "Recommended investment / year").font = _f(bold=True)
    ws.cell(total_row, 5).value = f"=ROUND(SUM(E5:E{total_row - 1}),2)"
    ws.cell(total_row, 5).number_format = "$#,##0"

    _widths(ws, [22, 16, 16, 14, 16])


# ---------- public API ----------

def build_workbook(data):
    """Build the live Investment Model workbook.

    Task 1: Investment Model sheet (inputs + scan formulas).
    Task 2: Pricing sheet (graduated tiers + live price formula).
    Tasks 3–4 will add Scope detail / Sample pages + cell locking.
    """
    layers = data.get("cadence_layers", [])
    if len(layers) != 5:
        raise ValueError(
            f"investment model: expected exactly 5 cadence layers (the fixed Investment Model "
            f"layout has 5 rows); got {len(layers)}. The frequency-advisor ladder always has 5 — "
            f"drop a layer by setting its pct=0, don't remove it.")

    # Guard: check only agent-composed, customer-facing strings (cadence names + why).
    # Per-domain why and identity fields are excluded — scoping is the caller's job.
    strings = [L.get("name", "") for L in layers] + \
              [L.get("why", "") for L in layers]
    customer_clean.assert_clean(strings, where="investment model")

    wb = Workbook()
    _investment_model(wb, data)
    _pricing(wb, data)
    return wb


_DOC_REF = "see references/deliverables-mapping.md"
_REQUIRED = {
    "page_count": "{low, anchor, high}",
    "cadence_layers": "[{name, pct, runs_per_year}, …]",
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
    out = argv[2] if len(argv) > 2 else "investment-model.xlsx"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f"scope-calculator: model inputs are not valid JSON ({e}); {_DOC_REF}")
    _validate(data)
    build_workbook(data).save(out)
    print(out)


if __name__ == "__main__":
    main(sys.argv)
