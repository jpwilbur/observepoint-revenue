"""ObservePoint-themed account research dossier (.docx) for research-account.

Input: a scored.json object (the classification object + a `score` block from score_account.py).
This is an INTERNAL AE artifact. The "best opening angle" is labeled internal strategy (the sharp
legal framing belongs to the AE's strategy, never to prospect-facing copy — that is the future
sequence-contacts skill's job, under the tone governor).

Theming mirrors ObservePoint's brand (Montserrat / #1E1E1E / #F2CD14), matching build_proposal.py.

CLI:  build_dossier.py <scored.json> <out.docx>   (prints the output path)
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


# ---------- theming helpers (mirrored from build_proposal.py) ----------
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
            # Dossier rows render plainly — no **bold** convention (build_proposal._table has one).
            _run(cells[i].paragraphs[0], str(val), size=9)
    return t


def _highlight(doc, text, fill=YELLOW_HEX, color=DARK):
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = t.rows[0].cells[0]
    _shade(c, fill)
    p = c.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p, text, bold=True, size=15, color=color)
    return t


def _set_base_style(doc):
    st = doc.styles["Normal"]
    st.font.name, st.font.size, st.font.color.rgb = FONT, Pt(10.5), DARK


def _bullets(doc, items):
    for it in items or []:
        p = doc.add_paragraph(style="List Bullet")
        _run(p, str(it), size=10)


# ---------- builder ----------
def build_dossier(data):
    score = data.get("score", {})
    research = data.get("research", {})
    scan = data.get("scan", {})

    doc = Document()
    _set_base_style(doc)

    # Header
    if LOGO.exists():
        try:
            doc.add_picture(str(LOGO), width=Inches(2.0))
        except Exception:
            pass
    _run(doc.add_paragraph(), f"Account Research Dossier — {data.get('account', '')}", bold=True, size=20)
    _yellow_bar(doc)
    sub = [b for b in (data.get("date"),
                       ("Prepared by " + data["prepared_by"]) if data.get("prepared_by") else None,
                       data.get("domain")) if b]
    if sub:
        _run(doc.add_paragraph(), "  ·  ".join(sub), size=9, color=GRAY)

    # Verdict band
    qualified = score.get("qualified")
    verdict = (f"{'QUALIFIED' if qualified else 'NOT QUALIFIED'}   ·   "
               f"Score {score.get('finalScore', 0)}  "
               f"(fit {score.get('fitScore', 0)} + why-now {score.get('whyNowScore', 0)})")
    _highlight(doc, verdict, fill=(YELLOW_HEX if qualified else "F2F2F2"))
    if score.get("lowFitHighTrigger"):
        _para(doc, "Qualified on the why-now trigger override despite sub-gate fit — a timing play.",
              size=9, color=RED)
    if data.get("rationale"):
        _para(doc, data["rationale"], size=10, color=GRAY)

    # Why now (all triggers; points from the scored breakdown, 0 if unscored)
    _heading(doc, "Why now")
    # `or 0` guards against a null/absent points value (dict.get's default only covers a MISSING key,
    # not a key mapped to None) so the sort key below never compares None to int.
    pts_by_desc = {b.get("description"): (b.get("points") or 0) for b in score.get("whyNowBreakdown", [])}
    trigs = sorted(data.get("triggers", []) or [],
                   key=lambda t: pts_by_desc.get(t.get("description"), 0), reverse=True)
    if trigs:
        _table(doc, ["Trigger", "Date", "Category", "Source", "Points"],
               [[t.get("description", ""), t.get("date", "—"), t.get("category", ""),
                 t.get("sourceUrl", ""), pts_by_desc.get(t.get("description"), 0)] for t in trigs])
    else:
        _para(doc, "No acute web-tracking trigger event found. A strong fit with no trigger is a "
                   "valid, honest result.", size=10, color=GRAY)

    # ICP fit
    _heading(doc, "ICP fit")
    _table(doc, ["Criterion", "Met?", "Points", "Evidence"],
           [[b["label"], "Yes" if b["met"] else "No", b["points"], b.get("evidence") or "—"]
            for b in score.get("fitBreakdown", [])])

    # Account overview
    _heading(doc, "Account overview")
    if research.get("companyOverview"):
        _para(doc, research["companyOverview"])
    if research.get("painHypotheses"):
        _para(doc, "Why ObservePoint matters here:", bold=True, size=10)
        _bullets(doc, research["painHypotheses"])
    if research.get("competitorIntel"):
        _para(doc, "Competitor intel: " + research["competitorIntel"], size=10)
    # Tech stack + the measured scan inventory
    tech = research.get("techStackNotes", "")
    tags = ", ".join(scan.get("tags") or [])
    cmp_line = scan.get("cmp")
    measured = []
    if cmp_line:
        measured.append(f"CMP: {cmp_line}" + (" (ObservePoint-supported)" if scan.get("cmp_supported") else ""))
    if tags:
        measured.append(f"Tags/pixels: {tags}")
    if scan.get("site_census"):
        measured.append(f"Site Census page count: {scan['site_census']}")
    line = "Tech stack: " + tech
    if measured:
        line += "  |  Measured on-site: " + "; ".join(measured) + "."
    _para(doc, line, size=10)

    # Best opening angle (internal strategy)
    _heading(doc, "Best opening angle")
    _para(doc, "Internal strategy — not prospect-facing copy.", bold=True, size=9, color=RED)
    _para(doc, research.get("bestOpeningAngle", ""))

    # Contacts
    _heading(doc, "Contacts")
    rows = []
    held = 0
    for c in data.get("contacts", []) or []:
        verified = bool(c.get("sourceVerified")) and bool(c.get("sourceUrl"))
        flag = "Yes" if verified else "⚠ held back — verify before outreach"
        if not verified:
            held += 1
        rows.append([c.get("name", ""), c.get("title", ""), c.get("linkedin") or "—",
                     flag, c.get("personalizationHook", ""), c.get("avoid", "")])
    if rows:
        _table(doc, ["Name", "Title", "LinkedIn", "Verified?", "Hook", "Avoid"], rows)
    if held:
        _para(doc, f"{held} contact(s) held back: missing source verification. Confirm the person and "
                   f"current title before any outreach (no fabricated or unverified contacts ship).",
              size=9, color=RED)

    # Sources & method
    _heading(doc, "Sources & method")
    _bullets(doc, research.get("researchSources", []))
    _para(doc, "Method: public web research + an ObservePoint CMP/tag scan of the live site. "
               "The score is computed deterministically from ObservePoint's ICP weights "
               "(reproducible; not a model guess).", size=9, color=GRAY)

    return doc


def main(argv):
    if len(argv) < 3:
        sys.exit("usage: build_dossier.py <scored.json> <out.docx>")
    data = json.loads(pathlib.Path(argv[1]).read_text())
    build_dossier(data).save(argv[2])
    print(argv[2])


if __name__ == "__main__":
    main(sys.argv)
