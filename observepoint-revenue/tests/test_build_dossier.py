import json
import pathlib
import subprocess
import sys

import build_dossier as bd
import score_account as sa

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "research-account" / "scripts" / "build_dossier.py"
AS_OF = "2026-06-07"

CLASSIFICATION = {
    "account": "Acme Health", "domain": "acmehealth.com", "prepared_by": "Jarrod Wilbur", "date": AS_OF,
    "scan": {"cmp": "OneTrust", "cmp_supported": True, "cmp_confirmed": True,
             "tags": ["Google Tag Manager", "GA4", "Meta Pixel"],
             "tag_method": "homepage script-signature scan (WebFetch)", "site_census": None,
             "method": "observepoint detect_cmp + static tag scan"},
    "fit": [
        {"key": "privacyConsentSurface", "met": True, "evidence": "OneTrust CMP (confirmed via ObservePoint scan)."},
        {"key": "regulatoryExposure", "met": True, "evidence": "HIPAA + CCPA."},
        {"key": "tagPixelDensity", "met": True, "evidence": "GTM + Meta Pixel observed."},
        {"key": "webScale", "met": True, "evidence": "Thousands of pages."},
        {"key": "targetVertical", "met": True, "evidence": "Healthcare."},
        {"key": "analyticsAccuracy", "met": False},
    ],
    "triggers": [
        {"description": "CIPA class action re: tracking pixels.", "date": "2026-01-16",
         "sourceUrl": "https://example.com/cipa", "category": "litigation", "scoreKey": "pixelWiretapSuit"},
    ],
    "rationale": "Strong privacy fit with active CIPA exposure.",
    "research": {
        "companyOverview": "Acme Health is a large consumer healthcare web property.",
        "keyTriggers": ["Active CIPA class action."],
        "painHypotheses": ["Needs dated per-page evidence of what fires and the consent state."],
        "competitorIntel": "Likely OneTrust CMP; no incumbent pixel-audit vendor.",
        "techStackNotes": "GTM tag orchestration; multiple ad/analytics partners.",
        "bestOpeningAngle": "Offer a free scan tear sheet of what fires vs captured consent.",
        "researchSources": ["https://example.com/leadership", "https://example.com/news"],
    },
    "contacts": [
        {"name": "Dana Rivera", "title": "Senior Director, Privacy Counsel",
         "linkedin": "https://www.linkedin.com/in/example-dana", "sourceVerified": True,
         "sourceUrl": "https://www.linkedin.com/in/example-dana",
         "personalizationHook": "Posted about expanding the privacy team.",
         "toneGuidance": "Privacy-counsel voice.", "avoid": "Do not lead with their lawsuit."},
        {"name": "Sam Okonkwo", "title": "VP, Compliance",
         "linkedin": None, "sourceVerified": False, "sourceUrl": "",
         "personalizationHook": "Built the internal audit program.",
         "toneGuidance": "Operator voice.", "avoid": "Avoid legal-threat framing."},
    ],
}

SCORED = sa.score(CLASSIFICATION, AS_OF)


def test_header_and_verdict():
    h = bd.build_html(SCORED)
    assert "Acme Health" in h
    assert "Account Research Dossier" in h
    assert "QUALIFIED" in h
    assert ">120<" in h                       # final-score badge (fit 90 + why-now 30)
    assert "fit 90" in h and "why-now 30" in h


def test_why_now_card_chip_and_clickable_source():
    h = bd.build_html(SCORED)
    assert "Why now" in h
    assert "CIPA class action" in h
    assert "LITIGATION" in h                   # colored category chip
    assert 'href="https://example.com/cipa"' in h   # clickable source link


def test_fit_overview_and_internal_strategy():
    h = bd.build_html(SCORED)
    assert "Privacy &amp; consent surface" in h     # fit-criterion label (HTML-escaped &)
    assert "✓ MET" in h                             # ICP fit chip
    assert "confirmed via ObservePoint scan" in h   # measured evidence folded in
    assert "consumer healthcare web property" in h
    assert "tear sheet" in h                         # best opening angle
    assert "Internal strategy" in h                  # strategy-vs-copy label
    assert "Meta Pixel" in h                         # measured tag inventory


def test_contacts_verified_and_held_back():
    h = bd.build_html(SCORED)
    assert "Dana Rivera" in h and "Sam Okonkwo" in h
    assert "VERIFIED" in h                           # Dana verified
    assert "HELD BACK" in h                          # Sam unverified -> flagged, not hidden


def test_not_qualified_verdict():
    data = {**SCORED, "score": {**SCORED["score"], "qualified": False}}
    assert "NOT QUALIFIED" in bd.build_html(data)


def test_empty_triggers_renders_graceful_note():
    data = {**SCORED, "triggers": [], "score": {**SCORED["score"], "whyNowBreakdown": []}}
    assert "No acute web-tracking trigger event found" in bd.build_html(data)


def test_html_escapes_injected_markup():
    data = {**SCORED, "account": "<script>alert(1)</script>"}
    h = bd.build_html(data)
    assert "<script>alert(1)</script>" not in h       # not rendered raw
    assert "&lt;script&gt;" in h                       # escaped instead


def test_cli_writes_pdf_only(tmp_path):
    f = tmp_path / "scored.json"; f.write_text(json.dumps(SCORED))
    out = tmp_path / "dossier.pdf"
    res = subprocess.run([sys.executable, str(SCRIPT), str(f), str(out)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    printed = res.stdout.strip()
    html = out.with_suffix(".html")
    # PDF is best-effort (depends on a Chrome/weasyprint engine). When one is present, ONLY the .pdf
    # should land in the output folder — no .html beside it. Without an engine, the HTML is the fallback.
    if printed.endswith(".pdf"):
        assert pathlib.Path(printed).exists() and pathlib.Path(printed).stat().st_size > 0
        assert not html.exists()
    else:
        assert printed == str(html)
        assert html.exists() and "Acme Health" in html.read_text(encoding="utf-8")
