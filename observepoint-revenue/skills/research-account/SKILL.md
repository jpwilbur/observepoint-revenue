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

2. **Default scan (always):**
   - Call `detect_cmp({url: "https://<domain>/"})`. Record the CMP vendor (or none) and the
     `supported` flag.
   - **Tag/pixel inventory:** `WebFetch` the homepage (and 1–2 high-value pages) and identify the
     MarTech/pixel stack from script signatures — GTM (`googletagmanager.com/gtm.js`), GA4 (`gtag`),
     Adobe Launch (`assets.adobedtm.com`), Tealium (`tags.tiqcdn.com`), Segment, Meta Pixel
     (`fbevents.js`), etc.
   - **Caveat:** a POSITIVE finding is evidence; a NEGATIVE is inconclusive (static fetch misses
     dynamically-injected tags / lazy CMPs). Never assert "no CMP / no tags" from a null scan.

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
   - Source **2–5 real, currently-employed** contacts: name, title, linkedin, `sourceVerified`,
     `sourceUrl`, `personalizationHook`, `toneGuidance`, `avoid`. **No placeholders, no fabricated
     people or sources.** If you cannot verify a person, set `sourceVerified:false` (the dossier
     flags them as held back) — never invent.

5. **Write the classification JSON** to a temp file (e.g. `/tmp/<slug>-classification.json`) with
   keys: `account`, `domain`, `prepared_by`, `date` (today's date), `scan{}`, `fit[]`,
   `triggers[]`, `rationale`, `research{}`, `contacts[]`. (See the spec §4 for the exact shape.)

6. **Score it:**
   ```bash
   python3 "$SKILL/scripts/score_account.py" /tmp/<slug>-classification.json /tmp/<slug>-scored.json
   ```

7. **Render the dossier:**
   ```bash
   python3 "$SKILL/scripts/build_dossier.py" /tmp/<slug>-scored.json "<out>.docx"
   ```
   **Output location (uniform across the plugin):** if the rep named a folder, use it. Otherwise
   default to `~/Documents/ObservePoint Revenue/Account Research/` — expand `~` to the home dir and
   `mkdir -p` the folder first; never leave the deliverable in a temp dir. Name the file
   `<Company> - research dossier.docx`.

8. **Summarize in chat:** final score, QUALIFIED/NOT, dominant fit angle, the top trigger, number of
   sourced vs held-back contacts, and the `.docx` path.

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
