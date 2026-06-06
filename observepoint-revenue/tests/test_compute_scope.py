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
