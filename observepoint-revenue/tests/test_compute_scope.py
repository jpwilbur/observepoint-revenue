import json
import pathlib
import subprocess
import sys

import pytest

import compute_scope as cs


def test_baked_tiers_shape():
    assert cs.BAKED_TIERS[0] == {"limit": 1_000, "pricePerPage": 0.0}
    assert cs.BAKED_TIERS[1]["pricePerPage"] == 0.17
    assert len(cs.BAKED_TIERS) == 6


def test_graduated_price_calibration():
    # Spec §10 fixture: 1,664,256 annual scans through the baked tiers.
    p = cs.graduated_price(1_664_256, cs.BAKED_TIERS)
    assert p["total"] == 133_030.24
    assert p["avg_per_page"] == 0.0799
    # bands hit: free, 0.17, 0.12, 0.06, 0.04 (5th band absorbs the remainder) = 5 priced bands
    assert len(p["breakdown"]) == 5
    assert p["breakdown"][1]["cost"] == 8_500.0   # 50,000 @ 0.17


def test_graduated_price_free_tier():
    p = cs.graduated_price(500, cs.BAKED_TIERS)
    assert p["total"] == 0.0


def test_graduated_price_first_paid_band():
    # 1,000 free + 9,000 @ 0.17
    p = cs.graduated_price(10_000, cs.BAKED_TIERS)
    assert p["total"] == round(9_000 * 0.17, 2)  # 1530.0


def test_classify_tier_boundaries():
    assert cs.classify_tier(599_999) == "starter"
    assert cs.classify_tier(600_000) == "professional"   # n < 600k is starter; 600k is not
    assert cs.classify_tier(6_000_000) == "professional"  # <= 6M
    assert cs.classify_tier(6_000_001) == "enterprise"
    assert cs.classify_tier(1_664_256) == "professional"


CALIBRATION_LAYERS = [
    {"name": "annual baseline", "pct": 1.0,   "runs_per_year": 1},
    {"name": "quarterly",       "pct": 0.05,  "runs_per_year": 4},
    {"name": "weekly",          "pct": 0.004, "runs_per_year": 52},
    {"name": "daily",           "pct": 0.0,   "runs_per_year": 365},
]


def test_use_case_pages():
    assert cs.use_case_pages(197_000, geographies=2, scenarios=3, environments=1) == 1_182_000


def test_annual_scans_layered_calibration():
    # Spec §10: 1,182,000 use-case pages through the calibration cadence = 1,664,256.
    out = cs.annual_scans(1_182_000, CALIBRATION_LAYERS)
    assert out["total"] == 1_664_256
    by = {l["name"]: l["runs"] for l in out["by_layer"]}
    assert by["annual baseline"] == 1_182_000
    assert by["quarterly"] == 236_400
    assert by["weekly"] == 245_856
    assert by["daily"] == 0


def test_apply_buffer():
    assert cs.apply_buffer(100_000, 0.10) == 110_000
    assert cs.apply_buffer(1_664_256, 0.0) == 1_664_256          # no-op
    assert cs.apply_buffer(1_664_256, 0.10) == 1_830_682          # round(…*1.1)


ROOT = pathlib.Path(__file__).resolve().parent.parent
COMPUTE = ROOT / "skills" / "scope-calculator" / "scripts" / "compute_scope.py"

BASE_INPUTS = {
    "customer": "Acme",
    "use_case": "privacy",
    "page_count": {"low": 180_000, "anchor": 197_000, "high": 210_000, "confidence": "MEDIUM"},
    "multipliers": {"geographies": 2, "scenarios": 3, "environments": 1},
    "cadence_layers": CALIBRATION_LAYERS,
    "buffer_pct": 0.0,
}


def test_compute_anchor_calibration():
    out = cs.compute(BASE_INPUTS)
    a = out["anchor"]
    assert a["use_case_pages"] == 1_182_000
    assert a["predicted_scans"] == 1_664_256
    assert a["purchased_scans"] == 1_664_256
    assert a["tier"] == "professional"
    assert a["price"]["total"] == 133_030.24
    assert a["implied_blended_frequency"] == round(1_664_256 / 1_182_000, 3)
    assert out["recommended_quote"]["price_total"] == 133_030.24
    assert out["pricing_source"].startswith("baked")  # no tiers passed → baked


def test_compute_range_is_monotonic():
    out = cs.compute(BASE_INPUTS)
    lo, hi = out["range"]["low"], out["range"]["high"]
    assert lo["purchased_scans"] < out["anchor"]["purchased_scans"] < hi["purchased_scans"]
    assert lo["price_total"] < out["anchor"]["price"]["total"] < hi["price_total"]


def test_compute_buffer_changes_purchased():
    inp = dict(BASE_INPUTS, buffer_pct=0.10)
    out = cs.compute(inp)
    assert out["anchor"]["predicted_scans"] == 1_664_256
    assert out["anchor"]["purchased_scans"] == 1_830_682
    assert out["anchor"]["price"]["total"] > 133_030.24


def test_compute_uses_passed_tiers_and_source():
    inp = dict(BASE_INPUTS, tiers=cs.BAKED_TIERS, pricing_source="live @ test")
    out = cs.compute(inp)
    assert out["pricing_source"] == "live @ test"


def test_cli_reads_json_writes_json(tmp_path):
    f = tmp_path / "in.json"
    f.write_text(json.dumps(BASE_INPUTS))
    res = subprocess.run([sys.executable, str(COMPUTE), str(f)],
                         capture_output=True, text=True)
    assert res.returncode == 0
    out = json.loads(res.stdout)
    assert out["anchor"]["price"]["total"] == 133_030.24


