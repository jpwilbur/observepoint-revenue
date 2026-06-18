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
