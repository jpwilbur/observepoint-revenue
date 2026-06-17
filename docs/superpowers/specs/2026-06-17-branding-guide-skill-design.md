# Spec: `branding-guide` skill (ObservePoint brand authority)

**Plugin:** `observepoint-revenue` (5th skill; sibling of `scope-calculator`, `research-account`,
`find-accounts`, `owned-properties`).
**Status:** approved design (pending build). **Date:** 2026-06-17.

---

## 1. Goal & intent

ObservePoint branding is currently hardcoded and **drifting** across at least three codebases:

| Source | Yellow | Dark | Light |
|---|---|---|---|
| This plugin's renderers (`build_proposal`, `build_model`, …) | `#F2CD14` | `#1E1E1E` | `#F2F2F2` |
| WGMA app (`BrandHeader.tsx`, commented *"sampled from the OP deck — confirm exact hexes"*) | `#efc100` | `#1c1c1e` | `#f4f4f5` |
| `research-account` dossier dark theme | `#F2CD14` | `#14151A` | — |
| **Live site CSS (authoritative)** | **`#F2CD14`** | — | — |

`branding-guide` is the **single source of truth** for the ObservePoint brand. It holds the brand
values, assets, and voice once; every document-producing skill pulls from it instead of re-declaring
constants, which is what *structurally* ends the drift (nothing to copy, nothing to re-mistype).

It is a **standalone skill** with three capabilities, all shipped together:

1. **Brand authority** — the canonical spec (colors, typography, logo variants + usage rules, dark/
   light themes, naming, boilerplate) + bundled assets + a deterministic `brand_kit.py` helper that
   renderers import.
2. **Brand checker** — lint (and optionally fix) an existing document or block of text against the
   spec: wrong "ObservePoint" capitalization, off-palette colors, missing/wrong logo, missing
   copyright/boilerplate.
3. **Doc-maker** — render net-new branded documents the other skills don't already produce:
   one-pager (PDF), slide deck (PPTX), letter/memo (DOCX), generic HTML→PDF report.

It can be **invoked directly** ("brand this", "make an OP one-pager", "check this deck") and is
**invoked by the sibling skills** before they render any ObservePoint document. The
`observepoint-consultant` plugin reuses it too (see §6).

**Success:** one place defines the brand; all five revenue skills (and the consultant plugin) render
identical, correct branding; drift is detectable on demand; net-new branded docs and brand checks are
one skill invocation away. No fabricated brand values — every token traces to the spec, and the spec
traces to a dated source.

---

## 2. Architecture & data flow

Mirrors the plugin's principle — **Claude gathers and judges → deterministic Python scripts compute
and render.** Claude decides *what* to say (voice, copy, which document, which theme when ambiguous)
and applies the usage rules; `brand_kit.py` deterministically supplies tokens, resolves the right
logo/theme, and the renderers lay out files. There is **no LLM-maintained brand state** — the brand
lives in `brand-spec.json`, a versioned data file that humans edit deliberately.

```
brand-spec.json  ──read──>  brand_kit.py  ──tokens/themes/logo paths/style helpers──>  renderers
      ▲                          │                                                      ├─ sibling skills' build_*.py (retrofit)
      │                          └── --emit-json (CLI) ──> external consumers (consultant plugin)
   verify_brand.py (re-pull live site, diff, report — never auto-writes)
```

---

## 3. Layout

```
skills/branding-guide/
  SKILL.md                         # when-to-use; non-negotiables; voice summary; how siblings call it
  references/
    brand-spec.json                # ← THE canonical source of truth (machine-readable)
    brand-guidelines.md            # logo do/don'ts, clear-space, color usage (human-readable mirror)
    voice-and-messaging.md         # tone, naming rules, boilerplate, product names, words to avoid
  assets/
    logo-primary.png               # all-yellow logotype (dark bg) — canonical 366×57 file
    logo-secondary.png             # white "Observe" + yellow "Point" wordmark (decks) — TO CONFIRM file
    logo-ink.png                   # dark/ink logotype for LIGHT backgrounds — TO CONFIRM it exists
    favicon.png                    # "OP" monogram (gray on yellow)
  scripts/
    brand_kit.py                   # loads spec; palette/themes/fonts/logo resolver + docx/xlsx/html helpers; --emit-json CLI
    verify_brand.py                # re-pull live site, diff vs spec, print drift report
    brand_check.py                 # lint/fix a document or text against the spec
    make_document.py               # render a net-new branded document (one-pager / deck / letter / report)
```

