import json
import pathlib
import subprocess
import sys

import pytest
from docx import Document

import build_proposal as bp
import compute_scope as cs

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "scope-calculator" / "scripts" / "build_proposal.py"

DATA = {
    "customer": "Arthur J. Gallagher",
    "prepared_by": "Jarrod Wilbur",
    "date": "2026-06-07",
    "use_case": "privacy / consent monitoring",
    "domains": ["ajg.com"],
    "properties_note": "233 web properties identified.",
    "regulations": ["CCPA/CPRA"],
    "monitoring_summary": "Annual full-site privacy & consent monitoring across all properties, "
                          "with quarterly and monthly re-checks of consent-critical pages.",
    "page_count": {"low": 95_721, "anchor": 95_721, "high": 108_155, "confidence": "MEDIUM",
                   "url_total": 485_096, "defensible": 95_721, "discounted": 389_375,
                   "census_id": 711, "crawl_status": "running",
                   "spiral_note": "Excluded ~389,375 query-string-duplicate URLs across 6 properties."},
    "consent_states": {"count": 3, "names": ["Default", "Opt-Out", "GPC"]},
    "cadence_layers": [
        {"name": "Full privacy sweep", "runs_per_year": 1, "pages": 287_163, "runs": 287_163,
         "why": "A full sweep so nothing on the site is invisible."},
        {"name": "Priority pages", "runs_per_year": 4, "pages": 14_358, "runs": 57_432,
         "why": "Sites drift — quarterly keeps the full picture current."},
        {"name": "Consent-critical pages", "runs_per_year": 12, "pages": 7_179, "runs": 86_149,
         "why": "Crown-jewel pages checked far more often."}],
    "usage": {"pages_per_sweep": 287_163, "annual_scans": 430_744},
    "pricing": {"recommended_price": 54_000, "recommended_scans": 430_167,
                "range_low_price": 54_069, "range_high_price": 60_784,
                "price_by_band": [{"band_limit": 1000, "rate": 0.0, "pages": 1000, "cost": 0.0},
                                  {"band_limit": 50000, "rate": 0.17, "pages": 50000, "cost": 8500.0},
                                  {"band_limit": 500000, "rate": 0.12, "pages": 379744, "cost": 45569.28}],
                "pricing_source": "live @ https://app.observepoint.com/www-pricing/main.js",
                "modeled_scans": 430_744, "modeled_price": 54_069.28},
    "internal": {"assumptions": ["Geographies defaulted to 1 — confirm regions.",
                                 "Consent states assumed CCPA (3) — confirm regulations."],
                 "implied_frequency": 1.5,
                 "thresholds_swept": "5000/1.3=95721; 10000/1.5=95721; 20000/2.0=106638"},
}


def _text(doc):
    parts = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                parts.append(c.text)
    return "\n".join(parts)


def test_customer_sections_and_derivation():
    t = _text(bp.build_proposal(DATA))
    assert "Arthur J. Gallagher" in t
    assert "Your web footprint" in t
    assert "96,000" in t                       # anchor rounded for the customer (not 95,721)
    assert "How your annual usage is calculated" in t
    assert "page scan" in t.lower()            # the unit is defined
    assert "Default" in t and "Opt-Out" in t and "GPC" in t
    assert "287,163" in t                       # pages per full sweep (the consent-state multiply)
    assert "Annually" in t and "Quarterly" in t and "Monthly" in t  # the frequencies, explicit
    assert "430,744" in t                       # annual page scans total
    assert "Recommended contract" in t
    assert "430,167" in t and "$54,000" in t    # the reconciling pair
    assert "Scope detail" in t                          # points to the live model tabs
    assert "investment model" in t.lower()             # customer workbook is now the live model
    assert "live" in t.lower()                         # emphasises the interactive nature


def test_recommended_pair_reconciles_in_calculator():
    # The page-scans and price shown MUST match the graduated calculator (the rep's whole ask).
    s = DATA["pricing"]["recommended_scans"]
    assert abs(cs.graduated_price(s, cs.BAKED_TIERS)["total"] - DATA["pricing"]["recommended_price"]) < 1


def test_no_internal_section_or_confidence_in_customer_doc():
    t = _text(bp.build_proposal(DATA))
    assert "[INTERNAL" not in t                 # the strippable section is gone
    assert "485,096" not in t                   # raw URL total never in the customer doc
    assert "711" not in t                       # census id never in the customer doc
    assert "CONFIDENCE" not in t.upper()        # confidence moved to the internal file
    for term in ("census", "spiral", "raw url", "defensible", "anchor"):
        assert term not in t.lower(), f"leaked internal term: {term}"


def test_cadence_table_shows_the_why():
    t = _text(bp.build_proposal(DATA))
    assert "Why" in t                                            # the new column header
    assert "nothing on the site is invisible" in t              # a rationale line, customer-facing


def test_clean_guard_rejects_internal_terms_in_narrative():
    d = json.loads(json.dumps(DATA))
    d["monitoring_summary"] = "We discounted query-param spiral URLs."
    with pytest.raises(ValueError):
        bp.build_proposal(d)


def test_clean_guard_allows_internal_section_terms():
    # 'spiral'/'query-string' etc. live in the INTERNAL fields by design — must NOT trip the guard.
    d = json.loads(json.dumps(DATA))
    d["page_count"]["spiral_note"] = "6 query-param spiral domains discounted."
    bp.build_proposal(d)  # must not raise


