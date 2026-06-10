# Spec: `find-accounts` skill (territory discovery)

**Plugin:** `observepoint-revenue` (sibling of `scope-calculator`, `research-account`,
`owned-properties`).
**Status:** approved design. **Date:** 2026-06-09.

---

## 1. Goal & intent

NERD's Stage-0 Discovery, ported: proactively FIND new in-territory companies that match
ObservePoint's ICP and have a strong, *current* reason to be contacted — and that are not already in
the rep's pipeline. Discovery does **not** deep-research; it surfaces qualified candidates (name,
one-line why-now reason, trigger category, real source URL) that then feed `research-account`.

**Inputs:** requested count (default **5**, NERD's default); optional per-run territory override
("just healthcare this time"); optional rep-supplied pipeline/exclusion list (pasted or a file);
optional "include previously seen" / "refresh" request.

**Success:** a ranked list of strong, in-territory, non-duplicate candidates — every one with a real
source URL and a trigger category from the shared scoring config. Fewer than requested is a valid,
honest result; **never pad with weak fits** (NERD rule, kept verbatim).

---

## 2. Architecture & data flow

Same pattern as the rest of the plugin — **Claude gathers and judges → a deterministic script does
the mechanics** (dedup, ranking math, log state, rendering). No LLM math, no LLM-maintained state.

1. **Territory profile (Claude).** Read `~/Documents/ObservePoint Revenue/territory.md`. If missing,
   ask the rep (region(s) + verticals, defaulting verticals to the config's `targetVerticals`) and
   write it. A per-run override adjusts this run only — it never overwrites the file. Territory is a
   **hard boundary**: when in doubt whether a company is in-territory, leave it out.

2. **Exclusion set (Claude assembles, judgment-level).** Union of:
   - **auto:** subfolder names under `~/Documents/ObservePoint Revenue/Account Research/` — accounts
     already researched;
   - **rep-supplied:** any pasted/pointed-to pipeline list (e.g. a Salesforce export);
   - plus the **seen-log**, which the *script* enforces mechanically (§4).
   Judgment rule: also exclude obvious duplicates and subsidiaries of excluded names.

3. **Discovery sweep (Claude)** per `references/discovery-sources.md` (ported from NERD
   `prompts/discovery.md`): litigation trackers (ClassAction.org, Top Class Actions, Law360,
   law-firm privacy-litigation reports, PACER coverage), FTC / HHS OCR / CPPA / state-AG enforcement
   pages, breach/incident news, privacy-compliance leadership hires and governance job postings.
   Public sources only. Quick ICP sanity per candidate: large enterprise, complex web presence,
   target vertical. Each candidate gets a `triggerKey` that **must exist** in research-account's
   `scoring-config.json` (single source of truth — the file is *passed by path*, never copied).

4. **Rank & log — `rank_candidates.py`** (deterministic): validates, drops previously-seen names,
   ranks by trigger weight × recency decay (identical math to `score_account.py`), appends new names
   to the seen-log, prints the chat-ready ranked list, and writes the optional `.xlsx` radar only on
   flag.

5. **Summarize in chat** (ranked list + how many were excluded as previously seen) → **offer the
   spreadsheet export** (chat-first per design decision; `.xlsx` only on request) → offer to run
   `research-account` on the top pick.

---

## 3. Components & boundaries

| Component | Responsibility | Depends on |
|---|---|---|
| `SKILL.md` | Orchestrates: territory profile → exclusions → web sweep → candidates JSON → `rank_candidates.py` → summarize/offer export. Owns the territory-boundary and trigger-classification judgment. | `WebSearch`, `WebFetch`, the script |
| `scripts/rank_candidates.py` | Validate candidates; seen-log dedup + append; rank by points × recency decay; print chat table; optional `.xlsx` radar. No LLM, no network. | `openpyxl` (only when `--xlsx`) |
| `references/discovery-sources.md` | The sweep playbook (sources, trigger taxonomy pointers, territory/no-padding/no-fabrication rules). | — |
| *(shared)* `research-account/references/scoring-config.json` | Trigger taxonomy (`whyNow` keys/points), `targetVerticals`, `recency` constants. Read-only consumer. | — |

---

## 4. Data contracts

### Candidates JSON (Claude assembles → script input), e.g. `/tmp/discovery-candidates.json`

```json
{
  "territory": {"region": "US West", "verticals": ["healthcare", "retail & e-commerce"],
                 "override": null},
  "prepared_by": "Jarrod Wilbur",
  "date": "2026-06-09",
  "requested": 5,
  "candidates": [
    {"name": "Example Health System", "domain": "examplehealth.org",
     "vertical": "healthcare",
     "reason": "Named in a May 2026 CIPA class action over Meta Pixel on its patient portal.",
     "triggerKey": "pixelWiretapSuit", "triggerDate": "2026-05-12",
     "sourceUrl": "https://www.classaction.org/..."}
  ]
}
```

- `triggerKey` ∈ the config's `whyNow` keys — an unknown key is a **hard error** (prevents invented
  categories). `sourceUrl` non-empty — missing is a **hard error** (no unsourced candidates).
- `domain` optional (fill when obvious from the source; research-account resolves it anyway).
- `triggerDate` optional: undated triggers get the same 0.6 factor research-account uses.

### CLI

```
rank_candidates.py <candidates.json> <scoring-config.json>
                   [--seen <seen.json>] [--include-seen] [--xlsx <out.xlsx>]
```

- `--seen`: path to the seen-log. Missing/corrupt file ⇒ treated as empty and recreated.
- Default: previously-seen names are **dropped** from output (counted in a stdout note) and not
  re-appended; new names are appended with `firstSeen` = the candidates file's `date`.
- `--include-seen`: seen names stay in the ranked output, annotated with their `firstSeen` date; the
  log is not re-modified for them. (This is the "refresh" path.)
- `--xlsx`: write the radar workbook; **without the flag no file is written** (chat-first).
- stdout: ranked table (rank, name, trigger label, effective points, trigger date, reason, source
  URL) + the excluded-as-seen count. Exit non-zero with a clear message on validation errors.

### Seen-log (`seen-candidates.json`)

```json
{"candidates": [
  {"name": "Example Health System", "firstSeen": "2026-06-09",
   "triggerKey": "pixelWiretapSuit", "sourceUrl": "https://..."}
]}
```

Name matching is normalized: lowercase, drop a leading standalone "the" article, strip all
non-alphanumerics ("The Example Health-System, Inc." ≡ "example health system inc"; "Theranos"
stays intact).

### Ranking math (parity with research-account)

`effectivePoints = round_half_up(whyNow[triggerKey].points × recency_factor(triggerDate))` using the
**same** decay as `score_account.py`: full strength ≤ `fullStrengthMonths` (6), linear decay to a
0.1 floor at `zeroStrengthMonths` (24), undated 0.6, 30-day months, JS-style half-up rounding,
`as_of` = the candidates file's `date` (not the system clock — reproducible). The function is
reimplemented locally (no cross-skill import) with a **parity test** comparing both implementations
across a grid of dates. Sort: effective points desc, tie-break newer `triggerDate` first (undated
last among ties).

---

## 5. Outputs

- **Chat (always):** ranked candidates — name, trigger label, effective points, date, one-line
  reason, source link; the previously-seen exclusion count; a closing offer to (a) export the
  spreadsheet, (b) run research-account on the top pick.
- **Optional `.xlsx` radar** (only when the rep says yes):
  `~/Documents/ObservePoint Revenue/Account Discovery/<YYYY-MM-DD> - discovery radar.xlsx`
  (rep override honored; `mkdir -p` first). One sheet, columns:
  **Rank | Company | Vertical | Trigger | Trigger date | Why now | Source | Pursue? | Notes** —
  Source is a clickable hyperlink (same explicit `Font(color="0563C1", underline="single")`
  convention as build_inventory), **Pursue?/Notes empty and fillable**, dark `1E1E1E` header row,
  per-header column widths.
- **Seen-log:** `~/Documents/ObservePoint Revenue/Account Discovery/seen-candidates.json`
  (script-maintained state, not a deliverable).
- **Territory profile:** `~/Documents/ObservePoint Revenue/territory.md` (rep-editable markdown:
  Region(s), Verticals, Notes).

---

## 6. Guardrails (non-negotiable)

- **Territory is a hard boundary.** A great-fit company outside the territory is left out — it
  belongs to a different AE. When in doubt, leave it out.
- **Never pad.** Fewer than requested, stated plainly, beats weak fits.
- **Every candidate carries a real source URL** for its trigger. No fabricated companies, triggers,
  or sources. The script hard-errors on missing sources and unknown trigger keys.
- **Web-tracking nexus required** — same trigger discipline as research-account (no BIPA-only,
  generic breach, antitrust, or product-safety stretches).
- **No duplicates/subsidiaries** of pipeline, already-researched, or seen accounts.
- Discovery output is **internal** prospecting work product; outreach copy is a separate, governed
  step (sequence-contacts, future).

---

## 7. Out of scope (v1)

Auto-running research-account on candidates (the rep picks; the prospect-orchestrator backlog item
chains stages later), contact-level work, Salesforce sync (manual paste stands in), scheduled/
recurring sweeps, and any paid data sources.

---

## 8. Cost control

- The sweep is bounded: aim for ~2× the requested count of raw leads before filtering, stop early
  when the count is met with strong candidates; log anything intentionally skipped (no silent
  truncation).
- Candidates are dozens of small records — no sidecar files needed (unlike owned-properties' host
  dumps). The seen-log stays apex-level small.
- `openpyxl` imported lazily (only on `--xlsx`) so the default chat-first path has no dependency
  surface.

---

## 9. Testing & housekeeping

- **`test_rank_candidates.py`** (offline, ~12 tests): ranking order by effective points; decay
  **parity test** vs `score_account.recency_factor` across dated/undated/old triggers; half-up
  rounding; tie-break by recency; seen-log dedup (normalized name match); `--include-seen`
  annotation + log untouched; log append with `firstSeen`; missing/corrupt log recreated; unknown
  `triggerKey` hard error; missing `sourceUrl` hard error; `--xlsx` writes the workbook with the
  exact column set, hyperlink font, fillable Pursue?/Notes; **no file written without `--xlsx`**;
  empty candidates list is valid (prints "0 candidates", exit 0).
- **`SKILL.md`** via the writing-skills TDD loop; trigger-only frontmatter (CSO-compliant); red-flags
  table (out-of-territory great fit → leave out; padding; fabricated sources; subsidiaries counted
  as new; non-nexus triggers; trigger categories not in the config).
- **Version:** bump `observepoint-revenue` `0.8.1 → 0.9.0` (new capability); add find-accounts to
  the plugin description; update `docs/ROADMAP.md` (move find-accounts to Recently shipped; fix the
  stale v0.8.0/domains.txt header note while in the file).
- No customer/prospect data committed (deliverables live under `~/Documents`, outside the repo).