def test_graduated_price_zero():
    p = cs.graduated_price(0, cs.BAKED_TIERS)
    assert p["total"] == 0.0
    assert p["breakdown"] == []
    assert p["avg_per_page"] == 0.0


def test_graduated_price_empty_tiers_raises():
    with pytest.raises(ValueError):
        cs.graduated_price(100, [])


def test_annual_scans_empty_layers():
    out = cs.annual_scans(1_000_000, [])
    assert out["total"] == 0
    assert out["by_layer"] == []


def test_apply_buffer_zero_scans():
    assert cs.apply_buffer(0, 0.10) == 0


def test_compute_accepts_source_alias():
    inp = dict(BASE_INPUTS, tiers=cs.BAKED_TIERS, source="live @ alias")
    out = cs.compute(inp)
    assert out["pricing_source"] == "live @ alias"


def test_graduated_price_tail_beyond_bands():
    # Above the sum of all band widths the remainder prices at the last band's rate.
    total_width = sum(b["limit"] for b in cs.BAKED_TIERS)  # 56,551,000
    p = cs.graduated_price(total_width + 1_000_000, cs.BAKED_TIERS)
    tail = p["breakdown"][-1]
    assert tail["band_limit"] is None
    assert tail["pages"] == 1_000_000
    assert tail["rate"] == cs.BAKED_TIERS[-1]["pricePerPage"]


def test_scans_for_price_inverts_graduated():
    for scans in (10_000, 430_744, 1_664_256, 3_000_000):
        price = cs.graduated_price(scans, cs.BAKED_TIERS)["total"]
        assert abs(cs.scans_for_price(price, cs.BAKED_TIERS) - scans) <= 1


def test_scans_for_price_clean_target():
    s = cs.scans_for_price(54_000, cs.BAKED_TIERS)
    assert s == 430_167
    assert abs(cs.graduated_price(s, cs.BAKED_TIERS)["total"] - 54_000) < 0.5


def test_compute_recommended_contract():
    rc = cs.compute(BASE_INPUTS)["recommended_contract"]
    assert rc["price"] == 133_000                       # nearest $1,000 of 133,030.24
    assert rc["scans"] == cs.scans_for_price(133_000, cs.BAKED_TIERS)
    assert abs(cs.graduated_price(rc["scans"], cs.BAKED_TIERS)["total"] - 133_000) < 1


# --- buffer-crosses-tier flag (Part C) -------------------------------------------------
# One layer @ pct=1.0, runs=1 and all multipliers 1 → predicted_scans == base_pages, so we can
# place predicted and buffered counts on either side of the 600k starter/professional boundary.
_FLAT_LAYER = [{"name": "annual baseline", "pct": 1.0, "runs_per_year": 1}]
_FLAT_INPUTS = {
    "customer": "Tier Test",
    "page_count": {"low": 590_000, "anchor": 590_000, "high": 590_000, "confidence": "HIGH"},
    "multipliers": {"geographies": 1, "scenarios": 1, "environments": 1},
    "cadence_layers": _FLAT_LAYER,
}


def test_tier_changed_by_buffer_true_when_buffer_straddles_boundary():
    # 590,000 predicted (starter) → ×1.10 = 649,000 purchased (professional): flag True.
    out = cs.compute(dict(_FLAT_INPUTS, buffer_pct=0.10))
    a = out["anchor"]
    assert a["predicted_scans"] == 590_000
    assert a["purchased_scans"] == 649_000
    assert cs.classify_tier(a["predicted_scans"]) == "starter"
    assert cs.classify_tier(a["purchased_scans"]) == "professional"
    assert a["tier_changed_by_buffer"] is True


def test_tier_changed_by_buffer_false_same_tier():
    # Same predicted count, no buffer → predicted and purchased both starter: flag False.
    out = cs.compute(dict(_FLAT_INPUTS, buffer_pct=0.0))
    a = out["anchor"]
    assert a["predicted_scans"] == a["purchased_scans"] == 590_000
    assert a["tier_changed_by_buffer"] is False


def test_tier_changed_by_buffer_false_when_buffer_stays_in_tier():
    # 100,000 predicted (starter) → ×1.10 = 110,000 purchased (still starter): flag False.
    inp = dict(_FLAT_INPUTS, buffer_pct=0.10)
    inp["page_count"] = {"low": 100_000, "anchor": 100_000, "high": 100_000, "confidence": "HIGH"}
    a = cs.compute(inp)["anchor"]
    assert a["predicted_scans"] == 100_000 and a["purchased_scans"] == 110_000
    assert a["tier_changed_by_buffer"] is False


# --- friendly input validation (Part B) ------------------------------------------------
def _run_cli(stdin_text):
    return subprocess.run([sys.executable, str(COMPUTE)], input=stdin_text,
                          capture_output=True, text=True)


def test_cli_friendly_error_missing_cadence_layers():
    bad = dict(BASE_INPUTS)
    bad.pop("cadence_layers")
    res = _run_cli(json.dumps(bad))
    assert res.returncode != 0
    assert "missing" in res.stderr.lower()
    assert "cadence_layers" in res.stderr
    assert "Traceback" not in res.stderr and "KeyError" not in res.stderr


def test_cli_friendly_error_missing_page_count():
    bad = dict(BASE_INPUTS)
    bad.pop("page_count")
    res = _run_cli(json.dumps(bad))
    assert res.returncode != 0
    assert "missing" in res.stderr.lower() and "page_count" in res.stderr
    assert "Traceback" not in res.stderr and "KeyError" not in res.stderr


def test_cli_friendly_error_malformed_json():
    res = _run_cli("{not valid json")
    assert res.returncode != 0
    assert "Traceback" not in res.stderr
    assert "scope-calculator" in res.stderr
