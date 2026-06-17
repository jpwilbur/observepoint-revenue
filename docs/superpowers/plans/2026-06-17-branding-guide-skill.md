# branding-guide Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `observepoint-revenue:branding-guide` — a standalone skill that is the single source of truth for ObservePoint's brand (colors, fonts, logos, themes, voice, boilerplate), consumed by every renderer in the plugin and reusable from the `observepoint-consultant` plugin, plus a drift-checker, a document brand-checker, and a net-new branded document maker.

**Architecture:** A canonical `brand-spec.json` holds every brand value once. A self-contained, dependency-light `brand_kit.py` loads it and exposes tokens, themes, logo paths, fonts, and docx/xlsx/html + HTML→PDF rendering helpers (Claude judges voice/usage; Python provides tokens and renders — the plugin's existing boundary). The four existing renderers are retrofit to import `brand_kit` and drop their hardcoded constants, structurally ending the value-drift currently spread across the plugin scripts, the WGMA app, and the dossier theme.

**Tech Stack:** Python 3 (`/opt/homebrew/bin/python3`), `openpyxl`, `python-docx`, `python-pptx`, `Pillow` (PIL), `weasyprint` (all confirmed installed), stdlib `urllib`/`json`/`subprocess` (no `requests`/`bs4`/`jinja2` — not installed), pytest. Interpreter trap: always `/opt/homebrew/bin/python3`, never bare `python3`.

---

## File Structure

**New — the skill:**
- `observepoint-revenue/skills/branding-guide/SKILL.md` — when-to-use, non-negotiables, how sibling skills call it, voice summary
- `observepoint-revenue/skills/branding-guide/references/brand-spec.json` — **the source of truth**
- `observepoint-revenue/skills/branding-guide/references/brand-guidelines.md` — logo/color usage, clear-space, do/don't
- `observepoint-revenue/skills/branding-guide/references/voice-and-messaging.md` — tone, naming, boilerplate, products
- `observepoint-revenue/skills/branding-guide/assets/logo-primary.png` — all-yellow logotype (dark bg)
- `observepoint-revenue/skills/branding-guide/assets/logo-ink.png` — dark logotype for light bg (generated from primary)
- `observepoint-revenue/skills/branding-guide/assets/favicon.png` — OP monogram
- `observepoint-revenue/skills/branding-guide/scripts/brand_kit.py` — tokens/themes/logos/helpers + `--emit-json` CLI
- `observepoint-revenue/skills/branding-guide/scripts/verify_brand.py` — drift check vs live site
- `observepoint-revenue/skills/branding-guide/scripts/brand_check.py` — lint/fix a doc or text
- `observepoint-revenue/skills/branding-guide/scripts/make_document.py` — branded one-pager / report / letter / memo / deck

**New — tests:**
- `observepoint-revenue/tests/test_brand_kit.py`
- `observepoint-revenue/tests/test_verify_brand.py`
- `observepoint-revenue/tests/test_brand_check.py`
- `observepoint-revenue/tests/test_make_document.py`
- `observepoint-revenue/tests/fixtures/site_homepage.html` — captured site markup for verify tests (no network)

**Modified:**
- `observepoint-revenue/tests/conftest.py` — add `branding-guide/scripts` to sys.path
- `observepoint-revenue/skills/scope-calculator/scripts/build_proposal.py:43-48` — import brand_kit
- `observepoint-revenue/skills/scope-calculator/scripts/build_model.py:24-31` — import brand_kit
- `observepoint-revenue/skills/scope-calculator/scripts/build_internal_evidence.py:25-27` — import brand_kit
- `observepoint-revenue/skills/research-account/scripts/build_dossier.py:28-31,274-302` — import brand_kit, use `html_to_pdf`
- `observepoint-revenue/skills/scope-calculator/assets/op-logo.png` — **deleted** (de-dupe)
- `observepoint-revenue/skills/research-account/assets/op-logo.png` — **deleted** (de-dupe)
- `CLAUDE.md`, `README.md`, `docs/ROADMAP.md` — register the 5th skill
- `observepoint-revenue/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` — description + version bump

**Convention:** run tests with `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q`. Commit email stays `16406437+jpwilbur@users.noreply.github.com`. Work on a feature branch (already on `feat/branding-guide-skill`).

---

## Task 1: Scaffold skill + bundle assets + brand-spec.json

**Files:**
- Create: `observepoint-revenue/skills/branding-guide/references/brand-spec.json`
- Create: `observepoint-revenue/skills/branding-guide/assets/logo-primary.png` (copied)
- Create: `observepoint-revenue/skills/branding-guide/assets/favicon.png` (copied)
- Create: `observepoint-revenue/skills/branding-guide/assets/logo-ink.png` (generated)
- Test: `observepoint-revenue/tests/test_brand_kit.py` (spec-shape tests only in this task)

- [ ] **Step 1: Create directories and copy the canonical assets**

The repo already ships the byte-identical primary logo. The favicon was downloaded earlier to `/tmp/opbrand/site-favicon.png`; if absent, re-fetch it.

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin/observepoint-revenue"
mkdir -p skills/branding-guide/references skills/branding-guide/assets skills/branding-guide/scripts
cp skills/scope-calculator/assets/op-logo.png skills/branding-guide/assets/logo-primary.png
[ -f /tmp/opbrand/site-favicon.png ] || curl -s -L "https://www.observepoint.com/wp-content/themes/observepoint/assets/images/favicon.png" -o /tmp/opbrand/site-favicon.png
cp /tmp/opbrand/site-favicon.png skills/branding-guide/assets/favicon.png
ls -la skills/branding-guide/assets
```
Expected: `logo-primary.png` (~2KB) and `favicon.png` (~4KB) present.

- [ ] **Step 2: Generate the ink (dark) logo for light backgrounds**

The primary is flat yellow on transparent; recolor the opaque pixels to ink. This is the same logotype, recolored — not a new design.

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin/observepoint-revenue"
/opt/homebrew/bin/python3 - <<'PY'
from PIL import Image
src = Image.open("skills/branding-guide/assets/logo-primary.png").convert("RGBA")
px = src.load()
INK = (30, 30, 30)  # #1E1E1E
for y in range(src.height):
    for x in range(src.width):
        r, g, b, a = px[x, y]
        if a > 10:                      # keep alpha, repaint color
            px[x, y] = (INK[0], INK[1], INK[2], a)
src.save("skills/branding-guide/assets/logo-ink.png")
print("wrote logo-ink.png", src.size)
PY
```
Expected: `wrote logo-ink.png (366, 57)`.

- [ ] **Step 3: Write `brand-spec.json`**

```json
{
  "meta": {
    "version": "1.0.0",
    "last_verified": "2026-06-17",
    "sources": [
      "https://www.observepoint.com/ — site CSS `.logo{color:#f2cd14}`, theme op-logo.png, favicon.png",
      "observepoint-revenue scope-calculator + research-account renderers (existing constants)"
    ],
    "notes": "Dark-theme surface hexes reverse-engineered from the dossier renderer; confirm against the official ObservePoint brand guide when available."
  },
  "naming": {
    "company": "ObservePoint",
    "disallowed": ["Observepoint", "Observe Point", "observePoint", "OBSERVEPOINT", "Observe point"],
    "monogram": "OP",
    "products": [
      "Website Privacy Scan", "Analytics Validation Scan", "Website Accessibility Scan",
      "Full Website Audit", "Consent Banner Audit", "Marketing Landing Page & Email Scan",
      "Tag and Cookie Debugger"
    ]
  },
  "colors": {
    "brand_yellow": "#F2CD14",
    "ink": "#1E1E1E",
    "white": "#FFFFFF",
    "dark": {
      "bg": "#14151A", "panel": "#1E2027", "panel2": "#262932",
      "border": "#313440", "text": "#E8E9EC", "muted": "#9AA1AD"
    },
    "light": {
      "page": "#FFFFFF", "fill": "#F2F2F2", "gray": "#5C5C5C",
      "input": "#FFF7CC", "hairline": "#D9D9D9", "text": "#1E1E1E"
    },
    "semantic": { "success": "#27A567", "alert": "#F34146", "link": "#7CB8FF" },
    "dataviz": ["#2874FC", "#27A567", "#F34146", "#E0249A", "#1FB6B6", "#9B51E0", "#FF8C1A", "#F2CD14"]
  },
  "typography": {
    "family": "Montserrat",
    "fallback": "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    "google_fonts": "https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap",
    "weights": { "body": 400, "semibold": 600, "bold": 700, "heavy": 800 }
  },
  "logos": {
    "primary":   { "file": "logo-primary.png", "background": "dark",  "description": "All-yellow angular logotype" },
    "secondary": { "file": "logo-secondary.png", "background": "dark", "description": "White Observe + yellow Point wordmark (decks). FILE NOT YET PROVIDED — falls back to primary." },
    "ink":       { "file": "logo-ink.png", "background": "light", "description": "Dark logotype for light backgrounds (generated from primary)" },
    "favicon":   { "file": "favicon.png", "background": "any", "description": "OP monogram, gray on yellow" },
    "min_width_px": 120,
    "clear_space": "0.5× logo height on all sides"
  },
  "themes": {
    "dark":  { "surface": "dark",  "logo": "primary", "default": true },
    "light": { "surface": "light", "logo": "ink" }
  },
  "format_defaults": {
    "html": "dark", "pdf": "dark", "dossier": "dark", "onepager": "dark",
    "report": "dark", "deck": "dark", "pptx": "dark",
    "letter": "light", "memo": "light", "docx": "light", "proposal": "light",
    "xlsx": "light", "workbook": "light"
  },
  "boilerplate": {
    "tagline": "The Automated Website Scanner for Privacy, Accessibility, Tag Accuracy, and More",
    "about_confirmed": false,
    "about": "ObservePoint is the automated website scanner for privacy, accessibility, and tag accuracy, helping the world's most trusted brands govern their digital properties. (PROVISIONAL — confirm official boilerplate; about_confirmed=false.)",
    "copyright": "© {year} ObservePoint. All rights reserved."
  }
}
```

- [ ] **Step 4: Write the spec-shape test**

```python
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
```

- [ ] **Step 5: Run the spec-shape test**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_brand_kit.py -q`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
git add observepoint-revenue/skills/branding-guide/references/brand-spec.json \
        observepoint-revenue/skills/branding-guide/assets \
        observepoint-revenue/tests/test_brand_kit.py
