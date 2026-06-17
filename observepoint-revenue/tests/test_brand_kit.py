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


import subprocess as _sp
import sys as _sys


def test_rgbcolor_parses_hex():
    from docx.shared import RGBColor
    assert brand_kit.rgbcolor("#1E1E1E") == RGBColor(0x1E, 0x1E, 0x1E)
    assert brand_kit.rgbcolor("F2CD14") == RGBColor(0xF2, 0xCD, 0x14)


def test_xlsx_font_and_fill_use_brand():
    f = brand_kit.xlsx_font(bold=True, size=12)
    assert f.name == "Montserrat" and f.bold is True
    fill = brand_kit.xlsx_fill("#F2CD14")
    assert fill.fgColor.rgb.endswith("F2CD14")


def test_css_vars_block_contains_accent_and_font():
    block = brand_kit.css_vars("dark")
    assert block.startswith(":root{") and block.endswith("}")
    assert "--op-accent:#F2CD14;" in block
    assert "--op-bg:#14151A;" in block
    assert "Montserrat" in block


def test_logo_data_uri_is_base64_png():
    uri = brand_kit.logo_data_uri("dark")
    assert uri.startswith("data:image/png;base64,")
    assert len(uri) > 200


def test_html_to_pdf_returns_none_without_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(brand_kit, "_find_chrome", lambda: None)
    import builtins
    real_import = builtins.__import__

    def no_weasy(name, *a, **k):
        if name == "weasyprint":
            raise ImportError("blocked for test")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_weasy)
    html = tmp_path / "x.html"
    html.write_text("<html><body>hi</body></html>")
    assert brand_kit.html_to_pdf(str(html), str(tmp_path / "x.pdf")) is None
    assert brand_kit.html_to_pdf(str(html), str(tmp_path / "x2.pdf"), timeout=5) is None


def test_emit_json_cli_prints_spec():
    out = _sp.run([_sys.executable, str(brand_kit.__file__), "--emit-json"],
                  capture_output=True, text=True)
    assert out.returncode == 0
    import json as _json
    assert _json.loads(out.stdout)["colors"]["brand_yellow"].upper() == "#F2CD14"


def test_proposal_uses_brand_kit_constants():
    import build_proposal
    assert build_proposal.FONT == brand_kit.font()["family"]
    assert build_proposal.YELLOW_HEX.upper() == brand_kit.brand_yellow().lstrip("#").upper()
    assert build_proposal.DARK_HEX.upper() == brand_kit.colors()["ink"].lstrip("#").upper()
    assert build_proposal.LIGHT_HEX.upper() == brand_kit.colors()["light"]["fill"].lstrip("#").upper()


def test_model_uses_brand_kit_constants():
    import build_model
    assert build_model.FONT == brand_kit.font()["family"]
    assert build_model.YELLOW.upper() == brand_kit.brand_yellow().lstrip("#").upper()
    assert build_model.DARK.upper() == brand_kit.colors()["ink"].lstrip("#").upper()


def test_internal_evidence_uses_brand_kit_constants():
    import build_internal_evidence as bie
    assert bie.YELLOW.upper() == brand_kit.brand_yellow().lstrip("#").upper()
    assert bie.RED.upper() == brand_kit.colors()["semantic"]["alert"].lstrip("#").upper()


def test_dossier_uses_brand_kit_palette():
    import build_dossier
    d = brand_kit.theme("dark")
    assert build_dossier.YELLOW.upper() == brand_kit.brand_yellow().upper()
    assert build_dossier.BG.upper() == d["bg"].upper()
    assert build_dossier.PANEL.upper() == d["panel"].upper()
    assert build_dossier.TEXT.upper() == d["text"].upper()
    assert build_dossier.RED.upper() == brand_kit.colors()["semantic"]["alert"].upper()