---

## 4. `brand-spec.json` — the source of truth

A single JSON document. Indicative shape (exact keys finalized in implementation):

```jsonc
{
  "meta": {
    "version": "1.0.0",
    "last_verified": "2026-06-17",
    "sources": [
      "https://www.observepoint.com/ (site CSS: .logo{color:#f2cd14})",
      "observepoint-revenue renderers", "WGMA app BrandHeader.tsx (drift reference)"
    ]
  },
  "colors": {
    "brand_yellow": "#F2CD14",          // VERIFIED from live site CSS
    "ink": "#1E1E1E",                   // canonical near-black (corrects WGMA #1c1c1e)
    "white": "#FFFFFF",
    "dark":  { "bg": "#14151A", "panel": "#1E2027", "panel2": "#262932",
               "border": "#313440", "text": "#E8E9EC", "muted": "#9AA1AD" },
    "light": { "page": "#FFFFFF", "fill": "#F2F2F2", "gray": "#5C5C5C",
               "input": "#FFF7CC", "hairline": "#D9D9D9", "text": "#1E1E1E" },
    "semantic": { "success": "#27A567", "alert": "#F34146", "link": "#7CB8FF" },
    "dataviz": ["#2874FC","#27A567","#F34146","#E0249A","#1FB6B6","#9B51E0","#FF8C1A","#F2CD14"] // APPROX — TO CONFIRM
  },
  "typography": {
    "family": "Montserrat",
    "weights": [400, 600, 700, 800],
    "fallback": "-apple-system, \"Segoe UI\", Roboto, Helvetica, Arial, sans-serif",
    "google_fonts": "https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap"
  },
  "logos": {
    "primary":   { "file": "logo-primary.png",   "for_background": "dark",  "desc": "all-yellow logotype" },
    "secondary": { "file": "logo-secondary.png", "for_background": "dark",  "desc": "white+yellow wordmark (decks)" },
    "ink":       { "file": "logo-ink.png",        "for_background": "light", "desc": "dark logotype for light bg" },
    "favicon":   { "file": "favicon.png",         "desc": "OP monogram" },
    "min_width_px": 120, "clear_space": "0.5× logo height on all sides"
  },
  "themes": {
    "dark":  { "default": true,  "logo": "primary", "surface": "dark",  "accent": "brand_yellow" },
    "light": { "default": false, "logo": "ink",     "surface": "light", "accent": "brand_yellow" }
  },
  "format_defaults": {
    "html": "dark", "pdf": "dark", "deck": "dark", "onepager": "dark", "letter": "light",
    "report": "dark", "xlsx": "light", "docx": "light"
  },
  "naming": {
    "canonical": "ObservePoint",
    "rules": "one word, capital O and capital P; never 'Observepoint', 'Observe Point', or lowercase except in domains/code/URLs; 'OP' only as the monogram/icon, not in prose",
    "products": ["Website Privacy Scan","Analytics Validation Scan","Website Accessibility Scan",
                 "Full Website Audit","Consent Banner Audit","Marketing Landing Page & Email Scan",
                 "Tag and Cookie Debugger"]  // from site — TO CONFIRM the authoritative list
  },
  "boilerplate": {
    "copyright": "© {year} ObservePoint. All rights reserved.",
    "positioning": "The Automated Website Scanner for Privacy, Accessibility, Tag Accuracy, and More", // site hero — TO CONFIRM official tagline
    "about": "<official 'About ObservePoint' paragraph — TO CONFIRM>"
  }
}
```

