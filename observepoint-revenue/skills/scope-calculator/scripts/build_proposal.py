"""Comprehensive, ObservePoint-themed scope & investment proposal (.docx).

REP-FIRST + customer-strippable. This is a working proposal for the rep: it is comprehensive
(it shows HOW the usage and price were derived) and it ends with a clearly-marked
"[INTERNAL — REMOVE BEFORE SENDING]" section the rep deletes before sending to the customer.

Theming matches ObservePoint's brand: Montserrat, near-black #1E1E1E, brand yellow #F2CD14,
light gray #F2F2F2 table rows, alert red for the internal marker, and the OP logo in the header.

Only the customer-facing narrative field `monitoring_summary` is guarded against internal-only
language (`_assert_clean`); the [INTERNAL] section intentionally carries the derivation detail.

Input schema (all keys tolerant; orchestrator assembles from derive-page-count + size-and-price):
{
  customer, prepared_by?, date?, use_case, domains[], properties_note?, regulations[],
  monitoring_summary,                       # customer-facing prose (guarded)
  page_count: {low, anchor, high, confidence, url_total?, defensible?, discounted?,
               census_id?, crawl_status?, spiral_note?},
  consent_states: {count, names[]},
  cadence_layers: [{name, runs_per_year, pages, runs}],     # = compute_scope's cadence_by_layer
  usage: {pages_per_sweep, annual_scans},
  pricing: {recommended_price, recommended_scans, range_low_price, range_high_price,
            price_by_band?: [{band_limit, rate, pages, cost}], pricing_source?,
            modeled_scans?, modeled_price?},
  internal: {assumptions[]?, implied_frequency?, thresholds_swept?, precise_anchor?}
}
"""
import json
import pathlib
import sys

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

FONT = "Montserrat"
DARK = RGBColor(0x1E, 0x1E, 0x1E)
GRAY = RGBColor(0x5C, 0x5C, 0x5C)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
RED = RGBColor(0xF3, 0x41, 0x46)
DARK_HEX, YELLOW_HEX, LIGHT_HEX = "1E1E1E", "F2CD14", "F2F2F2"
LOGO = pathlib.Path(__file__).resolve().parent.parent / "assets" / "op-logo.png"

_NARRATIVE_FIELDS = ("monitoring_summary",)
_FORBIDDEN = ("spiral", "discount", "query-param", "raw url", "indefensible", "fallback")
_FREQ = {1: "Annually", 4: "Quarterly", 12: "Monthly", 26: "Bi-weekly", 52: "Weekly", 365: "Daily"}


# ---------- formatting helpers ----------
def _int(n):
    return f"{int(round(n)):,}"


def _round_k(n):
    return int(round(n / 1000.0)) * 1000


def _usd(n):
    return f"${n:,.0f}"


def _run(p, text, *, bold=False, size=10.5, color=DARK):
    r = p.add_run(text)
    r.font.name, r.font.bold, r.font.size, r.font.color.rgb = FONT, bold, Pt(size), color
    return r


def _shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def _yellow_bar(doc):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", "18"), ("w:space", "1"), ("w:color", YELLOW_HEX)):
        bottom.set(qn(k), v)
    pbdr.append(bottom)
    p._p.get_or_add_pPr().append(pbdr)
    return p


def _heading(doc, text, *, color=DARK, size=13):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    _run(p, text, bold=True, size=size, color=color)
    _yellow_bar(doc)


def _para(doc, text, *, size=10.5, color=DARK, bold=False):
    p = doc.add_paragraph()
    _run(p, text, size=size, color=color, bold=bold)
    return p


def _table(doc, headers, rows):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.LEFT
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        _shade(c, DARK_HEX)
        _run(c.paragraphs[0], h, bold=True, size=9, color=WHITE)
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for i, val in enumerate(row):
            if ri % 2 == 1:
                _shade(cells[i], LIGHT_HEX)
            bold = str(val).startswith("**")
            _run(cells[i].paragraphs[0], str(val).strip("*"), size=9, bold=bold)
    return t


def _highlight(doc, text):
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = t.rows[0].cells[0]
    _shade(c, YELLOW_HEX)
    p = c.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p, text, bold=True, size=15, color=DARK)
    return t


