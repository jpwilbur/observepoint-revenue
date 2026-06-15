---
name: research-account
description: Use when a revenue or sales rep wants to research and qualify a single named prospect for ObservePoint — "research <company>", "is <company> a good fit", "qualify this account", "build an account dossier", "why now for <company>". Produces a scored ICP PDF dossier (self-contained HTML fallback if no PDF engine is present) with dated/sourced why-now triggers and real sourced contacts. For sizing or pricing a deal use scope-calculator; this is account research, not contract scoping.
---

# Research Account

Given a named prospect, qualify it against ObservePoint's ICP, surface dated and sourced "why now"
triggers, build a deep dossier with real sourced contacts, score it deterministically, and render a
themed PDF (self-contained HTML fallback if no PDF engine is present).

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
   **Tool fence:** research and the tag/CMP scan use ONLY `detect_cmp` (ObservePoint MCP),
   `WebSearch`, and `WebFetch`. Do NOT use Playwright, Claude-in-Chrome, or any headless-browser /
   page-rendering / scraping tool. If a homepage fetch is JS-blocked (403/empty), treat the negative
   as INCONCLUSIVE and rely on web-signal research — never escalate to a browser.

3. **`--deep-scan` only:** if the rep asked for it and a relevant Site Census exists, call
   `size_site_census` to measure `webScale` (real page count, multi-domain/SPA complexity); put the
   result in `scan.site_census`. Skip silently if unavailable.
   **webScale honesty:** when `--deep-scan` did NOT run, `webScale` is *estimated from web signal, not
   measured* — say so in the `fit` evidence string and in the chat summary rather than presenting it
   identically to the measured criteria, and nudge "run --deep-scan for a measured page count."

4. **Research (WebSearch/WebFetch)** following the two reference prompts:
   - Classify each of the 6 ICP `fit` criteria (`met` true/false + short `evidence`), folding in the
     scan findings (CMP → `privacyConsentSurface`; tags → `tagPixelDensity`; census → `webScale`).
   - Find dated, **sourced** why-now triggers, each tagged with the single best `scoreKey` from
     `scoring-config.json`. Every trigger needs a real `sourceUrl` and a genuine web-tracking nexus.
     An empty trigger list is a valid, honest result — do not stretch (no BIPA, generic breaches,
     antitrust, product-safety).
   - **Trigger-recall checklist (REQUIRED — search EACH category explicitly).** The known failure
     mode is *missed* triggers, not bad math (a real run scored HID Global 65 because it missed a
     2025 M&A trigger that should have lifted it). Work through every category below with its own
     `WebSearch`; an empty category is a valid, honest result, but you must have CHECKED it and you
     must report which categories you checked and which returned nothing (see step 8):
       1. **Pixel / wiretap litigation** — PACER / CIPA (Cal. Penal Code 631) / state wiretap acts,
          ClassAction.org, Law360. (scoreKeys: `pixelWiretapSuit`, `sessionReplaySuit`, `demandLetter`)
       2. **VPPA / video-tracking** — Video Privacy Protection Act / Meta-Pixel video suits. (`vppaSuit`)
       3. **HHS OCR healthcare tracking** — OCR tracking-tech bulletin and patient-portal-pixel
          enforcement. (`ocrHealthcare`)
       4. **FTC / CPPA / state-AG enforcement** — actions or consent orders on tracking, consent, or
          data sharing. (`enforcementAction`)
       5. **M&A / acquisitions / re-platforms** — company newsroom + SEC 8-K / 10-K (including
          litigation reserves and new tracking-heavy surfaces). (`siteOrMerger`)
       6. **Privacy / analytics leadership changes + governance hiring** — new CPO / GC / VP MarTech /
          VP Analytics, and open privacy/analytics-governance roles. (`leadershipChange`,
          `governanceHiring`)
       7. **Breaches with a client-side / script nexus** — Magecart, web-skimming, rogue/hijacked tag
          (NOT a generic stolen-database breach). (`breachIncident`)
   - Write the dossier fields (overview, pain hypotheses, competitor intel, tech-stack notes, best
     opening angle = INTERNAL strategy, research sources).
   - Source **2–5 real, currently-employed** contacts with the fields in `research-and-contacts.md`.
     **Never fabricate a person or source** — if you can't verify someone, set `sourceVerified:false`
     and the dossier flags them held back.