Values marked **VERIFIED** are confirmed from an authoritative source; **TO CONFIRM** are
reverse-engineered defaults awaiting an official brand-guide / marketing input, and are flagged in the
spec so they are never silently treated as gospel.

---

## 5. `brand_kit.py` — the deterministic helper

Reads `references/brand-spec.json` (path resolved relative to `__file__`). Public API:

- `load_spec() -> dict`
- `theme(name="dark") -> dict` — resolved role→hex palette for a theme
- `default_theme_for(fmt) -> str` — `"dark"`/`"light"` from `format_defaults`
- `logo_path(theme="dark", variant=None) -> str` — absolute path to the right logo asset for the
  theme/background (override with `variant`)
- `font() -> (family, fallback, google_fonts_url)`
- `copyright(year) -> str`, `boilerplate(key) -> str`
- **docx helpers** — return `RGBColor` / a run-styler so `build_proposal.py` drops its local
  `DARK`/`YELLOW`/`FONT` constants
- **xlsx helpers** — return `Font`/`PatternFill` builders for `build_model.py` /
  `build_internal_evidence.py`
- **html helpers** — return a CSS-variables block / token dict for `build_dossier.py`
- **CLI:** `python brand_kit.py --emit-json` prints the resolved spec to stdout (the portable bridge
  for non-Python or cross-plugin consumers)

All deterministic; no network, no randomness.

---

## 6. How it is shared (import path)

- **Within the plugin:** a renderer resolves the sibling scripts dir off its own location and imports
  the kit:
  ```python
  import sys, pathlib
  sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "branding-guide" / "scripts"))
  import brand_kit
  ```
  No install step. `tests/conftest.py` already adds each skill's scripts dir to `sys.path`, so
  `brand_kit` imports cleanly under pytest too (add `branding-guide/scripts` there).
- **Cross-plugin (`observepoint-consultant`):** the consultant skill invokes `branding-guide` by name
  (works when both plugins are installed). For tokens without a Python dependency it calls
  `python brand_kit.py --emit-json` and reads the JSON. The skill dir is self-contained (spec +
  assets + kit), so it stays portable.

---

## 7. Themes (decided)

- **Dark = default for presentation surfaces:** HTML dossier, PDFs, decks, one-pagers, generic
  reports — uses the all-yellow **primary** logo on the dark surface ramp.
- **Light = default for working docs:** the editable `.xlsx` Scope-of-Work workbook and the printable
  `.docx` proposal/letter — uses the **ink** logo on a light surface.
- Either theme is selectable on request (`--theme dark|light`); `format_defaults` only sets the
  default when the caller doesn't specify.

---

## 8. `verify_brand.py` — staying up-to-date

Re-fetches the live site CSS, header logo, and favicon; extracts the brand yellow, key tokens, and
asset hashes; compares to `brand-spec.json`; prints a **drift report**
(`site yellow #F2CD14 == spec ✓`, `favicon hash changed ⚠`). It **never auto-edits** the spec —
Claude/the user reviews the report and bumps the spec + `last_verified` deliberately. Reproducible;
no LLM-maintained state. Run on demand or on a schedule.

---

## 9. `brand_check.py` — checker

Given a file (`.docx`/`.xlsx`/`.html`/`.pdf`-text/`.md`/plain text) or a string:
- flags **naming** violations ("Observepoint", "Observe Point", stray lowercase, "OP" in prose);
- flags **off-palette** colors (hexes not in the spec, with nearest on-brand suggestion);
- checks for the **logo** and **copyright/boilerplate** presence where expected;
- reports findings; with `--fix`, applies the safe, unambiguous corrections (e.g. capitalization,
  copyright line) and lists the rest for human review.
Claude judges ambiguous cases; the script does deterministic detection/replacement.

---

## 10. `make_document.py` — doc-maker

Renders a net-new branded document. Claude assembles the content (never fabricated); the renderer
lays it out from `brand_kit` tokens/assets. Formats (all in scope):

