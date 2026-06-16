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
    "multipliers": {"geographies": 1, "scenarios": 3, "environments": 1},
    "cadence_layers": [
        {"name": "Full privacy sweep", "runs_per_year": 1, "pct": 1.0,
         "why": "A full sweep so nothing on the site is invisible."},
        {"name": "Priority pages", "runs_per_year": 4, "pct": 0.05,
         "why": "Sites drift — quarterly keeps the full picture current."},
        {"name": "Consent-critical pages", "runs_per_year": 12, "pct": 0.025,
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
    # Keep the sweep chain consistent with the mutated anchor so the §3 reconciliation guard
    # doesn't trip — these tests exercise §1 footprint rounding, not §3.
    mx = d["multipliers"]
    d["usage"]["pages_per_sweep"] = anchor * mx["geographies"] * mx["scenarios"] * mx["environments"]
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


# ---------------------------------------------------------------------------
# Gilead-like fixture: multi-geography, full multiplier chain
# ---------------------------------------------------------------------------
GILEAD_DATA = {
    "customer": "Gilead Sciences",
    "prepared_by": "Jarrod Wilbur",
    "date": "2026-06-16",
    "use_case": "privacy / consent monitoring",
    "domains": ["gilead.com"],
    "monitoring_summary": "Annual full-site privacy monitoring across all regions and consent states.",
    "page_count": {"low": 700, "anchor": 848, "high": 1000},
    "consent_states": {"count": 3, "names": ["Pre-consent", "Opt-Out", "GPC"]},
    "multipliers": {"geographies": 3, "scenarios": 3, "environments": 1},
    "cadence_layers": [
        {"name": "Baseline inventory",    "why": "Full sweep so nothing is invisible.",
         "pct": 1.0,  "runs_per_year": 1},
        {"name": "Quarterly re-check",    "why": "Sites drift — quarterly keeps the picture current.",
         "pct": 0.5,  "runs_per_year": 4},
        {"name": "Monthly compliance",    "why": "Crown-jewel pages checked far more often.",
         "pct": 0.15, "runs_per_year": 12},
        {"name": "Weekly critical watch", "why": "High-risk pages watched weekly.",
         "pct": 0.05, "runs_per_year": 52},
    ],
    "usage": {"pages_per_sweep": 7632, "annual_scans": 56477},
    "pricing": {"recommended_price": 8_000, "recommended_scans": 56_477,
                "range_low_price": 7_500, "range_high_price": 9_000},
    "regulations": ["CCPA/CPRA"],
}


def test_gilead_sweep_table_has_geographies_row():
    """(a) A Geographies row with ×3 must appear; (b) consent states ×3 present;
    (c) 7,632 is shown; (d) chain reconciles 848×3×3=7,632; (e+f) cadence rows derive
    correctly from pct — not from missing pages/runs keys."""
    t = _text(bp.build_proposal(GILEAD_DATA))

    # (a) geographies row with ×3
    assert "×3" in t or "x3" in t.lower() or "Geographies" in t, \
        "Expected a Geographies ×3 row in the sweep table"
    # narrow: geographies label + multiplier must both be present
    assert "Geographies" in t
    # find the ×3 occurrence near geographies
    assert "×3" in t

    # (b) consent states ×3
    assert "Pre-consent" in t and "Opt-Out" in t and "GPC" in t
    # consent states row also has ×3
    assert t.count("×3") >= 2  # at least geographies row + consent row

    # (c) pages per full sweep shown
    assert "7,632" in t

    # (d) chain reconciles: 848 × 3 × 3 = 7,632 — anchor must appear
    assert "848" in t

    # (e) first cadence row: pct=1.0, runs=1 → pages_each = round(7632*1.0) = 7,632
    #     scans = round(7632*1.0*1) = 7,632   (NOT zero)
    assert t.count("7,632") >= 2  # at minimum: pages_per_sweep cell + first cadence pages_each

    # (f) quarterly row: pct=0.5, runs=4 → pages_each=3,816; scans=15,264
    assert "3,816" in t
    assert "15,264" in t


def test_gilead_environments_row_hidden_when_one():
    """environments=1 → no Environments row should appear."""
    t = _text(bp.build_proposal(GILEAD_DATA))
    assert "Environments" not in t


def test_gilead_environments_row_shown_when_gt_one():
    """environments=2 → an Environments row must appear."""
    import copy
    d = copy.deepcopy(GILEAD_DATA)
    d["multipliers"]["environments"] = 2
    # recalculate pages_per_sweep: 848*3*3*2 = 15264
    d["usage"]["pages_per_sweep"] = 15264
    d["usage"]["annual_scans"] = 112954
    t = _text(bp.build_proposal(d))
    assert "Environments" in t
    assert "×2" in t


# ---------------------------------------------------------------------------
# Regression: the §3 multiplier chain MUST reconcile to usage.pages_per_sweep.
# Production bug (Gilead, geos=3): the orchestrator passed geographies=1 in the
# proposal payload while usage.pages_per_sweep already baked geos in (848×3×3 =
# 7,632). The geographies row was silently dropped and §3 showed 848 → 7,632
# with no factor explaining the jump. A non-reconciling proposal must be
# REFUSED, not shipped as a wrong customer doc. The §3 factors are not allowed
# to drift from compute_scope's authoritative output.
# ---------------------------------------------------------------------------
def _gilead_with_dropped_geo():
    """The exact production failure: multipliers.geographies forgotten (defaults to 1),
    but usage still reflects the real geos=3 the engine used (848×3×3 = 7,632)."""
    d = json.loads(json.dumps(GILEAD_DATA))
    d["multipliers"]["geographies"] = 1            # dropped by the orchestrator
    assert d["usage"]["pages_per_sweep"] == 7632   # engine still used geos=3
    return d


def test_dropped_geo_multiplier_is_rejected_not_silently_rendered():
    with pytest.raises(ValueError):
        bp.build_proposal(_gilead_with_dropped_geo())


def test_cli_friendly_error_on_unreconciled_sweep(tmp_path):
    f = tmp_path / "bad.json"; f.write_text(json.dumps(_gilead_with_dropped_geo()))
    out = tmp_path / "p.docx"
    res = subprocess.run([sys.executable, str(SCRIPT), str(f), str(out)],
                         capture_output=True, text=True)
    assert res.returncode != 0
    assert "Traceback" not in res.stderr and "KeyError" not in res.stderr
    assert "reconcile" in res.stderr.lower()
    assert "7,632" in res.stderr            # the message names the mismatch so it can be fixed
    assert not out.exists()                 # a wrong customer doc must NOT be written


def test_consistent_chain_still_renders():
    # The correct payload (geos=3, pages_per_sweep=7,632) must still build cleanly.
    bp.build_proposal(GILEAD_DATA)          # must not raise


def test_environments_one_point_five_reconciles():
    # Fractional environment multiplier (1.5) must not trip the reconciliation guard.
    d = json.loads(json.dumps(GILEAD_DATA))
    d["multipliers"] = {"geographies": 1, "scenarios": 3, "environments": 1.5}
    d["usage"]["pages_per_sweep"] = round(848 * 1 * 3 * 1.5)   # 3,816
    d["usage"]["annual_scans"] = 28239
    bp.build_proposal(d)                    # must not raise