def test_clean_guard_allows_collision_identity():
    d = json.loads(json.dumps(DATA))
    d["customer"] = "Discount Tire Co"
    d["domains"] = ["spiral-galaxy.com"]
    d["monitoring_summary"] = "Full-site privacy sweep annually."
    t = _text(bp.build_proposal(d))  # must not raise
    assert "Discount Tire Co" in t


def _with_anchor(low, anchor, high):
    d = json.loads(json.dumps(DATA))
    d["page_count"].update(low=low, anchor=anchor, high=high)
    return d


def test_round_sig_preserves_small_and_distinguishes_neighbors():
    # The bug: round-to-nearest-1000 turned ~80 pages into "0" and collided 4,722 & 5,398 at "5,000".
    assert bp._round_sig(80) == 80          # was 0
    assert bp._round_sig(4_722) == 4_700    # was 5,000
    assert bp._round_sig(5_398) == 5_400    # was 5,000 (collided with 4,722)
    assert bp._round_sig(95_721) == 96_000  # matches the methodology's 2-sig-fig example
    assert bp._round_sig(108_155) == 110_000
    assert bp._round_sig(0) == 0


def test_small_footprint_not_zero():
    t = _text(bp.build_proposal(_with_anchor(80, 80, 80)))
    assert "80 pages" in t                       # the real count, not collapsed
    assert "approximately 0 pages" not in t      # the bug symptom: round-to-1000 made ~80 read as 0
    assert "range 0–0" not in t


def test_neighbor_counts_render_distinctly():
    tc = _text(bp.build_proposal(_with_anchor(4_722, 4_722, 4_722)))
    tg = _text(bp.build_proposal(_with_anchor(5_398, 5_398, 5_398)))
    assert "4,700 pages" in tc and "5,400 pages" in tg   # not both collapsed to "5,000 pages"


def test_cli_writes_docx(tmp_path):
    f = tmp_path / "in.json"; f.write_text(json.dumps(DATA))
    out = tmp_path / "p.docx"
    res = subprocess.run([sys.executable, str(SCRIPT), str(f), str(out)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == str(out)
    assert "Arthur J. Gallagher" in _text(Document(out))


# --- friendly input validation (Part B) ------------------------------------------------
def test_cli_friendly_error_missing_required_key(tmp_path):
    bad = json.loads(json.dumps(DATA))
    bad.pop("page_count")
    f = tmp_path / "bad.json"; f.write_text(json.dumps(bad))
    out = tmp_path / "p.docx"
    res = subprocess.run([sys.executable, str(SCRIPT), str(f), str(out)],
                         capture_output=True, text=True)
    assert res.returncode != 0
    assert "missing" in res.stderr.lower() and "page_count" in res.stderr
    assert "Traceback" not in res.stderr and "KeyError" not in res.stderr


def test_cli_friendly_error_malformed_json(tmp_path):
    f = tmp_path / "bad.json"; f.write_text("{not valid json")
    out = tmp_path / "p.docx"
    res = subprocess.run([sys.executable, str(SCRIPT), str(f), str(out)],
                         capture_output=True, text=True)
    assert res.returncode != 0
    assert "Traceback" not in res.stderr
    assert "scope-calculator" in res.stderr


def test_clean_guard_rejects_internal_term_in_cadence_name():
    d = json.loads(json.dumps(DATA))
    d["cadence_layers"][1]["name"] = "Quarterly spiral re-check"   # internal term in a customer label
    with pytest.raises(ValueError):
        bp.build_proposal(d)


def test_clean_guard_rejects_internal_term_in_why():
    d = json.loads(json.dumps(DATA))
    d["cadence_layers"][0]["why"] = "Full crawl to find every defensible page."
    with pytest.raises(ValueError):
        bp.build_proposal(d)


def test_clean_guard_allows_identity_collision_in_name_and_domain():
    d = json.loads(json.dumps(DATA))
    d["customer"] = "Discount Tire Co"
    d["domains"] = ["spiral-galaxy.com"]
    d["monitoring_summary"] = "Full-site privacy monitoring annually."
    bp.build_proposal(d)  # identity fields are not scrubbed → must not raise


def test_clean_guard_rejects_internal_term_in_properties_note():
    d = json.loads(json.dumps(DATA))
    d["properties_note"] = "Site census crawl excluded spiral pages."
    with pytest.raises(ValueError):
        bp.build_proposal(d)


def test_proposal_does_not_mention_removed_methodology_sheet_or_internal_terms():
    """Regression: customer workbook has no Methodology sheet; proposal must not advertise it.
    Also guards against internal-derivation language leaking into the rendered customer document."""
    t = _text(bp.build_proposal(DATA))
    # The Methodology sheet was removed from the customer workbook in Phase A.
    assert "Methodology" not in t, "proposal advertises the removed Methodology workbook sheet"
    # Internal-derivation terms must not appear in the customer-facing proposal.
    for term in ("census", "spiral", "raw url", "defensible", "reduced",
                 "crawl", "query-param", "query-string", "recursion", "collapsed"):
        assert term not in t.lower(), f"internal term leaked into proposal: {term!r}"


def test_frequency_advisor_reference_exists_and_has_ladder():
    refs = pathlib.Path(__file__).resolve().parent.parent / "skills" / "scope-calculator" / "references"
    doc = (refs / "frequency-advisor.md").read_text().lower()
    for layer in ("baseline inventory", "inventory refresh", "compliance", "release catch", "critical watch"):
        assert layer in doc
    for pct in ("100%", "50%", "15%", "5%", "1%"):
        assert pct in doc