- **one-pager** → HTML→PDF, dark default (reuses the dossier's HTML→PDF pattern)
- **deck** → **bespoke** PPTX renderer via `python-pptx` (branded title/section/content masters,
  themed directly from `brand_kit` — consistent with how the plugin renders everything else)
- **letter / memo** → DOCX, light default (letterhead logo + footer/copyright)
- **report** → generic multi-section branded HTML→PDF, dark default

CLI shape: `make_document.py <format> <content.json> <out.path> [--theme dark|light]`.

---

## 11. Retrofit of existing renderers

Replace local brand constants with `brand_kit` imports, preserving current output where the theme is
unchanged (light workbook/proposal stay light; dark dossier stays dark — they just source values
centrally):

- `scope-calculator/scripts/build_proposal.py` (`FONT`, `DARK`, `YELLOW_HEX`, … → kit)
- `scope-calculator/scripts/build_model.py`
- `scope-calculator/scripts/build_internal_evidence.py`
- `research-account/scripts/build_dossier.py` (palette block → kit html helpers)

**De-dupe the logo:** delete the per-skill `assets/op-logo.png` copies (scope-calculator,
research-account) and resolve the single `branding-guide/assets/logo-primary.png` via
`brand_kit.logo_path()`.

---

## 12. `SKILL.md` (self-sufficient at runtime)

- **When to use:** "brand / brand-check / make an OP document"; and "invoked by a sibling skill before
  it renders any ObservePoint document."
- **Non-negotiables:** never fabricate a brand value; always source tokens from `brand-spec.json` via
  `brand_kit`; correct "ObservePoint" capitalization; include copyright/boilerplate; pick the theme by
  `format_defaults` unless told otherwise; `verify_brand.py` reports drift but only humans update the
  spec.
- **Voice & messaging** summary (full detail in `references/voice-and-messaging.md`).
- **How sibling skills call it** (the `sys.path` import + `--emit-json` CLI).

---

## 13. Testing

- `brand_kit`: spec loads; `theme()`/`default_theme_for()`/`logo_path()` return expected values;
  `--emit-json` round-trips; logo files exist.
- `verify_brand`: against a captured site-CSS fixture, detects a match and a planted drift (no network
  in tests).
- `brand_check`: catches naming + off-palette violations on fixtures; `--fix` corrects the safe ones.
- `make_document`: each format produces a non-empty file with the logo embedded and the right theme.
- Retrofit: existing scope-calculator / research-account renderer tests still pass (output equivalence
  where theme unchanged).
- Add `branding-guide/scripts` to `tests/conftest.py` sys.path. Run with `/opt/homebrew/bin/python3 -m
  pytest tests -q`.

---

## 14. Docs & manifest updates

- `CLAUDE.md` — "Skills (4)" → "(5)"; add a `branding-guide` bullet; note the shared-brand convention.
- `README.md` — add the skill.
- `docs/ROADMAP.md` — move/record this work.
- `observepoint-revenue/.claude-plugin/plugin.json` + root `.claude-plugin/marketplace.json` —
  add `branding-guide` to the description; bump plugin version.

---

## 15. Open items to confirm (do not block the build; flagged in the spec as TO CONFIRM)

1. The real **secondary** (white+yellow) logo file; whether an **ink/dark** primary exists for light
   backgrounds (else light theme uses a dark-typeset wordmark).
2. Official **"About ObservePoint" boilerplate**, the official **tagline**, and the authoritative
   **product-name** list.
3. The **dark-surface hexes** (`#14151A` ramp) and the **data-viz categorical** set are
   reverse-engineered — confirm against an official brand guide if one surfaces.

---

## 16. Non-goals (this build)

- No separate brand *plugin* (stays one plugin, per the project principle).
- No automatic spec mutation (verify reports; humans decide).
- No web/email-template system; no font self-hosting beyond what renderers already use.
- Not re-theming existing documents beyond sourcing their values centrally (themes per §7).
