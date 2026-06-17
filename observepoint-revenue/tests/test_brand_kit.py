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


import brand_kit  # noqa: E402  (conftest puts branding-guide/scripts on the path)


def test_theme_resolves_surface_accent_and_logo():
    dark = brand_kit.theme("dark")
    assert dark["accent"].upper() == "#F2CD14"
    assert dark["bg"].upper() == "#14151A"
    assert dark["logo"] == "primary"
    light = brand_kit.theme("light")
    assert light["text"].upper() == "#1E1E1E"
    assert light["logo"] == "ink"


def test_default_theme_for_format():
    assert brand_kit.default_theme_for("dossier") == "dark"
    assert brand_kit.default_theme_for(".xlsx") == "light"
    assert brand_kit.default_theme_for("proposal") == "light"
    assert brand_kit.default_theme_for("deck") == "dark"
    assert brand_kit.default_theme_for("unknown-format") == "dark"  # safe default


def test_logo_path_picks_variant_and_falls_back():
    assert brand_kit.logo_path("dark").endswith("logo-primary.png")
    assert brand_kit.logo_path("light").endswith("logo-ink.png")
    # secondary file not provided -> falls back to primary
    assert brand_kit.logo_path("dark", variant="secondary").endswith("logo-primary.png")


def test_copyright_and_font():
    assert brand_kit.copyright(2026) == "© 2026 ObservePoint. All rights reserved."
    assert brand_kit.font()["family"] == "Montserrat"


def test_naming_company_and_disallowed():
    n = brand_kit.naming()
    assert n["company"] == "ObservePoint"
    assert "Observepoint" in n["disallowed"]
