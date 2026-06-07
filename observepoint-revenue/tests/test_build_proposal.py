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
        {"name": "Full privacy sweep", "runs_per_year": 1, "pages": 287_163, "runs": 287_163},
        {"name": "Priority pages", "runs_per_year": 4, "pages": 14_358, "runs": 57_432},
        {"name": "Consent-critical pages", "runs_per_year": 12, "pages": 7_179, "runs": 86_149}],
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
    assert "Sample Pages" in t and "Methodology" in t   # points to the evidence workbook sheets


def test_recommended_pair_reconciles_in_calculator():
    # The page-scans and price shown MUST match the graduated calculator (the rep's whole ask).
    s = DATA["pricing"]["recommended_scans"]
    assert abs(cs.graduated_price(s, cs.BAKED_TIERS)["total"] - DATA["pricing"]["recommended_price"]) < 1


def test_internal_section_marked_and_present():
    t = _text(bp.build_proposal(DATA))
    assert "[INTERNAL — REMOVE BEFORE SENDING TO CUSTOMER]" in t
    assert "485,096" in t                       # raw URL total — internal only
    assert "711" in t                           # census id
    assert "confirm regulations" in t.lower()   # an assumption surfaced for the rep


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


def test_cli_writes_docx(tmp_path):
    f = tmp_path / "in.json"; f.write_text(json.dumps(DATA))
    out = tmp_path / "p.docx"
    res = subprocess.run([sys.executable, str(SCRIPT), str(f), str(out)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == str(out)
    assert "Arthur J. Gallagher" in _text(Document(out))