def _set_base_style(doc):
    st = doc.styles["Normal"]
    st.font.name, st.font.size, st.font.color.rgb = FONT, Pt(10.5), DARK


# ---------- guard ----------
def _assert_clean(data):
    """Guard the agent-composed customer narrative against internal-only language. Scoped to
    `_NARRATIVE_FIELDS` only — NOT identity fields and NOT the intentional [INTERNAL] section."""
    blob = " ".join(str(data.get(f, "")) for f in _NARRATIVE_FIELDS).lower()
    leaked = [w for w in _FORBIDDEN if w in blob]
    if leaked:
        raise ValueError(f"proposal narrative contains internal-only term(s): {leaked}")


# ---------- builder ----------
def build_proposal(data):
    _assert_clean(data)
    pc = data["page_count"]
    pr = data["pricing"]
    us = data["usage"]
    cs = data.get("consent_states", {"count": 1, "names": ["Default"]})
    internal = data.get("internal", {})

    doc = Document()
    _set_base_style(doc)

    # Header: logo + title
    if LOGO.exists():
        try:
            doc.add_picture(str(LOGO), width=Inches(2.0))
        except Exception:
            pass
    _run(doc.add_paragraph(), "Scope & Investment Proposal", bold=True, size=22)
    _yellow_bar(doc)
    _run(doc.add_paragraph(), f"Prepared for {data.get('customer', '')}", size=12, bold=True)
    sub_bits = [b for b in (data.get("date"),
                            ("Prepared by " + data["prepared_by"]) if data.get("prepared_by") else None,
                            (data.get("use_case", "").title() if data.get("use_case") else None)) if b]
    if sub_bits:
        _run(doc.add_paragraph(), "  ·  ".join(sub_bits), size=9, color=GRAY)

    # §1 Footprint
    _heading(doc, "1. Your web footprint")
    _para(doc, f"We scanned your web properties to establish how many real pages ObservePoint "
               f"would monitor. Your validated footprint is approximately "
               f"{_int(_round_k(pc['anchor']))} pages "
               f"(range {_int(_round_k(pc['low']))}–{_int(_round_k(pc['high']))}; "
               f"confidence {pc.get('confidence', 'MEDIUM')}).")
    if data.get("properties_note"):
        _para(doc, data["properties_note"] + " The full property list is in the attached evidence "
                   "workbook — please review and confirm which properties are in scope.")

    # §2 What we monitor
    _heading(doc, "2. What ObservePoint will monitor")
    _para(doc, data.get("monitoring_summary", ""))
    _para(doc, "Delivered through ObservePoint Web Audits (automated page scanning), Tag & Variable "
               "Rules (validation of what fires and what must not), and scheduled re-scans — "
               "continuous evidence that your site behaves the way it should.")

    # §3 Derivation
    _heading(doc, "3. How your annual usage is calculated")
    _para(doc, "A page scan = one page checked one time. Scanning your pages once is one pass; "
               "checking them on a recurring schedule multiplies that into annual usage.", size=9.5, color=GRAY)
    _table(doc, ["From pages to one full sweep", "", "Pages"], [
        ["Validated pages on your properties", "", _int(pc["anchor"])],
        [f"× Consent states monitored ({', '.join(cs['names'])})", "", f"×{cs['count']}"],
        ["**Pages per full sweep**", "", "**" + _int(us["pages_per_sweep"]) + "**"],
    ])
    _para(doc, "")
    cadence_rows = []
    for L in data.get("cadence_layers", []):
        freq = _FREQ.get(L.get("runs_per_year"), f"{L.get('runs_per_year')}×/yr")
        cadence_rows.append([L["name"], freq, _int(L.get("pages", 0)),
                             str(L.get("runs_per_year", "")), _int(L.get("runs", 0))])
    cadence_rows.append(["**Total annual page scans**", "", "", "", "**" + _int(us["annual_scans"]) + "**"])
    _table(doc, ["What's monitored", "How often", "Pages each run", "Runs/yr", "Page scans/yr"], cadence_rows)

    # §4 Investment
    _heading(doc, "4. Recommended contract & investment")
    _highlight(doc, f"{_int(pr['recommended_scans'])} page scans   ·   {_usd(pr['recommended_price'])} / year")
    _para(doc, "Usage-based pricing at ObservePoint's published rates. The two figures above "
               "reconcile exactly in ObservePoint's pricing calculator.", size=9.5, color=GRAY)
    if pr.get("range_low_price") and pr.get("range_high_price"):
        _para(doc, f"As your property list and monitoring cadence are confirmed, expect a range of "
                   f"{_usd(pr['range_low_price'])}–{_usd(pr['range_high_price'])} per year.")

    # §5 To finalize
    _heading(doc, "5. To finalize")
    for item in ("Confirm the in-scope property list (see the evidence workbook).",
                 f"Confirm applicable regulations and consent states ({', '.join(data.get('regulations', []) or ['TBD'])}).",
                 "Confirm the monitoring cadence above matches your risk tolerance.",
                 "Finalize the agreement at the confirmed usage."):
        p = doc.add_paragraph(style="List Bullet")
        _run(p, item)

    # [INTERNAL] — rep-only, delete before sending
    doc.add_page_break()
    _heading(doc, "[INTERNAL — REMOVE BEFORE SENDING TO CUSTOMER]", color=RED, size=13)
    _para(doc, "Everything below is rep-only context for how this scope was built. Delete this "
               "section before sharing the proposal.", size=9, color=RED, bold=True)

    _para(doc, "Page-count derivation", bold=True, size=11)
    pcrows = [["Census ID", str(pc.get("census_id", "—"))],
              ["Crawl status", str(pc.get("crawl_status", "—"))],
              ["Raw URLs crawled (NOT quoted)", _int(pc["url_total"]) if pc.get("url_total") else "—"],
              ["Defensible pages (anchor)", _int(pc.get("defensible", pc["anchor"]))],
              ["Discounted (query-string duplicates)", _int(pc["discounted"]) if pc.get("discounted") else "—"],
              ["Confidence", str(pc.get("confidence", "—"))]]
    _table(doc, ["Metric", "Value"], pcrows)
    if pc.get("spiral_note"):
        _para(doc, pc["spiral_note"], size=9, color=GRAY)

    _para(doc, "Modeled vs. contracted", bold=True, size=11)
    _table(doc, ["", "Modeled (precise)", "Contracted (clean)"], [
        ["Annual page scans", _int(pr.get("modeled_scans", us["annual_scans"])), _int(pr["recommended_scans"])],
        ["Annual price", _usd(pr.get("modeled_price", pr["recommended_price"])), _usd(pr["recommended_price"])],
    ])
    if internal.get("implied_frequency") is not None:
        _para(doc, f"Implied blended frequency: {internal['implied_frequency']}× (vs the public "
                   f"single-frequency calculator).", size=9, color=GRAY)

    if internal.get("assumptions"):
        _para(doc, "Assumptions applied (confirm with customer)", bold=True, size=11)
        for a in internal["assumptions"]:
            p = doc.add_paragraph(style="List Bullet")
            _run(p, a, size=9.5)

    if pr.get("price_by_band"):
        _para(doc, "Usage-based pricing — per-band breakdown", bold=True, size=11)
        band_rows = []
        for b in pr["price_by_band"]:
            band = "tail" if b.get("band_limit") is None else _int(b["band_limit"])
            band_rows.append([band, f"${b['rate']:.2f}", _int(b["pages"]), _usd(b["cost"])])
        _table(doc, ["Band width", "Rate/scan", "Scans", "Cost"], band_rows)

    src = pr.get("pricing_source", "")
    if src:
        _para(doc, f"Pricing source: {src}", size=8, color=GRAY)
    if internal.get("thresholds_swept"):
        _para(doc, f"Spiral threshold sweep: {internal['thresholds_swept']}", size=8, color=GRAY)

    return doc


def main(argv):
    if len(argv) > 1:
        with open(argv[1]) as fh:
            raw = fh.read()
    else:
        raw = sys.stdin.read()
    out = argv[2] if len(argv) > 2 else "proposal.docx"
    build_proposal(json.loads(raw)).save(out)  # narrative guard runs inside
    print(out)


if __name__ == "__main__":
    main(sys.argv)
