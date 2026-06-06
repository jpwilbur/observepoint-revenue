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
    # bands hit: free, 0.17, 0.12, 0.06, 0.04 (tail) = 5 priced bands
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


import json
import subprocess
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMPUTE = ROOT / "skills" / "size-and-price" / "scripts" / "compute_scope.py"

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
