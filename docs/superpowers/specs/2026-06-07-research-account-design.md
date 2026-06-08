# Spec: `research-account` skill (porting NERD's research engine into the plugin)

**Plugin:** `observepoint-revenue` (sibling of `scope-calculator`, `derive-page-count`, `size-and-price`).
**Status:** approved design. **Date:** 2026-06-07.
**Source IP:** `~/Documents/NERD/nerd` — the local-first AE research tool. This spec ports its
**research brain** (prompts + deterministic scoring + schemas) into a single Claude Code skill.

---

## 1. Goal & intent

Let a revenue rep research a named prospect **through Claude directly** instead of through the NERD
app. One command produces a qualified, scored, evidence-backed account dossier as a polished,
ObservePoint-themed `.docx`.

This is the **research-first** slice of NERD's 5-stage pipeline (Discovery → Trigger&Fit →
Research+Contacts → Enrich → Sequencer). We build the middle that carries the value:
**Trigger & Fit + Research + Contacts**. Discovery, enrichment, sequencing/sending, and Salesforce
sync are explicitly out of scope for v1 (see §7), with clean seams left to add them later.

### Why this ports cheaply (the reusability finding)
- The **4 NERD prompts** and the **scoring model** are pure, well-developed IP that lift in almost
  verbatim. The tone-governor / strategy-vs-copy discipline lifts in as a dossier convention.
- NERD's hardest-built component — `localClaude.ts` (the Claude Agent SDK bridge, JSON-only-output
  hack, usage metering, abort plumbing) — **is not needed**. A Claude Code skill *is* Claude with
  `WebSearch`/`WebFetch`. That complexity evaporates.
- New capability NERD lacked: the connected **ObservePoint MCP** can *measure* a fit signal
  (CMP presence) instead of guessing it.

---

## 2. Architecture & data flow

Mirrors `scope-calculator`'s proven three-part pattern: **Claude gathers evidence → a deterministic
script computes → a builder renders**. The model classifies; code does the math (reproducible,
tunable).

1. **Invoke:** `research-account <Company>` with optional `domain` and optional `--deep-scan`.
2. **Claude (the SKILL body):**
   1. Resolve the prospect's primary domain (from input, else a quick web lookup).
   2. **Light OP scan (default):** call `detect_cmp({url: <homepage>})`. Record the CMP vendor (or
      "none detected") and whether ObservePoint's auto-opt-out supports it. This is **measured**
      evidence for the highest-weight fit criterion, `privacyConsentSurface` (25 pts).
      - **Caveat baked into scoring guidance:** `detect_cmp` is a server-side fetch (no JS), so a
        *positive* detection is strong evidence, but a *negative* is NOT proof of absence — fall
        back to the public-web signal and mark the evidence "unconfirmed," never assert "no CMP."
   3. **`--deep-scan` (opt-in):** additionally pull richer measured signals if available (e.g. a
      tag/pixel inventory or Site Census sizing) to harden `tagPixelDensity` / `webScale`. v1 keeps
      this best-effort and dependency-aware: it only uses data reachable without standing up new
      customer infrastructure; if unavailable, it degrades silently to web research. (Full deep-scan
      wiring can be hardened in a later pass; the light path is the guaranteed default.)
   4. **Web research** per the ported prompts (`trigger-and-fit.md`, `research-and-contacts.md`):
      - Classify each of the 6 ICP fit criteria as `met` true/false with a short `evidence` string.
      - Find dated, **sourced** why-now triggers, each tagged with the single best `scoreKey` and a
        coarse display `category`. Every trigger needs a real, clickable `sourceUrl` and a genuine
        web-tracking nexus (empty list is a valid, honest result).
      - Write the dossier: company overview, pain hypotheses, competitor intel, tech-stack notes,
        **best opening angle**, research sources.
      - Source **2–5 real, currently-employed** contacts: name, title, LinkedIn, `sourceVerified`,
        `sourceUrl`, `personalizationHook`, `toneGuidance`, `avoid`. Enforce NERD's
        **no-placeholder** rule and the per-contact source-evidence rule.
   5. Fold the CMP scan result into the `privacyConsentSurface` classification evidence
      (measured > guessed).
   6. Write a **classification JSON** to a temp path, matching the schema in §4.
3. **`score_account.py classification.json [scored.json]`** — deterministic scoring (port of NERD
   `scoring.ts` `computeFit` + recency decay), reading weights from bundled `scoring-config.json`:
   - `fitScore` = sum of met-criteria points, capped at 100.
   - `whyNowScore` = sum over triggers of `points × recencyFactor(date)` (full strength ≤6mo, linear
     decay to a 0.1 floor by 24mo; undated → 0.6).
   - `finalScore = fitScore + whyNowScore`.
   - `qualified = fitScore ≥ fitGate(55) OR whyNowScore ≥ triggerOverride(30)`.
   - `lowFitHighTrigger = qualified && !byFit && byTrigger` (a badge).
   - Emits `scored.json` with full `fitBreakdown` / `whyNowBreakdown`.
