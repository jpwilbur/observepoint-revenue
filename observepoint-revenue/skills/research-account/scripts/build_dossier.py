"""Dark, NERD-styled account research dossier — self-contained HTML rendered to PDF.

Input: a scored.json object (classification + a `score` block from score_account.py).
INTERNAL AE artifact. The "best opening angle" is internal strategy, never prospect-facing copy.

Output: a single self-contained .html (inline CSS, opens in any browser and looks like the NERD
account-detail screen) plus a .pdf frozen from it. PDF engine, in order of preference:
  PDF rendering is delegated to brand_kit.html_to_pdf (engine cascade: headless Chrome
  via --print-to-pdf, then weasyprint). If no engine is available the dossier still writes
  the self-contained .html so there is always a deliverable.
The dossier is read, not edited, so a frozen PDF is the right format (the editable proposal stays .docx).

CLI:  build_dossier.py <scored.json> <out.pdf>
      Writes ONLY <out>.pdf to the output folder (the HTML is rendered from a temp file and discarded).
      If no PDF engine is available, falls back to writing <out>.html so there is still a deliverable.
      Prints the path it produced.
"""
import html as _html
import json
import os
import pathlib
import sys
import tempfile

# --- ObservePoint brand authority (single source of truth) ---
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "branding-guide" / "scripts"))
import brand_kit  # noqa: E402

_d = brand_kit.theme("dark")
_sem = brand_kit.colors()["semantic"]
BG, PANEL, PANEL2, BORDER = _d["bg"], _d["panel"], _d["panel2"], _d["border"]
TEXT, MUTED = _d["text"], _d["muted"]
YELLOW, RED, GREEN, LINK = brand_kit.brand_yellow(), _sem["alert"], _sem["success"], _sem["link"]
GRAYCHIP = "#3a3e49"   # dossier-only chip shade (not a brand token)

# why-now category -> (chip bg, chip text color)
_CAT = {
    "litigation": (RED, "#fff"), "enforcement": (RED, "#fff"), "incident": (RED, "#fff"),
    "leadership": (YELLOW, "#1a1a1a"), "hiring": (YELLOW, "#1a1a1a"),
    "earnings": (YELLOW, "#1a1a1a"), "settlement": (YELLOW, "#1a1a1a"),
}


def _e(x):
    return _html.escape("" if x is None else str(x))


def _chip(text, bg, fg, *, big=False):
    pad = "4px 12px" if big else "2px 9px"
    fs = "12px" if big else "10.5px"
    return (f'<span class="chip" style="background:{bg};color:{fg};padding:{pad};'
            f'font-size:{fs}">{_e(text)}</span>')


def _link(url, text=None):
    return f'<a href="{_e(url)}" target="_blank">{_e(text or url)}</a>'


