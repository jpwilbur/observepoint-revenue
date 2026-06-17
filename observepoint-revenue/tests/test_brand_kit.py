# observepoint-revenue/tests/test_brand_kit.py
import json
import pathlib

SKILL = pathlib.Path(__file__).resolve().parent.parent / "skills" / "branding-guide"
SPEC = SKILL / "references" / "brand-spec.json"


def test_spec_is_valid_json_with_required_sections():
    spec = json.loads(SPEC.read_text())
    for key in ("meta", "naming", "colors", "typography", "logos", "themes", "format_defaults", "boilerplate"):
        assert key in spec, f"missing top-level section: {key}"


def test_brand_yellow_is_canonical():
    spec = json.loads(SPEC.read_text())
    assert spec["colors"]["brand_yellow"].upper() == "#F2CD14"


def test_bundled_assets_exist():
    for f in ("logo-primary.png", "logo-ink.png", "favicon.png"):
        assert (SKILL / "assets" / f).exists(), f"missing asset {f}"
