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
