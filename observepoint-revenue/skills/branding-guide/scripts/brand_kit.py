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
import base64
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


def html_to_pdf(html_path: str, pdf_path: str, timeout: int = 60):
    """Render html_path -> pdf_path. Returns the engine name used, or None if none worked.

    timeout: max seconds for the headless-Chrome attempt (heavy pages may need more;
    the dossier passes 90)."""
    chrome = _find_chrome()
    if chrome:
        try:
            subprocess.run(
                [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                 f"--print-to-pdf={pdf_path}", pathlib.Path(html_path).resolve().as_uri()],
                check=True, capture_output=True, timeout=timeout)
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


def _main(argv) -> int:
    if "--emit-json" in argv:
        print(json.dumps(load_spec(), indent=2))
        return 0
    sys.stderr.write("usage: brand_kit.py --emit-json\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
