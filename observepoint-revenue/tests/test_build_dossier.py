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
    # Badge shows the two components explicitly (fit 90 + why-now 30), not a bare 120 on a 0-100 scale.
    assert "Fit" in h and "90" in h
    assert "Why-now" in h and "30" in h


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


def test_badge_shows_fit_and_whynow_as_labeled_components_not_bare_total():
    # A multi-trigger account: fitScore 100 (all 6 ICP criteria met) + whyNowScore 42
    # (pixelWiretapSuit 30 + complianceDeadline 12, both full strength) -> finalScore 142.
    # 142 on a badge that reads as a 0-100 scale is misleading; the badge must label both components.
    big = {
        **CLASSIFICATION,
        "fit": [
            {"key": "privacyConsentSurface", "met": True, "evidence": "CMP."},
            {"key": "regulatoryExposure", "met": True, "evidence": "HIPAA."},
            {"key": "tagPixelDensity", "met": True, "evidence": "GTM."},
            {"key": "webScale", "met": True, "evidence": "Many pages."},
            {"key": "targetVertical", "met": True, "evidence": "Healthcare."},
            {"key": "analyticsAccuracy", "met": True, "evidence": "GA4 reliance."},
        ],
        "triggers": [
            {"description": "CIPA pixel suit.", "date": "2026-05-01", "sourceUrl": "https://x/a",
             "category": "litigation", "scoreKey": "pixelWiretapSuit"},
            {"description": "Consent Mode v2 deadline exposure.", "date": "2026-05-01",
             "sourceUrl": "https://x/b", "category": "other", "scoreKey": "complianceDeadline"},
        ],
    }
    scored = sa.score(big, AS_OF)
    assert scored["score"]["fitScore"] == 100
    assert scored["score"]["whyNowScore"] == 42
    assert scored["score"]["finalScore"] == 142
    h = bd.build_html(scored)
    # Both components must appear as distinct labeled values.
    assert "100" in h
    assert "42" in h
    assert "Fit" in h and "Why-now" in h
    # The bare combined total must NOT be the lone number rendered as the score badge.
    assert ">142<" not in h


def test_whynow_renders_from_breakdown_not_description_join():
    # Two triggers with IDENTICAL descriptions but different points/dates. The old code keyed points
    # to triggers by free-text description, so it would collapse/mis-assign them. Rendering from
    # whyNowBreakdown (which carries per-trigger points) must show BOTH with their correct points.
    scored = {
        **CLASSIFICATION,
        "triggers": [
            {"description": "Pixel litigation update.", "date": "2026-05-01",
             "sourceUrl": "https://x/new", "category": "litigation", "scoreKey": "pixelWiretapSuit"},
            {"description": "Pixel litigation update.", "date": "2021-01-01",
             "sourceUrl": "https://x/old", "category": "litigation", "scoreKey": "settlement"},
        ],
        "score": {
            "fitScore": 90, "whyNowScore": 32, "finalScore": 122, "qualified": True,
            "lowFitHighTrigger": False, "fitBreakdown": [],
            "whyNowBreakdown": [
                {"key": "pixelWiretapSuit", "label": "Active pixel/wiretap suit", "basePoints": 30,
                 "points": 30, "description": "Pixel litigation update.", "date": "2026-05-01",
                 "sourceUrl": "https://x/new"},
                {"key": "settlement", "label": "Settlement finalized", "basePoints": 15,
                 "points": 2, "description": "Pixel litigation update.", "date": "2021-01-01",
                 "sourceUrl": "https://x/old"},
            ],
        },
    }
    h = bd.build_html(scored)
    # Both distinct point values must render — the description-join would have shown one twice.
    assert "+30" in h
    assert "+2" in h
    # Both sources must render (they differ even though descriptions match).
    assert 'href="https://x/new"' in h
    assert 'href="https://x/old"' in h


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
