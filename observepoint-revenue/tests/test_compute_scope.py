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
