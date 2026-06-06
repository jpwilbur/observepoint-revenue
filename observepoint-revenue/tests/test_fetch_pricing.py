import json
import subprocess
import sys
import pathlib

import fetch_pricing as fp
import compute_scope as cs

ROOT = pathlib.Path(__file__).resolve().parent.parent
FETCH = ROOT / "skills" / "size-and-price" / "scripts" / "fetch_pricing.py"

# Representative snippet copied from the live bundle (app.observepoint.com/www-pricing/main.js).
SAMPLE_JS = (
    'var Gt=[{limit:1e3,pricePerPage:0},{limit:5e4,pricePerPage:.17},'
    '{limit:5e5,pricePerPage:.12},{limit:1e6,pricePerPage:.06},'
    '{limit:5e6,pricePerPage:.04},{limit:5e7,pricePerPage:.03}],Nn=1e3,Jr=5e7'
)


def test_parse_tiers_from_sample():
    tiers = fp.parse_tiers(SAMPLE_JS)
    assert tiers == [
        {"limit": 1_000, "pricePerPage": 0.0},
        {"limit": 50_000, "pricePerPage": 0.17},
        {"limit": 500_000, "pricePerPage": 0.12},
        {"limit": 1_000_000, "pricePerPage": 0.06},
        {"limit": 5_000_000, "pricePerPage": 0.04},
        {"limit": 50_000_000, "pricePerPage": 0.03},
    ]


def test_parse_tiers_missing_returns_none():
    assert fp.parse_tiers("no pricing here") is None


def test_validate_tiers():
    assert fp.validate_tiers(cs.BAKED_TIERS) is True
    assert fp.validate_tiers(None) is False
    assert fp.validate_tiers(cs.BAKED_TIERS[:3]) is False                  # < 5 bands
    bad = [dict(b) for b in cs.BAKED_TIERS]; bad[2]["limit"] = 10          # non-monotonic
    assert fp.validate_tiers(bad) is False


def test_fetch_pricing_live():
    out = fp.fetch_pricing(fetcher=lambda url: SAMPLE_JS)
    assert out["source"].startswith("live")
    assert out["tiers"][1]["pricePerPage"] == 0.17


def test_fetch_pricing_fallback_on_error():
    def boom(url):
        raise RuntimeError("network down")
    out = fp.fetch_pricing(fetcher=boom)
    assert out["source"].startswith("fallback")
    assert out["tiers"] == cs.BAKED_TIERS


def test_fetch_pricing_fallback_on_garbage():
    out = fp.fetch_pricing(fetcher=lambda url: "garbage")
    assert out["source"].startswith("fallback")
    assert out["tiers"] == cs.BAKED_TIERS


def test_cli_emits_json():
    res = subprocess.run([sys.executable, str(FETCH), "--offline"],
                         capture_output=True, text=True)
    assert res.returncode == 0
    out = json.loads(res.stdout)
    assert "tiers" in out and "source" in out


def test_parse_tiers_ignores_sibling_var():
    # A sibling minified var must NOT be matched instead of the real Gt.
    js = (
        "var vGt=[{limit:9,pricePerPage:9}];"
        "var Gt=[{limit:1e3,pricePerPage:0},{limit:5e4,pricePerPage:.17},"
        "{limit:5e5,pricePerPage:.12},{limit:1e6,pricePerPage:.06},"
        "{limit:5e6,pricePerPage:.04},{limit:5e7,pricePerPage:.03}]"
    )
    tiers = fp.parse_tiers(js)
    assert len(tiers) == 6
    assert tiers[0] == {"limit": 1_000, "pricePerPage": 0.0}


def test_validate_tiers_negative_rate():
    bad = [dict(b) for b in cs.BAKED_TIERS]
    bad[1]["pricePerPage"] = -0.01
    assert fp.validate_tiers(bad) is False