4. **`build_dossier.py scored.json out.docx`** — themed `.docx` (theming primitives mirrored from
   `build_proposal.py`). Sections in §5.
5. **Chat summary:** verdict line (final score, qualified?, dominant fit angle, top trigger,
   # sourced contacts, # held-back) + the docx path.

---

## 3. Components & boundaries

| Component | Responsibility | Depends on |
|---|---|---|
| `SKILL.md` | Orchestrates: scan → research → write classification JSON → run both scripts → summarize. Carries the ICP/trigger/contact instructions (or points to references). | `WebSearch`, `WebFetch`, `detect_cmp`, the two scripts |
| `references/trigger-and-fit.md` | Ported NERD Stage-1 prompt: what OP does, 6 ICP criteria (keys), 12 why-now trigger `scoreKey`s, sources, the web-tracking-nexus rule. | — |
| `references/research-and-contacts.md` | Ported NERD Stage-2/3 prompt: research protocol, CIPA framing as internal strategy, contact rules (real-only, source-verified, no placeholders). | — |
| `references/scoring-config.json` | Ported NERD `config.json`: `fitGate`, `triggerOverride`, `recency`, `fit{}`, `whyNow{}`, `targetVerticals`, `personaPriorityTitles`, `triggerSources`. Single source of truth for weights. | — |
| `references/icp-and-tone.md` | Condensed: OP's four buying centers, privacy-weighted emphasis, strategy-vs-copy boundary. | — |
| `scripts/score_account.py` | Deterministic scoring + qualify decision from a classification JSON. No LLM, no network. | `scoring-config.json` |
| `scripts/build_dossier.py` | Render `scored.json` → themed `.docx`. No LLM, no network. | `python-docx`, `assets/op-logo.png` |
| `assets/op-logo.png` | Brand logo for the header (copied from `scope-calculator/assets`). | — |

Each script is independently testable: pure function of its JSON input.

---

## 4. Classification JSON contract (the model's output → `score_account.py` input)

Ported from NERD `schemas.ts` (`FIT_TOOL` + `RESEARCH_TOOL`), flattened into one object:

```json
{
  "account": "Arthur J. Gallagher",
  "domain": "ajg.com",
  "prepared_by": "Jarrod Wilbur",
  "date": "2026-06-07",
  "scan": { "cmp": "OneTrust", "cmp_supported": true, "method": "observepoint detect_cmp",
            "confirmed": true },
  "fit": [
    { "key": "privacyConsentSurface", "met": true,
      "evidence": "OneTrust CMP detected (confirmed via ObservePoint scan)." },
    { "key": "regulatoryExposure", "met": true, "evidence": "..." }
    /* one entry per criterion in scoring-config.fit */
  ],
  "triggers": [
    { "description": "...", "date": "2026-01-16", "sourceUrl": "https://...",
      "category": "litigation", "scoreKey": "pixelWiretapSuit" }
  ],
  "rationale": "Dominant angle: privacy/consent. Strongest why-now: active CIPA suit.",
  "research": {
    "companyOverview": "...", "keyTriggers": ["..."], "painHypotheses": ["...","..."],
    "competitorIntel": "...", "techStackNotes": "...",
    "bestOpeningAngle": "INTERNAL strategy, not prospect copy: ...",
    "researchSources": ["https://...", "https://..."]
  },
  "contacts": [
    { "name": "...", "title": "...", "linkedin": "https://...",
      "sourceVerified": true, "sourceUrl": "https://...",
      "personalizationHook": "...", "toneGuidance": "...", "avoid": "..." }
  ]
}
```

`scored.json` = this object plus a `score` block: `{ fitScore, whyNowScore, finalScore, qualified,
lowFitHighTrigger, fitBreakdown[], whyNowBreakdown[] }`.

**Keys are config-driven.** The SKILL injects the valid `fit` keys and `whyNow` scoreKeys from
`scoring-config.json` into the model's instructions (as NERD's `stages.ts` does) so the
classification lines up with what the script scores. Unknown scoreKeys are shown but score 0.

---

## 5. Dossier `.docx` sections

1. **Header** — OP logo + "Account Research Dossier — {Company}", prepared-by/date.
2. **Verdict band** — `finalScore`, `fitScore`, `whyNowScore`, a **QUALIFIED / NOT QUALIFIED** badge,
   and a `lowFitHighTrigger` note when set. Brand-yellow accent.
3. **Why now** — triggers table: description, date, category, source URL, points (after decay).
   Sorted by points. The persuasive heart of the dossier.
4. **ICP fit** — breakdown table: criterion label, met?, points, evidence. Privacy criteria first.
5. **Account overview** — companyOverview, pain hypotheses (2–3), competitor intel, tech-stack notes.
6. **Best opening angle** — clearly labeled **"Internal strategy — not prospect-facing copy"** (the
   strategy-vs-copy boundary; sharp legal framing allowed here, never in outreach).
7. **Contacts** — roster table: name, title, LinkedIn, **Verified?** (source_verified), hook, tone,
   avoid. Unverified contacts get a visible "⚠ held back — verify before outreach" note (the publish
   gate, surfaced not hidden).
