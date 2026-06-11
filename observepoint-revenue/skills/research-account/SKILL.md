---
name: research-account
description: Use when a revenue or sales rep wants to research and qualify a single named prospect for ObservePoint — "research <company>", "is <company> a good fit", "qualify this account", "build an account dossier", "why now for <company>". Produces a scored ICP dossier (.docx) with dated/sourced why-now triggers and real sourced contacts. For sizing or pricing a deal use scope-calculator; this is account research, not contract scoping.
---

# Research Account

Given a named prospect, qualify it against ObservePoint's ICP, surface dated and sourced "why now"
triggers, build a deep dossier with real sourced contacts, score it deterministically, and render a
themed `.docx`.

This skill is the research brain ported from the NERD tool. The model classifies and researches;
`score_account.py` does the math; `build_dossier.py` renders the document.

## Inputs

- **Company name** (required).
- **Domain** (optional — look it up if not given).
- **`--deep-scan`** (optional flag) — also size an ObservePoint Site Census for `webScale`
  (time-intensive; only when asked).

## Workflow

Set `SKILL=${CLAUDE_PLUGIN_ROOT}/skills/research-account`. Read these references first:
`$SKILL/references/trigger-and-fit.md`, `$SKILL/references/research-and-contacts.md`,
`$SKILL/references/icp-and-tone.md`, and `$SKILL/references/scoring-config.json` (for the exact `fit`
keys and `whyNow` scoreKeys you must use).

1. **Resolve the domain.** Use the given domain, or find the prospect's primary domain via a quick
   `WebSearch`.

2. **Default scan (always):** `detect_cmp({url: "https://<domain>/"})` (record vendor or none + the
   `supported` flag), then `WebFetch` the homepage (+ 1–2 key pages) for the MarTech/pixel stack via
   the script signatures in `trigger-and-fit.md`. **Caveat:** a POSITIVE finding is evidence; a
   NEGATIVE is inconclusive (static fetch misses dynamically-injected tags / lazy CMPs) — never
   assert "no CMP / no tags" from a null scan.

3. **`--deep-scan` only:** if the rep asked for it and a relevant Site Census exists, call
   `size_site_census` to measure `webScale` (real page count, multi-domain/SPA complexity); put the
   result in `scan.site_census`. Skip silently if unavailable.

4. **Research (WebSearch/WebFetch)** following the two reference prompts:
   - Classify each of the 6 ICP `fit` criteria (`met` true/false + short `evidence`), folding in the
     scan findings (CMP → `privacyConsentSurface`; tags → `tagPixelDensity`; census → `webScale`).
   - Find dated, **sourced** why-now triggers, each tagged with the single best `scoreKey` from
     `scoring-config.json`. Every trigger needs a real `sourceUrl` and a genuine web-tracking nexus.
     An empty trigger list is a valid, honest result — do not stretch (no BIPA, generic breaches,
     antitrust, product-safety).
   - Write the dossier fields (overview, pain hypotheses, competitor intel, tech-stack notes, best
     opening angle = INTERNAL strategy, research sources).
   - Source **2–5 real, currently-employed** contacts with the fields in `research-and-contacts.md`.
     **Never fabricate a person or source** — if you can't verify someone, set `sourceVerified:false`
     and the dossier flags them held back.

5. **Write the classification JSON** (`/tmp/<slug>-classification.json`) with the shape in spec §4
   (`account`, `domain`, `prepared_by`, `date`, `scan{}`, `fit[]`, `triggers[]`, `rationale`,
   `research{}`, `contacts[]`).

6. **Score it:**
   ```bash
   python3 "$SKILL/scripts/score_account.py" /tmp/<slug>-classification.json /tmp/<slug>-scored.json
   ```

7. **Render the dossier (dark, NERD-styled HTML → PDF):**
   ```bash
   python3 "$SKILL/scripts/build_dossier.py" /tmp/<slug>-scored.json "<out>.pdf"
   ```
   Freezes a self-contained dark dossier to `.pdf` (headless Chrome → weasyprint → HTML fallback;
   the script prints the path). **Output location (uniform across the plugin) — one folder per
   account:** rep-named base folder, else default `~/Documents/ObservePoint Revenue/Account Research/`;
   create a **per-account subfolder** and write `<Company> - research dossier.pdf` there. Expand `~`,
   `mkdir -p` first, never a temp dir. (Only the `.pdf` lands.)

8. **Summarize in chat:** final score, QUALIFIED/NOT, dominant fit angle, the top trigger, number of
   sourced vs held-back contacts, and the `.pdf` path.

## Red flags — stop and fix

| Rationalization | Reality |
|---|---|
| "I'll estimate the score myself." | No. `score_account.py` computes it from the config weights. You only classify. |
| "I couldn't find a contact, I'll put a likely name." | Never fabricate a person or a source URL. Set `sourceVerified:false`. |
| "The scan found no CMP, so they have none." | A static fetch misses lazy CMPs. Negative = inconclusive; use the web signal. |
| "There's a big lawsuit — lead the dossier with it as the pitch." | The legal angle is INTERNAL strategy only. Outreach copy is a separate, governed step. |
| "No trigger found, I'll stretch to a BIPA/antitrust item." | Triggers need a web-tracking nexus. An empty list is a valid result. |

## What this skill does not do (v1)

Discovery/territory prospecting, contact enrichment (email/phone), sequencing/sending, and Salesforce
sync are out of scope. The dossier is the deliverable; the rep takes it from there.