git commit -m "feat(branding-guide): canonical brand-spec.json + bundled logo/favicon assets"
```

---

## Task 2: `brand_kit.py` core API (tokens, themes, logos, fonts, boilerplate)

**Files:**
- Create: `observepoint-revenue/skills/branding-guide/scripts/brand_kit.py`
- Modify: `observepoint-revenue/tests/conftest.py:8-13`
- Test: `observepoint-revenue/tests/test_brand_kit.py`

- [ ] **Step 1: Add branding-guide/scripts to the test path**

Modify `observepoint-revenue/tests/conftest.py` — add the line to the tuple:

```python
for rel in (
    "skills/scope-calculator/scripts",
    "skills/research-account/scripts",
    "skills/owned-properties/scripts",
    "skills/find-accounts/scripts",
    "skills/branding-guide/scripts",
):
    sys.path.insert(0, str(ROOT / rel))
```

- [ ] **Step 2: Write the failing tests for the core API**

Append to `observepoint-revenue/tests/test_brand_kit.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_brand_kit.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'brand_kit'`.

- [ ] **Step 4: Write `brand_kit.py` core**

```python
# observepoint-revenue/skills/branding-guide/scripts/brand_kit.py
"""ObservePoint brand authority — the single source of truth.

Loads references/brand-spec.json and exposes the canonical tokens, themes, logo
paths, fonts, and rendering helpers so every renderer pulls identical brand values
instead of hardcoding them. Dependency-light (stdlib + optional openpyxl/docx/
weasyprint imported lazily) so it is safe to import from any skill or plugin.

CLI:
  python brand_kit.py --emit-json    # print the canonical spec as JSON (any consumer)
"""
from __future__ import annotations
import json
import os
import pathlib
import subprocess
import sys

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parent                                  # skills/branding-guide/
SPEC_PATH = _ROOT / "references" / "brand-spec.json"
ASSETS = _ROOT / "assets"

_SPEC = None


def load_spec() -> dict:
    """Parse and cache brand-spec.json."""
    global _SPEC
    if _SPEC is None:
        _SPEC = json.loads(SPEC_PATH.read_text())
    return _SPEC


def colors() -> dict:
    return load_spec()["colors"]


def brand_yellow() -> str:
    return colors()["brand_yellow"]


def font() -> dict:
    return load_spec()["typography"]


def naming() -> dict:
    return load_spec()["naming"]


def theme(name: str = "dark") -> dict:
    """Resolved palette for a theme: surface colors + accent + chosen logo variant."""
    spec = load_spec()
    t = spec["themes"][name]
    surface = spec["colors"][t["surface"]]
    return {**surface, "accent": spec["colors"]["brand_yellow"], "logo": t["logo"], "name": name}


def default_theme_for(fmt: str) -> str:
    """Brand-default theme for a document format (dark = presentation, light = working docs)."""
    return load_spec()["format_defaults"].get(fmt.lower().lstrip("."), "dark")


def logo_path(theme_name: str = "dark", variant: str | None = None) -> str:
    """Absolute path to the right logo file; falls back to primary if the file is absent."""
    spec = load_spec()
    variant = variant or spec["themes"][theme_name]["logo"]
    f = ASSETS / spec["logos"][variant]["file"]
    if not f.exists():
        f = ASSETS / spec["logos"]["primary"]["file"]
    return str(f)


def copyright(year: int) -> str:
    return load_spec()["boilerplate"]["copyright"].format(year=year)


def boilerplate(key: str) -> str:
    return load_spec()["boilerplate"][key]