# ---------- HTML builder ----------
def build_html(data):
    score = data.get("score", {}) or {}
    research = data.get("research", {}) or {}
    scan = data.get("scan", {}) or {}
    qualified = bool(score.get("qualified"))

    # --- header ---
    sub = " · ".join(_e(b) for b in (data.get("date"),
                                     ("Prepared by " + data["prepared_by"]) if data.get("prepared_by") else None,
                                     data.get("domain")) if b)
    head = f"""
    <div class="brand"><span class="op">ObservePoint</span><span class="bar">|</span>
      <span class="kicker">Account Research Dossier</span></div>
    <h1>{_e(data.get('account', ''))}</h1>
    <div class="sub">{sub}</div>
    """

    # --- verdict ---
    vchip = _chip("QUALIFIED" if qualified else "NOT QUALIFIED",
                  GREEN if qualified else GRAYCHIP, "#fff", big=True)
    lowfit = ('<div class="note red">Qualified on the why-now trigger override despite sub-gate '
              'fit — a timing play.</div>' if score.get("lowFitHighTrigger") else "")
    rationale = f'<div class="rationale">{_e(data.get("rationale"))}</div>' if data.get("rationale") else ""
    # The badge labels the two components explicitly. finalScore is fitScore (capped 0-100) PLUS an
    # uncapped additive whyNowScore, so a multi-trigger account can total >100 — showing that total as
    # a lone number on a 0-100-looking badge is misleading. Show "Fit n/100 · Why-now m" instead.
    fit_s = _e(score.get("fitScore", 0))
    why_s = _e(score.get("whyNowScore", 0))
    total_s = _e(score.get("finalScore", 0))
    verdict = f"""
    <div class="verdict">
      <div class="badge">
        <span class="bscore"><span class="bnum">{fit_s}</span><span class="bden">/100</span></span>
        <span class="blbl">Fit</span>
        <span class="bsep">·</span>
        <span class="bscore"><span class="bnum">{why_s}</span></span>
        <span class="blbl">Why-now</span>
      </div>
      <div class="vmeta">
        <div>{vchip}</div>
        <div class="vmath">Fit {fit_s}/100 &nbsp;·&nbsp; Why-now {why_s} &nbsp;(combined {total_s})</div>
      </div>
    </div>{lowfit}{rationale}
    """

    # --- why now ---
    # Render the scored triggers DIRECTLY from whyNowBreakdown, which carries the points score_account
    # computed per trigger (with recency decay). Do NOT re-join raw triggers to points by free-text
    # description: two triggers with identical/similar descriptions would collapse or mis-assign points.
    # `category` is a display-only field that lives on the raw trigger (not the breakdown), so it is
    # joined back by a consuming positional match on the immutable (scoreKey, sourceUrl, date) tuple —
    # never on description. Unscored raw triggers (unknown scoreKey, absent from the breakdown) are
    # appended at the end at 0 points so honest context is not silently dropped.
    raw_trigs = list(data.get("triggers", []) or [])
    breakdown = list(score.get("whyNowBreakdown", []) or [])

    def _take_category(score_key, source_url, date):
        for i, t in enumerate(raw_trigs):
            if (t.get("scoreKey") == score_key and t.get("sourceUrl") == source_url
                    and t.get("date") == date):
                return (raw_trigs.pop(i).get("category") or "")
        return ""

    rows = []  # (points, date, sourceUrl, description, category)
    for b in sorted(breakdown, key=lambda b: (b.get("points") or 0), reverse=True):
        cat = _take_category(b.get("key"), b.get("sourceUrl"), b.get("date"))
        rows.append((b.get("points") or 0, b.get("date"), b.get("sourceUrl"),
                     b.get("description"), cat))
    # Any raw triggers not matched above were unscored (unknown scoreKey) — show them at 0 points.
    for t in raw_trigs:
        rows.append((0, t.get("date"), t.get("sourceUrl"), t.get("description"),
                     t.get("category") or ""))

    if rows:
        whynow = ""
        for p, date, source_url, desc, cat in rows:
            bg, fg = _CAT.get((cat or "").lower(), (GRAYCHIP, TEXT))
            src = _link(source_url, "source ↗") if source_url else ""
            whynow += f"""
            <div class="trigger">
              <div class="trow">{_chip((cat or '—').upper(), bg, fg)}
                <span class="tdate">{_e(date or '—')}</span>
                <span class="tpts">+{_e(p)}</span></div>
              <div class="tdesc">{_e(desc or '')}</div>
              <div class="tsrc">{src}</div>
            </div>"""
    else:
        whynow = ('<div class="empty">No acute web-tracking trigger event found. A strong fit with '
                  'no trigger is a valid, honest result.</div>')

    # --- ICP fit ---
    fit_rows = ""
    for b in score.get("fitBreakdown", []):
        chip = _chip("✓ MET", GREEN, "#fff") if b.get("met") else _chip("—", GRAYCHIP, MUTED)
        fit_rows += f"""
        <tr><td class="fcrit">{_e(b.get('label'))}</td>
            <td class="fmet">{chip}</td>
            <td class="fpts">{_e(b.get('points'))}</td>
            <td class="fev">{_e(b.get('evidence') or '—')}</td></tr>"""

    # --- account overview ---
    ov = ""
    if research.get("companyOverview"):
        ov += f"<p>{_e(research['companyOverview'])}</p>"
    if research.get("painHypotheses"):
        ov += '<div class="lbl">Why ObservePoint matters here</div><ul>'
        ov += "".join(f"<li>{_e(x)}</li>" for x in research["painHypotheses"]) + "</ul>"
    if research.get("competitorIntel"):
        ov += f'<p><span class="lbl-inline">Competitor intel:</span> {_e(research["competitorIntel"])}</p>'
    measured = []
    if scan.get("cmp"):
        measured.append("CMP: " + _e(scan["cmp"]) + (" (ObservePoint-supported)" if scan.get("cmp_supported") else ""))
    if scan.get("tags"):
        measured.append("Tags/pixels: " + _e(", ".join(scan["tags"])))
    if scan.get("site_census"):
        measured.append("Site Census pages: " + _e(scan["site_census"]))
    tech = _e(research.get("techStackNotes", ""))
    if measured:
        tech += '<div class="measured"><span class="lbl-inline">Measured on-site:</span> ' + "; ".join(measured) + ".</div>"
    if tech:
        ov += f"<p>{tech}</p>"

    # --- contacts ---
    cards, held = "", 0
    for c in data.get("contacts", []) or []:
        verified = bool(c.get("sourceVerified")) and bool(c.get("sourceUrl"))
        if not verified:
            held += 1
        vc = _chip("✓ VERIFIED", GREEN, "#fff") if verified else _chip("⚠ HELD BACK", RED, "#fff")
        li = f' · {_link(c["linkedin"], "LinkedIn ↗")}' if c.get("linkedin") else ""
        src = f' · {_link(c["sourceUrl"], "source ↗")}' if c.get("sourceUrl") else ""
        cards += f"""
        <div class="contact">
          <div class="crow"><span class="cname">{_e(c.get('name'))}</span>
            <span class="ctitle">{_e(c.get('title'))}</span>{vc}</div>
          <div class="chook"><span class="lbl-inline">Hook:</span> {_e(c.get('personalizationHook') or '—')}</div>
          <div class="cavoid"><span class="lbl-inline">Avoid:</span> {_e(c.get('avoid') or '—')}</div>
          <div class="clinks">{li}{src}</div>
        </div>"""
    held_note = (f'<div class="note red">{held} contact(s) held back — missing source verification. '
                 f'Confirm the person and current title before any outreach (no fabricated or '
                 f'unverified contacts ship).</div>' if held else "")

    srcs = "".join(f"<li>{_link(u)}</li>" for u in research.get("researchSources", []))
    angle = _e(research.get("bestOpeningAngle", ""))

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{_e(data.get('account',''))} — Account Research Dossier</title>
<style>
@import url('{brand_kit.font()["google_fonts"]}');
*{{box-sizing:border-box}}
html{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
body{{margin:0;background:{BG};color:{TEXT};
  font-family:'{brand_kit.font()["family"]}',{brand_kit.font()["fallback"]};font-size:13px;line-height:1.5}}
.page{{max-width:840px;margin:0 auto;padding:34px 40px 56px}}
a{{color:{LINK};text-decoration:none}} a:hover{{text-decoration:underline}}
.brand{{display:flex;align-items:center;gap:10px;font-weight:800;letter-spacing:.3px}}
.brand .op{{color:#fff}} .brand .bar{{color:{YELLOW};font-weight:700}}
.brand .kicker{{color:{MUTED};font-weight:700;font-size:12px;letter-spacing:1.5px;text-transform:uppercase}}
h1{{font-size:30px;font-weight:800;margin:10px 0 4px;color:#fff}}
.sub{{color:{MUTED};font-size:12px;border-bottom:3px solid {YELLOW};padding-bottom:14px;margin-bottom:20px}}
.verdict{{display:flex;align-items:center;gap:18px;margin-bottom:6px}}
.badge{{background:{YELLOW};color:#15161a;border-radius:14px;padding:12px 18px;
  display:flex;align-items:baseline;gap:7px;flex-wrap:wrap}}
.badge .bscore{{font-weight:800;line-height:1}}
.badge .bnum{{font-size:32px}} .badge .bden{{font-size:15px;font-weight:700;opacity:.7}}
.badge .blbl{{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.6px;align-self:center}}
.badge .bsep{{font-size:20px;font-weight:800;opacity:.5;align-self:center}}
.vmeta{{display:flex;flex-direction:column;gap:8px}}
.vmath{{color:{MUTED};font-size:13px}}
.chip{{display:inline-block;border-radius:999px;font-weight:700;letter-spacing:.4px;
  text-transform:uppercase;white-space:nowrap}}
.rationale{{color:{MUTED};margin:10px 0 4px;font-style:italic}}
.note.red{{color:{RED};font-size:12px;margin:8px 0;font-weight:600}}
section{{background:{PANEL};border:1px solid {BORDER};border-radius:14px;padding:6px 20px 18px;margin:18px 0}}
section>h2{{font-size:12px;letter-spacing:1.6px;text-transform:uppercase;color:{MUTED};
  font-weight:800;border-bottom:1px solid {BORDER};padding:14px 0 10px;margin:0 0 14px}}
.trigger{{background:{PANEL2};border-radius:10px;padding:11px 14px;margin:10px 0;
  border-left:4px solid {YELLOW}}}
.trow{{display:flex;align-items:center;gap:12px;margin-bottom:5px}}
.tdate{{color:{MUTED};font-size:11px}} .tpts{{margin-left:auto;color:{YELLOW};font-weight:800;font-size:13px}}
.tdesc{{color:{TEXT}}} .tsrc{{margin-top:4px;font-size:12px}}
.empty{{color:{MUTED};font-style:italic}}
table{{width:100%;border-collapse:collapse}}
td{{padding:9px 8px;border-bottom:1px solid {BORDER};vertical-align:top;font-size:12.5px}}
.fcrit{{font-weight:600;width:34%}} .fmet{{width:78px}} .fpts{{width:48px;color:{YELLOW};font-weight:700}}
.fev{{color:{MUTED}}}
.lbl{{color:{YELLOW};font-weight:700;text-transform:uppercase;letter-spacing:.6px;font-size:11px;margin:12px 0 6px}}
.lbl-inline{{color:{MUTED};font-weight:700}}
ul{{margin:6px 0;padding-left:20px}} li{{margin:4px 0}}
.measured{{margin-top:8px;color:{TEXT}}}
.callout{{background:{PANEL2};border-left:5px solid {YELLOW};border-radius:10px;padding:13px 16px}}
.callout .intern{{color:{RED};font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:.6px;margin-bottom:6px}}
.contact{{background:{PANEL2};border-radius:10px;padding:12px 15px;margin:10px 0}}
.crow{{display:flex;align-items:center;gap:11px;flex-wrap:wrap;margin-bottom:6px}}
.cname{{font-weight:700;color:#fff;font-size:14px}} .ctitle{{color:{MUTED}}}
.chook,.cavoid{{font-size:12.5px;margin:3px 0}} .clinks{{margin-top:6px;font-size:12px}}
.method{{color:{MUTED};font-size:12px;margin-top:10px}}
@page{{size:A4;margin:14mm}}
</style></head>
<body><div class="page">
  {head}
  {verdict}
  <section><h2>Why now</h2>{whynow}</section>
  <section><h2>ICP fit</h2><table><tbody>{fit_rows}</tbody></table></section>
  <section><h2>Account overview</h2>{ov}</section>
  <section><h2>Best opening angle</h2>
    <div class="callout"><div class="intern">Internal strategy — not prospect-facing copy</div>{angle}</div>
  </section>
  <section><h2>Contacts</h2>{cards}{held_note}</section>
  <section><h2>Sources &amp; method</h2><ul>{srcs}</ul>
    <div class="method">Method: public web research + an ObservePoint CMP/tag scan of the live site.
    The score is computed deterministically from ObservePoint's ICP weights (reproducible; not a model guess).</div>
  </section>
</div></body></html>"""


# ---------- PDF rendering (delegated to brand_kit) ----------
def to_pdf(html_path, pdf_path):
    """Render html_path -> pdf_path via the shared brand_kit engine cascade.

    Passes timeout=90 (heavy full-page dossiers) — the dossier's historical limit."""
    return brand_kit.html_to_pdf(html_path, pdf_path, timeout=90)


def main(argv):
    if len(argv) < 3:
        sys.exit("usage: build_dossier.py <scored.json> <out.pdf>")
    data = json.loads(pathlib.Path(argv[1]).read_text())
    out_pdf = pathlib.Path(argv[2])
    html = build_html(data)
    # Render from a TEMP html so only the .pdf lands in the rep's output folder.
    fd, tmp_html = tempfile.mkstemp(suffix=".html")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(html)
        engine = to_pdf(tmp_html, str(out_pdf))
    finally:
        try:
            os.unlink(tmp_html)
        except OSError:
            pass
    if engine:
        print(str(out_pdf))   # only the PDF remains in the output folder
    else:
        # No PDF engine — keep the HTML as the deliverable so the rep can still print it.
        out_html = out_pdf.with_suffix(".html")
        out_html.write_text(html, encoding="utf-8")
        sys.stderr.write("no PDF engine found (Chrome/weasyprint); wrote HTML only — open it and Print to PDF\n")
        print(str(out_html))


if __name__ == "__main__":
    main(sys.argv)