8. **Sources & method** — research source URLs; a short methodology note (web research + ObservePoint
   CMP scan; scoring is deterministic from config weights).

No customer-strippable INTERNAL section is needed (this is an internal AE artifact, not a
customer-facing proposal), but the opening-angle section keeps the internal-strategy labeling.

---

## 6. Preserved NERD properties (non-negotiable)

- **Deterministic scoring split** — model classifies, `score_account.py` computes. Reproducible;
  tuning is a `scoring-config.json` edit, not a code change.
- **Real contacts only** — no fabricated people, no placeholder patterns (`[Name]`, `TBD`,
  `{{name}}`, generic role labels, empty required fields). Any contact lacking `sourceVerified:true`
  or a non-empty `sourceUrl` is **held back** (flagged in the docx), never silently shipped.
- **Web-tracking nexus** for every trigger; an empty trigger list is a valid, honest result. No
  stretching to BIPA / generic breaches / antitrust / product-safety.
- **Strategy vs. copy boundary** — the sharp legal angle is internal-only; prospect-facing outreach
  copy is the future `sequence-contacts` skill's job (where the tone governor lives).
- **Privacy-weighted ICP** — privacy/consent is the dominant, durable angle; analytics is a lighter
  signal. (Encoded in the config point weights; do not flatten.)
- **No fabricated `detect_cmp` conclusions** — positive = evidence; negative ≠ "no CMP."

---

## 7. Out of scope (v1) — and the seams left for it

| Deferred | Why | Seam left |
|---|---|---|
| Discovery / territory | Needs territory source (was live Salesforce); research-first targets a named account. | `find-accounts` sibling skill; territory becomes a param/config. |
| Contact enrichment (email/phone) | Stubbed in NERD; needs a ZoomInfo/Apollo key. | Dossier emits named+sourced+LinkedIn contacts; an enrich step can fill `enrichment{}` later. |
| Sequencing copy + sending + reply-watch | Stateful background jobs; not a skill's job. | `sequence-contacts` sibling consumes `scored.json`; could drop Gmail drafts via the connected Gmail MCP. |
| Salesforce overlap-guard / write-back | No SF connector attached here. | Out; rep imports the dossier manually. |
| Review queue / persistence | The Electron app's job. | Rep reviews the docx inline; artifacts are files. |

A future `prospect` orchestrator can chain `find-accounts → research-account → sequence-contacts`,
mirroring how `scope-calculator` wraps its sub-skills.

---

## 8. Testing & housekeeping

- **`test_score_account.py`** — deterministic. Seed fixtures from NERD `agents/src/fixtures.ts`.
  Assert: fit sum + 100 cap; recency decay (≤6mo=full, ≥24mo=0.1 floor, undated=0.6); qualify by
  fit-gate; qualify by trigger-override with sub-gate fit → `lowFitHighTrigger`; unknown scoreKey
  scores 0 but still appears; empty triggers → not qualified unless fit≥gate.
- **`test_build_dossier.py`** — mirrors `test_build_proposal.py`: renders all §5 sections; the
  QUALIFIED badge reflects the input; an unverified contact shows the held-back note; the opening
  angle carries the internal-strategy label; CLI writes a `.docx`.
- **`SKILL.md`** authored via the writing-skills TDD loop (RED baseline subagent run → GREEN);
  frontmatter description is trigger-only (CSO-compliant), consistent with the other three skills.
- **Version:** bump `observepoint-revenue` `0.4.2 → 0.5.0` (new capability).
- **Theming:** mirror the ~40 lines of brand primitives (`FONT`, colors, `_run`/`_int`/`_usd`/table
  helpers) into `build_dossier.py`; do **not** refactor the existing scope-calculator scripts (smallest
  blast radius). Note a future shared `_theme.py` extraction as optional, not now.
- **No customer data committed** (consistent with the gitignore'd `sample-output/`).

---

## 9. Port map (NERD → skill) — for the implementation plan

| NERD source | Becomes |
|---|---|
| `control-plane/config/prompts/trigger-and-fit.md` | `references/trigger-and-fit.md` (light edits: skill context, OP-scan note) |
| `control-plane/config/prompts/research.md` | `references/research-and-contacts.md` |
| `control-plane/config/config.json` (scoring, verticals, persona titles, triggerSources) | `references/scoring-config.json` |
| `agents/src/scoring.ts` (`computeFit`, `recencyFactor`, `DEFAULT_SCORING`) | `scripts/score_account.py` |
| `agents/src/schemas.ts` (`FIT_TOOL`, `RESEARCH_TOOL`) | the §4 classification contract + script validation |
| `agents/src/fixtures.ts` | test fixtures for `test_score_account.py` |
| `agents/src/localClaude.ts`, `client.ts`, `orchestrator.ts` | **dropped** — replaced by the skill + Claude's native web tools |
| Discovery / sequencer / reply / enrich / Gmail / Salesforce | **deferred** (see §7) |
```