def _main(argv) -> int:
    if "--emit-json" in argv:
        print(json.dumps(load_spec(), indent=2))
        return 0
    sys.stderr.write("usage: brand_kit.py --emit-json\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_brand_kit.py -q`
Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
git add observepoint-revenue/skills/branding-guide/scripts/brand_kit.py \
        observepoint-revenue/tests/conftest.py observepoint-revenue/tests/test_brand_kit.py
git commit -m "feat(branding-guide): brand_kit core (tokens, themes, logos, boilerplate) + test path"
```

---

## Task 3: `brand_kit.py` rendering helpers (docx / xlsx / html / data-URI / HTML→PDF) + emit-json CLI

**Files:**
- Modify: `observepoint-revenue/skills/branding-guide/scripts/brand_kit.py`
- Test: `observepoint-revenue/tests/test_brand_kit.py`

- [ ] **Step 1: Write the failing tests for the helpers**

Append to `observepoint-revenue/tests/test_brand_kit.py`:

```python
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


def test_emit_json_cli_prints_spec():
    out = _sp.run([_sys.executable, str(brand_kit.__file__), "--emit-json"],
                  capture_output=True, text=True)
    assert out.returncode == 0
    import json as _json
    assert _json.loads(out.stdout)["colors"]["brand_yellow"].upper() == "#F2CD14"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_brand_kit.py -q`
Expected: FAIL — `AttributeError: module 'brand_kit' has no attribute 'rgbcolor'`.

- [ ] **Step 3: Add the helper functions to `brand_kit.py`**

Insert these functions just above `def _main` in `brand_kit.py`:

```python
import base64


# ---- docx helpers ----
def rgbcolor(hex_str: str):
    from docx.shared import RGBColor
    h = hex_str.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# ---- xlsx helpers ----
def xlsx_font(bold: bool = False, color: str | None = None, size: int = 10):
    from openpyxl.styles import Font
    return Font(name=font()["family"], bold=bold,
                color=(color or colors()["ink"]).lstrip("#"), size=size)


def xlsx_fill(hex_str: str):
    from openpyxl.styles import PatternFill
    return PatternFill("solid", fgColor=hex_str.lstrip("#"))


# ---- html helpers ----
def css_vars(theme_name: str = "dark") -> str:
    """A :root{} block of CSS variables for a theme (--op-bg, --op-text, --op-accent, --op-font)."""
    t = theme(theme_name)
    rows = [f"--op-{k}:{v.upper()};" for k, v in t.items()
            if isinstance(v, str) and v.startswith("#")]
    rows.append(f"--op-font:'{font()['family']}',{font()['fallback']};")
    return ":root{" + "".join(rows) + "}"


def logo_data_uri(theme_name: str = "dark", variant: str | None = None) -> str:
    """Base64 data: URI for embedding the logo inline in HTML (so output is self-contained)."""
    p = logo_path(theme_name, variant)
    b = base64.b64encode(pathlib.Path(p).read_bytes()).decode()
    return "data:image/png;base64," + b


# ---- HTML -> PDF (headless Chrome -> weasyprint -> None) ----
def _find_chrome():
    import shutil
    for p in (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ):
        if os.path.exists(p):
            return p
    for name in ("google-chrome", "google-chrome-stable", "chromium",
                 "chromium-browser", "microsoft-edge", "brave-browser"):
        found = shutil.which(name)
        if found:
            return found
    return None


def html_to_pdf(html_path: str, pdf_path: str):
    """Render html_path -> pdf_path. Returns the engine name used, or None if none worked."""
    chrome = _find_chrome()
    if chrome:
        try:
            subprocess.run(
                [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                 f"--print-to-pdf={pdf_path}", pathlib.Path(html_path).resolve().as_uri()],
                check=True, capture_output=True, timeout=60)
            if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                return "chrome"
        except Exception:
            pass
    try:
        from weasyprint import HTML
        HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            return "weasyprint"
    except Exception:
        pass
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_brand_kit.py -q`
Expected: 14 passed.

- [ ] **Step 5: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
git add observepoint-revenue/skills/branding-guide/scripts/brand_kit.py observepoint-revenue/tests/test_brand_kit.py
git commit -m "feat(branding-guide): brand_kit render helpers (docx/xlsx/html, data-uri, html_to_pdf, emit-json)"
```

---

## Task 4: `verify_brand.py` — drift check vs the live site

**Files:**
- Create: `observepoint-revenue/skills/branding-guide/scripts/verify_brand.py`
- Create: `observepoint-revenue/tests/fixtures/site_homepage.html`
- Test: `observepoint-revenue/tests/test_verify_brand.py`

- [ ] **Step 1: Capture a site fixture (so tests never hit the network)**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin/observepoint-revenue"
mkdir -p tests/fixtures
printf '%s\n' '<html><head><link rel="icon" href="/favicon.png"></head>' \
  '<body><style>.logo{color:#f2cd14;font-size:26px}</style></body></html>' \
  > tests/fixtures/site_homepage.html
cat tests/fixtures/site_homepage.html
```
Expected: the two-line HTML containing `.logo{color:#f2cd14}`.

- [ ] **Step 2: Write the failing test**

```python
# observepoint-revenue/tests/test_verify_brand.py
import pathlib
import verify_brand

FIX = pathlib.Path(__file__).resolve().parent / "fixtures" / "site_homepage.html"


def test_extract_yellow_from_css():
    html = FIX.read_text()
    assert verify_brand.extract_site_yellow(html).upper() == "#F2CD14"


def test_check_drift_reports_match(monkeypatch):
    monkeypatch.setattr(verify_brand, "fetch", lambda url: FIX.read_text())
    report = verify_brand.check_drift()
    assert report["yellow"]["site"].upper() == "#F2CD14"
    assert report["yellow"]["spec"].upper() == "#F2CD14"
    assert report["yellow"]["match"] is True
    assert report["ok"] is True


def test_check_drift_flags_mismatch(monkeypatch):
    monkeypatch.setattr(verify_brand, "fetch",
                        lambda url: '<style>.logo{color:#ABCDEF}</style>')
    report = verify_brand.check_drift()
    assert report["yellow"]["match"] is False
    assert report["ok"] is False
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_verify_brand.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'verify_brand'`.

- [ ] **Step 4: Write `verify_brand.py`**

```python
# observepoint-revenue/skills/branding-guide/scripts/verify_brand.py
"""Re-pull the live ObservePoint site and report drift against brand-spec.json.

Deterministic, stdlib-only (urllib). NEVER edits the spec — it prints a drift
report; a human/Claude updates brand-spec.json deliberately (reproducible, no
LLM-maintained state).

CLI:  python verify_brand.py            # human-readable report, exit 0 if no drift
      python verify_brand.py --json     # machine-readable report
"""
from __future__ import annotations
import json
import re
import sys
import urllib.request

import brand_kit

SITE = "https://www.observepoint.com/"
_YELLOW_RE = re.compile(r"\.logo\s*\{[^}]*color\s*:\s*(#[0-9a-fA-F]{6})", re.I)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "op-branding-guide/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def extract_site_yellow(html: str) -> str | None:
    m = _YELLOW_RE.search(html)
    return m.group(1) if m else None


def check_drift(html: str | None = None) -> dict:
    if html is None:
        html = fetch(SITE)
    site_yellow = extract_site_yellow(html)
    spec_yellow = brand_kit.brand_yellow()
    match = bool(site_yellow) and site_yellow.upper() == spec_yellow.upper()
    return {
        "yellow": {"site": site_yellow, "spec": spec_yellow, "match": match},
        "ok": match,
    }


def _main(argv) -> int:
    report = check_drift()
    if "--json" in argv:
        print(json.dumps(report, indent=2))
    else:
        y = report["yellow"]
        flag = "OK" if y["match"] else "DRIFT"
        print(f"[{flag}] brand yellow — site={y['site']} spec={y['spec']}")
        if not report["ok"]:
            print("Review and update brand-spec.json deliberately, then bump meta.last_verified.")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_verify_brand.py -q`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
git add observepoint-revenue/skills/branding-guide/scripts/verify_brand.py \
        observepoint-revenue/tests/test_verify_brand.py observepoint-revenue/tests/fixtures/site_homepage.html
git commit -m "feat(branding-guide): verify_brand.py drift check vs live site (stdlib, fixture-tested)"
```

---

## Task 5: `brand_check.py` — lint/fix a document or text against the spec

**Files:**
- Create: `observepoint-revenue/skills/branding-guide/scripts/brand_check.py`
- Test: `observepoint-revenue/tests/test_brand_check.py`

- [ ] **Step 1: Write the failing tests**

```python
# observepoint-revenue/tests/test_brand_check.py
import brand_check


def test_flags_misspelled_company_name():
    issues = brand_check.check_text("We love Observepoint and Observe Point.")
    kinds = {i["kind"] for i in issues}
    assert "naming" in kinds
    # both bad spellings flagged
    bad = {i["found"] for i in issues if i["kind"] == "naming"}
    assert "Observepoint" in bad and "Observe Point" in bad


def test_clean_text_has_no_naming_issues():
    issues = brand_check.check_text("ObservePoint scans your site.")
    assert [i for i in issues if i["kind"] == "naming"] == []


def test_flags_off_palette_hex():
    issues = brand_check.check_text("color: #ABCDEF; accent: #F2CD14;")
    offp = [i for i in issues if i["kind"] == "color"]
    assert any(i["found"].upper() == "#ABCDEF" for i in offp)
    assert all(i["found"].upper() != "#F2CD14" for i in offp)  # brand color is allowed


def test_fix_text_corrects_naming():
    fixed = brand_check.fix_text("Observepoint and Observe Point rock.")
    assert "ObservePoint and ObservePoint rock." == fixed
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_brand_check.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'brand_check'`.

- [ ] **Step 3: Write `brand_check.py`**

```python
# observepoint-revenue/skills/branding-guide/scripts/brand_check.py
"""Lint (and optionally auto-fix) a document or block of text against brand-spec.json.

Checks the deterministic, mechanical rules:
  - naming: disallowed spellings of the company name -> "ObservePoint"
  - color:  hex literals that are not in the approved palette
(Voice/tone is a judgment call Claude makes from references/voice-and-messaging.md;
this script only catches the mechanical violations.)

CLI:  python brand_check.py <file>            # list issues, exit 1 if any
      python brand_check.py <file> --fix      # rewrite the file with safe naming fixes
"""
from __future__ import annotations
import re
import sys

import brand_kit

_HEX_RE = re.compile(r"#[0-9a-fA-F]{6}")


def _approved_hexes() -> set[str]:
    c = brand_kit.colors()
    out: set[str] = set()
    for v in c.values():
        if isinstance(v, str) and v.startswith("#"):
            out.add(v.upper())
        elif isinstance(v, dict):
            out.update(x.upper() for x in v.values() if isinstance(x, str) and x.startswith("#"))
        elif isinstance(v, list):
            out.update(x.upper() for x in v if isinstance(x, str) and x.startswith("#"))
    return out


def check_text(text: str) -> list[dict]:
    issues: list[dict] = []
    n = brand_kit.naming()
    for bad in n["disallowed"]:
        for m in re.finditer(re.escape(bad), text):
            issues.append({"kind": "naming", "found": bad, "pos": m.start(),
                           "fix": n["company"]})
    approved = _approved_hexes()
    for m in _HEX_RE.finditer(text):
        if m.group(0).upper() not in approved:
            issues.append({"kind": "color", "found": m.group(0), "pos": m.start(),
                           "fix": None})
    return issues


def fix_text(text: str) -> str:
    """Apply only the safe, unambiguous fixes (naming). Colors are reported, not auto-changed."""
    n = brand_kit.naming()
    for bad in n["disallowed"]:
        text = re.sub(re.escape(bad), n["company"], text)
    return text


def _main(argv) -> int:
    args = [a for a in argv if not a.startswith("--")]
    do_fix = "--fix" in argv
    if not args:
        sys.stderr.write("usage: brand_check.py <file> [--fix]\n")
        return 2
    path = args[0]
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if do_fix:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(fix_text(text))
        print(f"fixed naming in {path}")
        return 0
    issues = check_text(text)
    for i in issues:
        print(f"[{i['kind']}] {i['found']!r} at {i['pos']}"
              + (f" -> {i['fix']}" if i["fix"] else " (off-palette)"))
    print(f"{len(issues)} issue(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_brand_check.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
git add observepoint-revenue/skills/branding-guide/scripts/brand_check.py observepoint-revenue/tests/test_brand_check.py
git commit -m "feat(branding-guide): brand_check.py naming + off-palette linter with --fix"
```

---

## Task 6: `make_document.py` — branded one-pager + report (HTML→PDF)

**Files:**
- Create: `observepoint-revenue/skills/branding-guide/scripts/make_document.py`
- Test: `observepoint-revenue/tests/test_make_document.py`

The content schema (shared by all kinds): a JSON object
`{"title": str, "subtitle": str?, "prepared_for": str?, "sections": [{"heading": str, "body": str?, "bullets": [str]?}], "footer": str?}`.

- [ ] **Step 1: Write the failing tests**

```python
# observepoint-revenue/tests/test_make_document.py
import json
import pathlib
import make_document

CONTENT = {
    "title": "Privacy Scan Overview",
    "subtitle": "Acme Pharma",
    "prepared_for": "Acme Pharma",
    "sections": [
        {"heading": "What we found", "body": "37 unique tags across 40 pages."},
        {"heading": "Next steps", "bullets": ["Block unapproved cookies", "Validate analytics"]},
    ],
}


def test_onepager_builds_html_with_brand(tmp_path):
    cj = tmp_path / "c.json"
    cj.write_text(json.dumps(CONTENT))
    out = tmp_path / "onepager.pdf"
    result = make_document.build("onepager", json.loads(cj.read_text()), str(out))
    # PDF if an engine exists, else a .html fallback — at least one deliverable exists
    produced = pathlib.Path(result["path"])
    assert produced.exists() and produced.stat().st_size > 0
    html = result["html"]
    assert "#14151A" in html.upper()            # dark theme by default
    assert "data:image/png;base64," in html      # logo embedded
    assert "Privacy Scan Overview" in html
    assert "© " in html and "ObservePoint" in html


def test_report_respects_light_override(tmp_path):
    out = tmp_path / "r.pdf"
    result = make_document.build("report", CONTENT, str(out), theme="light")
    assert "#FFFFFF" in result["html"].upper()
    assert result["theme"] == "light"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_make_document.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'make_document'`.

- [ ] **Step 3: Write `make_document.py` (one-pager + report; HTML→PDF kinds)**

```python
# observepoint-revenue/skills/branding-guide/scripts/make_document.py
"""Render a net-new ObservePoint-branded document from a content JSON.

Kinds: onepager, report  (HTML->PDF, this file)
       letter, memo       (DOCX, added in a later task)
       deck               (PPTX, added in a later task)

Claude assembles the content (judgment); this renders it (deterministic) with the
canonical brand via brand_kit. Theme defaults come from brand_kit.default_theme_for;
pass theme="dark"/"light" to override.

CLI:  python make_document.py <kind> <content.json> <out_path> [--theme dark|light]
"""
from __future__ import annotations
import datetime
import html as _html
import json
import pathlib
import sys
import tempfile

import brand_kit

HTML_KINDS = {"onepager", "report"}


def _esc(s) -> str:
    return _html.escape(str(s))


def _sections_html(sections) -> str:
    out = []
    for s in sections:
        out.append(f'<h2>{_esc(s.get("heading", ""))}</h2>')
        if s.get("body"):
            out.append(f'<p>{_esc(s["body"])}</p>')
        if s.get("bullets"):
            out.append("<ul>" + "".join(f"<li>{_esc(b)}</li>" for b in s["bullets"]) + "</ul>")
    return "\n".join(out)


def render_html(content: dict, theme: str) -> str:
    year = datetime.date.today().year
    footer = content.get("footer") or brand_kit.copyright(year)
    sub = content.get("subtitle") or content.get("prepared_for") or ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
@import url('{brand_kit.font()["google_fonts"]}');
{brand_kit.css_vars(theme)}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--op-bg,var(--op-page));color:var(--op-text);
  font-family:var(--op-font);font-size:13px;line-height:1.55;padding:48px}}