5. **Write the classification JSON** (`/tmp/<slug>-classification.json`) with the shape in the schema
   block below (`account`, `domain`, `prepared_by`, `date`, `scan{}`, `fit[]`, `triggers[]`,
   `rationale`, `research{}`, `contacts[]`).

   **Classification contract (the scripts consume this file — get the field names exactly right; the
   wrong key silently scores zero).** Verify the `key` values against `references/scoring-config.json`:

   ```jsonc
   {
     "account": "Acme Health",                  // company name
     "domain": "acmehealth.com",
     "prepared_by": "Rep Name",
     "date": "2026-06-14",                       // YYYY-MM-DD; also the default scoring as-of
     "scan": {                                   // from step 2/3 (omit fields you didn't measure)
       "cmp": "OneTrust", "cmp_supported": true,
       "tags": ["Google Tag Manager", "GA4", "Meta Pixel"],
       "site_census": null                       // page count only if --deep-scan ran (see G)
     },
     "fit": [                                     // one entry per ICP criterion you assessed
       {
         "key": "privacyConsentSurface",         // MUST be one of the scoring-config fit keys:
                                                  //   privacyConsentSurface | regulatoryExposure |
                                                  //   tagPixelDensity | webScale | targetVertical |
                                                  //   analyticsAccuracy
                                                  // score_account.py matches on f.get("key") — a
                                                  // mislabeled or missing key scores 0 for that line.
         "met": true,                            // bool
         "evidence": "OneTrust CMP confirmed via ObservePoint scan."
       }
       // ... repeat for the other criteria
     ],
     "triggers": [                               // each dated, sourced, web-tracking-nexus event
       {
         "description": "CIPA class action over tracking pixels.",
         "category": "litigation",               // coarse display tag: litigation | enforcement |
                                                  //   incident | leadership | hiring | earnings |
                                                  //   settlement | other
         "date": "2026-01-16",                   // YYYY-MM-DD or YYYY-MM (or YYYY); drives recency decay
         "sourceUrl": "https://example.com/cipa",
         "scoreKey": "pixelWiretapSuit"          // MUST be one of the scoring-config whyNow keys:
                                                  //   pixelWiretapSuit | vppaSuit | ocrHealthcare |
                                                  //   enforcementAction | sessionReplaySuit |
                                                  //   breachIncident | settlement | demandLetter |
                                                  //   complianceDeadline | leadershipChange |
                                                  //   governanceHiring | siteOrMerger
                                                  // an unknown scoreKey keeps the trigger but scores 0.
       }
     ],
     "rationale": "Strong privacy fit with active CIPA exposure.",
     "research": {                               // see references/research-and-contacts.md
       "companyOverview": "...", "keyTriggers": ["..."], "painHypotheses": ["..."],
       "competitorIntel": "...", "techStackNotes": "...",
       "bestOpeningAngle": "...",                // INTERNAL strategy, never prospect-facing copy
       "researchSources": ["https://..."]
     },
     "contacts": [                               // 2–5 real people; never fabricate (see step 4)
       {
         "name": "Dana Rivera", "title": "VP, Privacy", "linkedin": "https://...",
         "sourceVerified": true,                 // true only if a public source confirms current title
         "sourceUrl": "https://...",             // required when sourceVerified; else the dossier holds them back
         "personalizationHook": "...", "toneGuidance": "...", "avoid": "..."
       }
     ]
   }
   ```

> **Interpreter:** invoke the scripts with a Python that has the plugin deps (see the repo's
> requirements files); on a fresh machine prefer `/opt/homebrew/bin/python3`. If a script errors with
> `ModuleNotFoundError`, install the deps first.

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
   `mkdir -p` first, never a temp dir. **Report the EXACT path the script printed** — when no PDF
   engine (Chrome/weasyprint) is present the script falls back to writing `<Company> - research
   dossier.html` instead, and prints that `.html` path.

8. **Summarize in chat:** final score (state it as `fit <fitScore>/100 · why-now <whyNowScore>`, not a
   bare combined number — the why-now component is an uncapped additive sum), QUALIFIED/NOT, dominant
   fit angle, the top trigger, number of sourced vs held-back contacts, and **the EXACT path the
   script printed**. If that path ends in `.html`, add: "no PDF engine found — delivered HTML; open and
   Print-to-PDF, or install Chrome/weasyprint."
   - **Trigger-recall report (required):** state which of the 7 trigger categories (step 4) you
     checked and which returned nothing. An empty category is fine, but the summary must show it was
     checked, not skipped.
   - **webScale honesty:** if `--deep-scan` did NOT run, say webScale is *estimated from web signal,
     not measured*, and add the nudge: "run --deep-scan for a measured page count." Do not present an
     estimated webScale identically to the measured criteria.

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