.brandbar{{display:flex;align-items:center;gap:14px;border-bottom:3px solid var(--op-accent);padding-bottom:16px}}
.brandbar img{{height:30px}}
h1{{font-weight:800;font-size:28px;margin:22px 0 2px}}
.sub{{color:var(--op-muted,var(--op-gray));font-size:13px;margin-bottom:18px}}
h2{{font-weight:800;font-size:15px;margin:20px 0 4px}}
ul{{margin:6px 0 6px 18px}}
.footer{{margin-top:40px;border-top:1px solid var(--op-border,var(--op-hairline));
  padding-top:10px;color:var(--op-muted,var(--op-gray));font-size:11px}}
</style></head><body>
<div class="brandbar"><img src="{brand_kit.logo_data_uri(theme)}" alt="ObservePoint"></div>
<h1>{_esc(content.get("title", ""))}</h1>
<div class="sub">{_esc(sub)}</div>
{_sections_html(content.get("sections", []))}
<div class="footer">{_esc(footer)}</div>
</body></html>"""


def build(kind: str, content: dict, out_path: str, theme: str | None = None) -> dict:
    if kind not in HTML_KINDS:
        raise ValueError(f"{kind!r} is not an HTML kind; handled elsewhere")
    theme = theme or brand_kit.default_theme_for(kind)
    doc_html = render_html(content, theme)
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tf:
        tf.write(doc_html)
        tmp_html = tf.name
    engine = brand_kit.html_to_pdf(tmp_html, str(out))
    if engine:
        produced = str(out)
    else:                                   # no PDF engine — write the HTML beside it
        produced = str(out.with_suffix(".html"))
        pathlib.Path(produced).write_text(doc_html, encoding="utf-8")
    return {"path": produced, "engine": engine, "theme": theme, "html": doc_html}


def _main(argv) -> int:
    theme = None
    if "--theme" in argv:
        i = argv.index("--theme")
        theme = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if len(argv) < 3:
        sys.stderr.write("usage: make_document.py <kind> <content.json> <out_path> [--theme dark|light]\n")
        return 2
    kind, content_path, out_path = argv[0], argv[1], argv[2]
    content = json.loads(pathlib.Path(content_path).read_text())
    result = build(kind, content, out_path, theme=theme)
    print(f"wrote {result['path']} (engine={result['engine']}, theme={result['theme']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_make_document.py -q`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
git add observepoint-revenue/skills/branding-guide/scripts/make_document.py observepoint-revenue/tests/test_make_document.py
git commit -m "feat(branding-guide): make_document one-pager + report (HTML->PDF, dark default)"
```

---

## Task 7: `make_document.py` — branded letter / memo (DOCX)

**Files:**
- Modify: `observepoint-revenue/skills/branding-guide/scripts/make_document.py`
- Test: `observepoint-revenue/tests/test_make_document.py`

- [ ] **Step 1: Write the failing test**

Append to `observepoint-revenue/tests/test_make_document.py`:

```python
def test_letter_builds_docx_with_logo_and_copyright(tmp_path):
    from docx import Document
    out = tmp_path / "letter.docx"
    result = make_document.build("letter", CONTENT, str(out))
    assert pathlib.Path(result["path"]).suffix == ".docx"
    doc = Document(result["path"])
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Privacy Scan Overview" in text
    assert "ObservePoint" in text
    # light theme is the default for working docs
    assert result["theme"] == "light"
    # at least one inline image (the logo) is embedded
    assert len(doc.inline_shapes) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_make_document.py::test_letter_builds_docx_with_logo_and_copyright -q`
Expected: FAIL — `ValueError: 'letter' is not an HTML kind`.

- [ ] **Step 3: Add the DOCX renderer**

In `make_document.py`, add `DOCX_KINDS` and a `build_docx`, and route them in `build`:

```python
DOCX_KINDS = {"letter", "memo"}
```

Add this function above `def build`:

```python
def build_docx(kind: str, content: dict, out_path: str, theme: str) -> dict:
    from docx import Document
    from docx.shared import Inches, Pt
    year = datetime.date.today().year
    family = brand_kit.font()["family"]
    ink = brand_kit.colors()["ink"]
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name, style.font.size, style.font.color.rgb = family, Pt(10.5), brand_kit.rgbcolor(ink)
    # Letterhead: ink logo (light bg) + yellow rule
    doc.add_picture(brand_kit.logo_path(theme), width=Inches(2.0))
    rule = doc.add_paragraph()
    rule.paragraph_format.space_before = Pt(2)
    r = rule.add_run("_" * 60)
    r.font.color.rgb = brand_kit.rgbcolor(brand_kit.brand_yellow())
    # Title + subtitle
    h = doc.add_paragraph()
    hr = h.add_run(content.get("title", ""))
    hr.bold, hr.font.size, hr.font.name = True, Pt(16), family
    if content.get("subtitle") or content.get("prepared_for"):
        s = doc.add_paragraph().add_run(content.get("subtitle") or content["prepared_for"])
        s.font.size, s.font.color.rgb, s.font.name = Pt(10), brand_kit.rgbcolor(brand_kit.colors()["light"]["gray"]), family
    # Body sections
    for sec in content.get("sections", []):
        hp = doc.add_paragraph().add_run(sec.get("heading", ""))
        hp.bold, hp.font.size, hp.font.name = True, Pt(12), family
        if sec.get("body"):
            doc.add_paragraph(sec["body"])
        for b in sec.get("bullets", []):
            doc.add_paragraph(b, style="List Bullet")
    # Footer copyright
    foot = doc.add_paragraph()
    fr = foot.add_run(content.get("footer") or brand_kit.copyright(year))
    fr.font.size, fr.font.color.rgb, fr.font.name = Pt(8), brand_kit.rgbcolor(brand_kit.colors()["light"]["gray"]), family
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    return {"path": str(out), "engine": "python-docx", "theme": theme, "html": None}
```

Update `build` to route DOCX kinds — change the top of `build`:

```python
def build(kind: str, content: dict, out_path: str, theme: str | None = None) -> dict:
    theme = theme or brand_kit.default_theme_for(kind)
    if kind in DOCX_KINDS:
        return build_docx(kind, content, out_path, theme)
    if kind not in HTML_KINDS:
        raise ValueError(f"unknown kind {kind!r}")
    doc_html = render_html(content, theme)
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tf:
        tf.write(doc_html)
        tmp_html = tf.name
    engine = brand_kit.html_to_pdf(tmp_html, str(out))
    if engine:
        produced = str(out)
    else:
        produced = str(out.with_suffix(".html"))
        pathlib.Path(produced).write_text(doc_html, encoding="utf-8")
    return {"path": produced, "engine": engine, "theme": theme, "html": doc_html}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_make_document.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
git add observepoint-revenue/skills/branding-guide/scripts/make_document.py observepoint-revenue/tests/test_make_document.py
git commit -m "feat(branding-guide): make_document letter/memo (DOCX letterhead, light default)"
```

---

## Task 8: `make_document.py` — branded slide deck (PPTX)

**Files:**
- Modify: `observepoint-revenue/skills/branding-guide/scripts/make_document.py`
- Test: `observepoint-revenue/tests/test_make_document.py`

- [ ] **Step 1: Write the failing test**

Append to `observepoint-revenue/tests/test_make_document.py`:

```python
def test_deck_builds_pptx_with_title_and_section_slides(tmp_path):
    from pptx import Presentation
    out = tmp_path / "deck.pptx"
    result = make_document.build("deck", CONTENT, str(out))
    assert pathlib.Path(result["path"]).suffix == ".pptx"
    assert result["theme"] == "dark"
    prs = Presentation(result["path"])
    # title slide + one slide per section
    assert len(prs.slides) == 1 + len(CONTENT["sections"])
    all_text = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                all_text.append(shape.text_frame.text)
    joined = "\n".join(all_text)
    assert "Privacy Scan Overview" in joined
    assert "What we found" in joined
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_make_document.py::test_deck_builds_pptx_with_title_and_section_slides -q`
Expected: FAIL — `ValueError: unknown kind 'deck'`.

- [ ] **Step 3: Add the PPTX renderer**

In `make_document.py`, add `PPTX_KINDS` and `build_pptx`, and route it in `build`:

```python
PPTX_KINDS = {"deck"}
```

Add above `def build`:

```python
def _hex_to_rgb(hex_str: str):
    from pptx.dml.color import RGBColor
    h = hex_str.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def build_pptx(kind: str, content: dict, out_path: str, theme: str) -> dict:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    t = brand_kit.theme(theme)
    bg = _hex_to_rgb(t.get("bg", t.get("page")))
    text_col = _hex_to_rgb(t["text"])
    accent = _hex_to_rgb(t["accent"])
    family = brand_kit.font()["family"]
    prs = Presentation()                       # 10 x 7.5 in default
    blank = prs.slide_layouts[6]

    def paint_bg(slide):
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = bg

    def add_text(slide, text, left, top, width, height, size, bold, color):
        box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = text
        run.font.size, run.font.bold, run.font.name = Pt(size), bold, family
        run.font.color.rgb = color
        return box

    def accent_bar(slide):
        bar = slide.shapes.add_shape(1, Inches(0.6), Inches(1.7), Inches(2.0), Inches(0.06))
        bar.fill.solid(); bar.fill.fore_color.rgb = accent; bar.line.fill.background()

    # Title slide
    s = prs.slides.add_slide(blank); paint_bg(s)
    s.shapes.add_picture(brand_kit.logo_path(theme), Inches(0.6), Inches(0.6), height=Inches(0.5))
    add_text(s, content.get("title", ""), 0.6, 1.9, 9.0, 1.5, 40, True, text_col)
    if content.get("subtitle") or content.get("prepared_for"):
        add_text(s, content.get("subtitle") or content["prepared_for"], 0.6, 3.2, 9.0, 0.8, 18, False, accent)

    # One content slide per section
    for sec in content.get("sections", []):
        cs = prs.slides.add_slide(blank); paint_bg(cs)
        add_text(cs, sec.get("heading", ""), 0.6, 0.7, 9.0, 1.0, 28, True, text_col)
        accent_bar(cs)
        body = sec.get("body", "")
        if sec.get("bullets"):
            body = (body + "\n" if body else "") + "\n".join("• " + b for b in sec["bullets"])
        if body:
            add_text(cs, body, 0.6, 2.0, 9.0, 4.5, 16, False, text_col)

    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return {"path": str(out), "engine": "python-pptx", "theme": theme, "html": None}
```

Update the routing in `build` — add this branch before the HTML handling:

```python
    if kind in PPTX_KINDS:
        return build_pptx(kind, content, out_path, theme)
```

(So `build` routes: DOCX kinds → `build_docx`, PPTX kinds → `build_pptx`, HTML kinds → inline HTML→PDF.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_make_document.py -q`
Expected: 4 passed.

- [ ] **Step 5: Run the full suite to confirm nothing regressed**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q`
Expected: all pass (243 prior + the new branding-guide tests).

- [ ] **Step 6: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
git add observepoint-revenue/skills/branding-guide/scripts/make_document.py observepoint-revenue/tests/test_make_document.py
git commit -m "feat(branding-guide): make_document deck (PPTX, dark default, bespoke renderer)"
```

---

## Task 9: Retrofit `build_proposal.py` to import brand_kit

**Files:**
- Modify: `observepoint-revenue/skills/scope-calculator/scripts/build_proposal.py:41-48`
- Test: `observepoint-revenue/tests/test_brand_kit.py` (add a parity assertion)

- [ ] **Step 1: Add a parity test that locks the shared values**

Append to `observepoint-revenue/tests/test_brand_kit.py`:

```python
def test_proposal_uses_brand_kit_constants():
    import build_proposal
    assert build_proposal.FONT == brand_kit.font()["family"]
    assert build_proposal.YELLOW_HEX.upper() == brand_kit.brand_yellow().lstrip("#").upper()
    assert build_proposal.DARK_HEX.upper() == brand_kit.colors()["ink"].lstrip("#").upper()
    assert build_proposal.LIGHT_HEX.upper() == brand_kit.colors()["light"]["fill"].lstrip("#").upper()
```

- [ ] **Step 2: Run test to verify it fails or errors**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_brand_kit.py::test_proposal_uses_brand_kit_constants -q`
Expected: FAIL/ERROR — `build_proposal` currently has its own constants; the parity test only passes once they derive from brand_kit (and `import brand_kit` resolves at runtime).

- [ ] **Step 3: Make `build_proposal.py` derive its constants from brand_kit**

At `build_proposal.py:41-48`, the current block is:

```python
from docx.shared import Inches, Pt, RGBColor

FONT = "Montserrat"
DARK = RGBColor(0x1E, 0x1E, 0x1E)
GRAY = RGBColor(0x5C, 0x5C, 0x5C)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

DARK_HEX, YELLOW_HEX, LIGHT_HEX = "1E1E1E", "F2CD14", "F2F2F2"
LOGO = pathlib.Path(__file__).resolve().parent.parent / "assets" / "op-logo.png"
```

Replace it with (resolve the sibling branding-guide scripts dir, import brand_kit, derive everything):

```python
from docx.shared import Inches, Pt, RGBColor

# --- ObservePoint brand authority (single source of truth) ---
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "branding-guide" / "scripts"))
import brand_kit  # noqa: E402

FONT = brand_kit.font()["family"]
DARK = brand_kit.rgbcolor(brand_kit.colors()["ink"])
GRAY = brand_kit.rgbcolor(brand_kit.colors()["light"]["gray"])
WHITE = brand_kit.rgbcolor(brand_kit.colors()["white"])

DARK_HEX = brand_kit.colors()["ink"].lstrip("#")
YELLOW_HEX = brand_kit.brand_yellow().lstrip("#")
LIGHT_HEX = brand_kit.colors()["light"]["fill"].lstrip("#")
LOGO = pathlib.Path(brand_kit.logo_path("light"))   # proposal is a light/print doc -> ink logo
```

Confirm `import sys` and `import pathlib` are already present at the top of `build_proposal.py` (they are — `pathlib` is used for `LOGO`). If `sys` is missing, add `import sys` with the other stdlib imports.

- [ ] **Step 4: Run the parity test + the existing proposal tests**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_brand_kit.py::test_proposal_uses_brand_kit_constants tests -q -k "proposal or brand_kit"`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
git add observepoint-revenue/skills/scope-calculator/scripts/build_proposal.py observepoint-revenue/tests/test_brand_kit.py
git commit -m "refactor(scope-calculator): build_proposal pulls brand from brand_kit (kills drift)"
```

---

## Task 10: Retrofit `build_model.py` and `build_internal_evidence.py`

**Files:**
- Modify: `observepoint-revenue/skills/scope-calculator/scripts/build_model.py:24-27`
- Modify: `observepoint-revenue/skills/scope-calculator/scripts/build_internal_evidence.py:25-26`
- Test: `observepoint-revenue/tests/test_brand_kit.py`

- [ ] **Step 1: Add parity tests**

Append to `observepoint-revenue/tests/test_brand_kit.py`:

```python
def test_model_uses_brand_kit_constants():
    import build_model
    assert build_model.FONT == brand_kit.font()["family"]
    assert build_model.YELLOW.upper() == brand_kit.brand_yellow().lstrip("#").upper()
    assert build_model.DARK.upper() == brand_kit.colors()["ink"].lstrip("#").upper()


def test_internal_evidence_uses_brand_kit_constants():
    import build_internal_evidence as bie
    assert bie.YELLOW.upper() == brand_kit.brand_yellow().lstrip("#").upper()
    assert bie.RED.upper() == brand_kit.colors()["semantic"]["alert"].lstrip("#").upper()
```

- [ ] **Step 2: Run to verify failure**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_brand_kit.py -q -k "model or internal_evidence"`
Expected: FAIL (constants not yet derived from brand_kit).

- [ ] **Step 3: Retrofit `build_model.py`**

At `build_model.py:24-27`, the current block is:

```python
FONT = "Montserrat"
DARK, YELLOW, LIGHT, GRAY, WHITE = "1E1E1E", "F2CD14", "F2F2F2", "5C5C5C", "FFFFFF"
INPUT_FILL = "FFF7CC"   # pale yellow — marks the editable levers
```
(plus `LOGO = ... / "assets" / "op-logo.png"` at line 27).

Replace with:

```python
# --- ObservePoint brand authority (single source of truth) ---
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "branding-guide" / "scripts"))
import brand_kit  # noqa: E402

FONT = brand_kit.font()["family"]
_c = brand_kit.colors()
DARK = _c["ink"].lstrip("#")
YELLOW = brand_kit.brand_yellow().lstrip("#")
LIGHT = _c["light"]["fill"].lstrip("#")
GRAY = _c["light"]["gray"].lstrip("#")
WHITE = _c["white"].lstrip("#")
INPUT_FILL = _c["light"]["input"].lstrip("#")   # pale yellow — marks the editable levers
LOGO = pathlib.Path(brand_kit.logo_path("light"))
```

Confirm `import sys` and `import pathlib` are present at the top of `build_model.py`; add `import sys` if missing.

- [ ] **Step 4: Retrofit `build_internal_evidence.py`**

At `build_internal_evidence.py:25-26`, the current block is:

```python
FONT = "Montserrat"
DARK, YELLOW, LIGHT, GRAY, WHITE, RED = "1E1E1E", "F2CD14", "F2F2F2", "5C5C5C", "FFFFFF", "F34146"
```

Replace with:

```python
# --- ObservePoint brand authority (single source of truth) ---
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "branding-guide" / "scripts"))
import brand_kit  # noqa: E402

FONT = brand_kit.font()["family"]
_c = brand_kit.colors()
DARK = _c["ink"].lstrip("#")
YELLOW = brand_kit.brand_yellow().lstrip("#")
LIGHT = _c["light"]["fill"].lstrip("#")
GRAY = _c["light"]["gray"].lstrip("#")
WHITE = _c["white"].lstrip("#")
RED = _c["semantic"]["alert"].lstrip("#")
```

Confirm `import sys` and `import pathlib` are present at the top; add `import sys` if missing.

- [ ] **Step 5: Run parity + scope-calculator tests**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q -k "model or internal_evidence or brand_kit"`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
git add observepoint-revenue/skills/scope-calculator/scripts/build_model.py \
        observepoint-revenue/skills/scope-calculator/scripts/build_internal_evidence.py \
        observepoint-revenue/tests/test_brand_kit.py
git commit -m "refactor(scope-calculator): build_model + build_internal_evidence pull brand from brand_kit"
```

---

## Task 11: Retrofit `build_dossier.py` (tokens + reuse `html_to_pdf`)

**Files:**
- Modify: `observepoint-revenue/skills/research-account/scripts/build_dossier.py:28-31` and the PDF section `:274-302`
- Test: `observepoint-revenue/tests/test_brand_kit.py`

- [ ] **Step 1: Add a parity test for the dossier palette**

Append to `observepoint-revenue/tests/test_brand_kit.py`:

```python
def test_dossier_uses_brand_kit_palette():
    import build_dossier
    d = brand_kit.theme("dark")
    assert build_dossier.YELLOW.upper() == brand_kit.brand_yellow().upper()
    assert build_dossier.BG.upper() == d["bg"].upper()
    assert build_dossier.PANEL.upper() == d["panel"].upper()
    assert build_dossier.TEXT.upper() == d["text"].upper()
    assert build_dossier.RED.upper() == brand_kit.colors()["semantic"]["alert"].upper()
```

- [ ] **Step 2: Run to verify failure**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_brand_kit.py::test_dossier_uses_brand_kit_palette -q`
Expected: FAIL (palette constants not yet from brand_kit).

- [ ] **Step 3: Retrofit the dossier palette block**

At `build_dossier.py:28-31`, the current block is:

```python
BG, PANEL, PANEL2, BORDER = "#14151a", "#1e2027", "#262932", "#313440"
TEXT, MUTED = "#e8e9ec", "#9aa1ad"
YELLOW, RED, GREEN, LINK = "#F2CD14", "#F34146", "#27a567", "#7cb8ff"
GRAYCHIP = "#3a3e49"
```

Replace with:

```python
# --- ObservePoint brand authority (single source of truth) ---
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "branding-guide" / "scripts"))
import brand_kit  # noqa: E402

_d = brand_kit.theme("dark")
_sem = brand_kit.colors()["semantic"]
BG, PANEL, PANEL2, BORDER = _d["bg"], _d["panel"], _d["panel2"], _d["border"]
TEXT, MUTED = _d["text"], _d["muted"]
YELLOW, RED, GREEN, LINK = brand_kit.brand_yellow(), _sem["alert"], _sem["success"], _sem["link"]
GRAYCHIP = "#3a3e49"   # dossier-only chip shade (not a brand token)
```

Confirm `import sys` and `import pathlib` are present near the top of `build_dossier.py` (both are used elsewhere — `subprocess`/`os`/`pathlib` already imported per the file header). Add `import sys` if missing.

- [ ] **Step 4: Replace the local `to_pdf`/`_find_chrome` with brand_kit's**

At `build_dossier.py:274-302` (the `# ---------- PDF rendering ----------` section through the end of `def to_pdf`), the file defines its own `_find_chrome()` and `to_pdf(html_path, pdf_path)`. Delete those two function definitions and replace the section with a thin delegate so there is one HTML→PDF implementation:

```python
# ---------- PDF rendering (delegated to brand_kit) ----------
def to_pdf(html_path, pdf_path):
    """Render html_path -> pdf_path via the shared brand_kit engine cascade."""
    return brand_kit.html_to_pdf(html_path, pdf_path)
```

Keep every existing call site of `to_pdf(...)` unchanged.

- [ ] **Step 5: Run dossier + brand tests**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q -k "dossier or brand_kit"`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
git add observepoint-revenue/skills/research-account/scripts/build_dossier.py observepoint-revenue/tests/test_brand_kit.py
git commit -m "refactor(research-account): build_dossier pulls dark palette + html_to_pdf from brand_kit"
```

---

## Task 12: De-dupe the logo assets

**Files:**
- Delete: `observepoint-revenue/skills/scope-calculator/assets/op-logo.png`
- Delete: `observepoint-revenue/skills/research-account/assets/op-logo.png`
- Test: `observepoint-revenue/tests/test_brand_kit.py`

The retrofits in Tasks 9–11 already point `LOGO` at `brand_kit.logo_path(...)`, so the per-skill copies are now unused.

- [ ] **Step 1: Add a guard test that no stale per-skill logo remains**

Append to `observepoint-revenue/tests/test_brand_kit.py`:

```python
def test_no_duplicate_per_skill_logos():
    import pathlib as _pl
    skills = _pl.Path(__file__).resolve().parent.parent / "skills"
    stale = list(skills.glob("scope-calculator/assets/op-logo.png")) + \
            list(skills.glob("research-account/assets/op-logo.png"))
    assert stale == [], f"stale per-skill logos still present: {stale}"
    # the one canonical asset exists
    assert (skills / "branding-guide" / "assets" / "logo-primary.png").exists()
```

- [ ] **Step 2: Run to verify failure**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_brand_kit.py::test_no_duplicate_per_skill_logos -q`
Expected: FAIL (the two per-skill copies still exist).

- [ ] **Step 3: Delete the duplicate logos**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
git rm observepoint-revenue/skills/scope-calculator/assets/op-logo.png \
       observepoint-revenue/skills/research-account/assets/op-logo.png
```

- [ ] **Step 4: Run the full suite**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q`
Expected: all pass (the retrofitted renderers resolve the logo through brand_kit).

- [ ] **Step 5: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
git add observepoint-revenue/tests/test_brand_kit.py
git commit -m "refactor(branding-guide): de-dupe logo — single canonical asset via brand_kit"
```

---

## Task 13: SKILL.md + reference docs

**Files:**
- Create: `observepoint-revenue/skills/branding-guide/SKILL.md`
- Create: `observepoint-revenue/skills/branding-guide/references/brand-guidelines.md`
- Create: `observepoint-revenue/skills/branding-guide/references/voice-and-messaging.md`

- [ ] **Step 1: Write `SKILL.md`**

```markdown
---
name: branding-guide
description: Use whenever a document, deck, one-pager, letter, report, or any rendered artifact "related to ObservePoint" is being created, branded, or checked — and as the brand authority the other revenue skills call before they render. Triggers — "brand this", "make it on-brand", "ObservePoint one-pager / deck / letter", "is this on brand", "brand check", "what's our brand color / logo / font". Holds the single source of truth (colors, fonts, logos, themes, voice, boilerplate); other skills (and the observepoint-consultant plugin) consume it instead of hardcoding brand values. For sizing/pricing use scope-calculator; for account research use research-account.
---

# branding-guide — the ObservePoint brand authority

**Architecture (matches the plugin):** Claude judges voice/usage; deterministic
Python (`brand_kit.py`) provides the tokens and renders. Never invent a brand
value — every color, font, logo, and boilerplate string comes from
`references/brand-spec.json` via `brand_kit`.

## The non-negotiables
- **One source of truth:** `references/brand-spec.json`. Read brand values through
  `brand_kit` (or `python scripts/brand_kit.py --emit-json` from another plugin) —
  never copy hexes into a new script.
- **Company name** is always `ObservePoint` (one word, capital O, capital P). Run
  `brand_check.py` to catch `Observepoint` / `Observe Point` and off-palette colors.
- **Themes:** dark is the default for presentation surfaces (HTML dossier, PDFs,
  reports, one-pagers, decks); light is the default for working docs (`.xlsx`
  workbook, `.docx` proposal, letters, memos). Use
  `brand_kit.default_theme_for(<format>)`; honor an explicit `--theme` override.
- **Copyright** on every rendered artifact: `brand_kit.copyright(<year>)`.
- **Logos:** dark bg → primary (yellow); light bg → ink. Resolve with
  `brand_kit.logo_path(theme)`. Never recolor or stretch the logo.

## How other skills call it
A renderer in a sibling skill puts the branding-guide scripts dir on `sys.path`
and imports the kit:
```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "branding-guide" / "scripts"))
import brand_kit
```
Cross-plugin (e.g. observepoint-consultant): call
`python <path>/branding-guide/scripts/brand_kit.py --emit-json` and read the JSON.

## Scripts
- `brand_kit.py` — tokens, themes, `logo_path`, fonts, docx/xlsx/html helpers,
  `html_to_pdf`, `--emit-json`.
- `verify_brand.py` — re-pull the live site, report drift vs the spec (never edits it).
- `brand_check.py <file> [--fix]` — flag/fix disallowed names + off-palette colors.
- `make_document.py <kind> <content.json> <out> [--theme]` — `onepager`/`report`
  (PDF), `letter`/`memo` (DOCX), `deck` (PPTX).

## Keeping it current
Run `verify_brand.py` periodically. On drift, update `brand-spec.json` deliberately
and bump `meta.last_verified` — the script never self-edits.

## Confirm-when-available (tracked in brand-spec.json)
- Real `logo-secondary.png` (white+yellow deck wordmark) — currently falls back to primary.
- Official "About ObservePoint" boilerplate (`boilerplate.about_confirmed=false`).
- Dark-surface hexes (reverse-engineered from the dossier) vs the official brand guide.
```

- [ ] **Step 2: Write `references/brand-guidelines.md`**

```markdown
# ObservePoint brand — usage guidelines

Human-readable companion to `brand-spec.json` (the machine source of truth). When
they disagree, the JSON wins; fix the JSON, then this doc.

## Colors
- **Brand yellow `#F2CD14`** — the signature accent. Verified from the site CSS
  (`.logo{color:#f2cd14}`). Use for accents, rules, chips, highlights — not body text.
- **Ink `#1E1E1E`** — primary text on light; near-black brand neutral.
- **Dark surfaces** — bg `#14151A`, panel `#1E2027`, panel2 `#262932`, border `#313440`,
  text `#E8E9EC`, muted `#9AA1AD`.
- **Light surfaces** — page `#FFFFFF`, fill `#F2F2F2`, gray `#5C5C5C`, input `#FFF7CC`,
  hairline `#D9D9D9`.
- **Semantic** — success `#27A567`, alert `#F34146`, link `#7CB8FF`.

## Logos
- **Primary** (all-yellow logotype) → dark backgrounds only.
- **Ink** (dark logotype) → light backgrounds.
- **Secondary** (white Observe + yellow Point) → decks (file pending).
- **Favicon** (OP monogram, gray on yellow) → small spaces / app icon.
- Don't recolor, rotate, stretch, add effects, or place the yellow primary on a light
  background (it disappears — use ink).

## Typography
- **Montserrat** everywhere. Weights: 400 body, 600 labels, 700 subheads, 800 headlines.
- Fallback stack: `-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif`.

## Themes by format
- **Dark (default):** HTML dossier, PDFs, one-pagers, reports, decks.
- **Light (default):** `.xlsx` workbook, `.docx` proposal, letters, memos.
- Either is available on request via `--theme`.
```

- [ ] **Step 3: Write `references/voice-and-messaging.md`**

```markdown
# ObservePoint voice & messaging

## Name & terminology
- The company is **ObservePoint** — one word, capital O and P. Never "Observepoint",
  "Observe Point", or all-caps in body copy. The monogram **OP** is for the icon only.
- Product names (use exactly): Website Privacy Scan, Analytics Validation Scan,
  Website Accessibility Scan, Full Website Audit, Consent Banner Audit, Marketing
  Landing Page & Email Scan, Tag and Cookie Debugger.

## Positioning
- Tagline: *"The Automated Website Scanner for Privacy, Accessibility, Tag Accuracy,
  and More."*
- About (PROVISIONAL — `about_confirmed=false`): confirm the official boilerplate with
  marketing before using externally.

## Tone
- Direct, technical, credible. We sell governance and trust to enterprise teams —
  precise over hype. Lead with evidence (numbers, findings), not adjectives.
- Avoid fabricated stats. Cite what the scan/audit actually found.

## Mechanical checks
`brand_check.py` enforces the name spellings and off-palette colors. Everything else
in this doc is editorial judgment for Claude to apply when writing copy.
```

- [ ] **Step 4: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
git add observepoint-revenue/skills/branding-guide/SKILL.md observepoint-revenue/skills/branding-guide/references/brand-guidelines.md observepoint-revenue/skills/branding-guide/references/voice-and-messaging.md
git commit -m "docs(branding-guide): SKILL.md + brand-guidelines + voice-and-messaging references"
```

---

## Task 14: Register the 5th skill (CLAUDE.md, README, ROADMAP, manifests, version bump)

**Files:**
- Modify: `CLAUDE.md` (Skills section)
- Modify: `README.md`
- Modify: `docs/ROADMAP.md`
- Modify: `observepoint-revenue/.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`

- [ ] **Step 1: Update `CLAUDE.md` — bump the count and add the bullet**

Change the heading `## Skills (4)` to `## Skills (5)` and add this bullet to the list:

```markdown
- **branding-guide** — the single source of truth for ObservePoint's brand (colors,
  fonts, logos, dark/light themes, voice, boilerplate). Other skills call it before
  rendering any OP document; it also makes net-new branded docs (one-pager/report/
  letter/memo/deck), checks drafts (`brand_check.py`), and watches the live site for
  drift (`verify_brand.py`). `brand_kit.py` is the shared render kit they import.
```

Also add to the "Architecture principle" / conventions area a one-liner:

```markdown
- **Brand values come from `branding-guide` only** — `references/brand-spec.json` via
  `brand_kit`; never hardcode a hex/font/logo path in a renderer.
```

- [ ] **Step 2: Update `README.md`**

Add `branding-guide` to the skills list/description in `README.md`, mirroring the
CLAUDE.md bullet (one sentence: "branding-guide — ObservePoint brand authority + branded
document maker + brand checker"). Match the file's existing formatting.

- [ ] **Step 3: Update `docs/ROADMAP.md`**

Move/append a line marking `branding-guide` as built (date 2026-06-17), in the same
style as the other shipped skills in that file.

- [ ] **Step 4: Update `observepoint-revenue/.claude-plugin/plugin.json`**

Bump `version` `0.15.0` → `0.16.0` and extend `description` to mention branding-guide,
e.g. append: ` branding-guide (the single source of truth for ObservePoint branding —
colors, fonts, logos, themes, voice — that every renderer consumes, plus a branded
document maker, a brand checker, and a live-site drift check).`

- [ ] **Step 5: Update `.claude-plugin/marketplace.json`**

Append the same branding-guide clause to the plugin `description` there so the
marketplace listing matches.

- [ ] **Step 6: Run the full suite one last time**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
git add CLAUDE.md README.md docs/ROADMAP.md observepoint-revenue/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "chore: register branding-guide as the 5th skill; bump plugin 0.15.0 -> 0.16.0"
```

---

## Self-Review

**1. Spec coverage** (against the approved design):
- §1 brand authority / standalone skill → Tasks 1–3, 13.
- §2 layout (references/assets/scripts) → Tasks 1–8, 13.
- §3 brand-spec.json source of truth → Task 1.
- §4 brand_kit deterministic helpers + retrofit the 4 renderers → Tasks 2–3, 9–11.
- §5 import-path sharing + `--emit-json` CLI → Tasks 2 (conftest), 3 (CLI), 9–11 (sys.path pattern), 13 (documented).
- §6 dark-for-presentation / light-for-working-docs → `format_defaults` (Task 1), `default_theme_for` (Task 2), applied in Tasks 6–8.
- §7 verify_brand drift check → Task 4.
- §8 all three capabilities (authority + checker + doc-maker) → checker Task 5, doc-maker Tasks 6–8.
- de-dupe logo → Task 12.
- §9 open items flagged in spec → encoded in brand-spec.json (`logo-secondary` fallback note, `about_confirmed=false`, dark-surface note) and SKILL.md "confirm-when-available".
- docs/manifest registration → Task 14.

**2. Placeholder scan:** No "TBD/TODO/implement later" in plan steps. The only "TODO/PROVISIONAL" strings are *intentional data* in `brand-spec.json` (`about`, guarded by `about_confirmed=false`) and are documented as confirm-when-available — not plan placeholders.

**3. Type/name consistency:** `brand_kit` API names used identically across tasks — `theme`, `default_theme_for`, `logo_path`, `logo_data_uri`, `css_vars`, `rgbcolor`, `xlsx_font`, `xlsx_fill`, `html_to_pdf`, `brand_yellow`, `colors`, `font`, `copyright`, `naming`, `boilerplate`. `make_document.build(kind, content, out_path, theme=None)` returns `{"path","engine","theme","html"}` consistently across Tasks 6–8. Retrofit parity tests reference the same constant names the retrofits define (`FONT`, `DARK`/`DARK_HEX`, `YELLOW`/`YELLOW_HEX`, `LIGHT`/`LIGHT_HEX`, `RED`, `BG`, `PANEL`, `TEXT`).

---

## Open Items (carried from the spec — do not block the build)
- Provide the real `logo-secondary.png` (deck wordmark); until then `logo_path(variant="secondary")` falls back to primary.
- Confirm the official "About ObservePoint" boilerplate; set `boilerplate.about_confirmed=true` once verified.
- Confirm the dark-surface hexes against the official ObservePoint brand guide if/when one is provided.
