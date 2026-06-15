---
name: find-accounts
description: Use when a revenue or sales rep wants NEW prospects surfaced for their territory — "find me accounts", "who should I be prospecting", "what's new in my territory", "discovery run", "find triggered accounts". Produces a ranked, sourced candidate list (chat-first, optional .xlsx radar) that feeds research-account. For researching a single named company use research-account; this finds the names in the first place.
---

# Find Accounts (Territory Discovery)

Proactively find in-territory, ICP-fit companies with a strong, current reason to be contacted —
not already in the rep's pipeline. Candidates feed research-account; this stage does NOT
deep-research them.

You judge (territory, triggers, evidence); `rank_candidates.py` does the mechanics (validation,
seen-log dedup, ranking with research-account's trigger weights + recency decay).

**Tool fence:** The sweep uses `WebSearch` (and `WebFetch` to read a specific result) ONLY. Do NOT
open a browser / Playwright / Claude-in-Chrome or any page-rendering/scraping tool.

Set `SKILL=${CLAUDE_PLUGIN_ROOT}/skills/find-accounts` and
`SCORING=${CLAUDE_PLUGIN_ROOT}/skills/research-account/references/scoring-config.json`.
Read first: `$SKILL/references/discovery-sources.md` (sources, hard rules) and the `whyNow` keys +
`targetVerticals` in `$SCORING`.

## Inputs

- **Count** (default 5). **Territory override** (optional, this run only).
- **Pipeline list** (optional — pasted names or a file path; all excluded).
- **"Include previously seen" / "refresh"** (optional — re-show seen-log names).

## Workflow

1. **Territory.** Read `~/Documents/ObservePoint Revenue/territory.md`. If missing, ask the rep for
   region(s) + verticals (default verticals: the `targetVerticals` list in `$SCORING`) and write
   the file:

   ```markdown
   # Territory — <rep name>
   - **Region(s):** <e.g. US West>
   - **Verticals:** <comma-separated, or "all target verticals">
   - **Notes:** <segment limits, named exclusions, anything else>
   ```

   A per-run override ("just healthcare this time") adjusts THIS run only — never rewrite the file
   for an override. Territory is a hard boundary: when in doubt, leave the company out.

   **Shared-machine state guard.** This skill reads/writes per-home-dir state under
   `~/Documents/ObservePoint Revenue/`. On a SHARED training laptop that cross-contaminates reps.
   `territory.md` carries a rep name in its `# Territory — <rep name>` header: confirm WHOSE file
   this is, and if the rep running differs from the file's owner, WARN and ASK before using or
   overwriting it (offer a per-run override instead of a rewrite). Likewise the seen-log
   (`Account Discovery/seen-candidates.json`) is per-machine and may hold another rep's history —
   note that out loud so an "already seen" exclusion isn't mistaken for the current rep's own.

2. **Exclusions.** Union of: (a) subfolder names under
   `~/Documents/ObservePoint Revenue/Account Research/` (already researched — `ls` it),
   (b) any rep-supplied pipeline list, (c) the seen-log (the script enforces that one). Also skip
   obvious duplicates/subsidiaries of excluded names.

3. **Sweep** (`WebSearch`/`WebFetch`) per `$SKILL/references/discovery-sources.md`. Build each
   candidate: `name`, `domain` (when obvious), `vertical`, one-line `reason`, `triggerKey` (must be
   a `whyNow` key in `$SCORING`), `triggerDate` (YYYY-MM-DD if known), real `sourceUrl`. Fewer than
   requested is a valid result — say so; never pad.

4. **Assemble** `/tmp/discovery-candidates.json`: `territory{region,verticals,override}`,
   `prepared_by`, `date` (today), `requested`, `candidates[]`.

5. **Rank:**

   ```bash
   python3 "$SKILL/scripts/rank_candidates.py" /tmp/discovery-candidates.json "$SCORING" \
     --seen "$HOME/Documents/ObservePoint Revenue/Account Discovery/seen-candidates.json"
   ```

   Add `--include-seen` only when the rep asked to refresh/re-include. The script drops
   previously-seen names, appends new ones to the log, and prints the ranked list. It also
   deprioritizes and flags off-ICP verticals (`⚠ off-ICP vertical: …`) — it never silently drops
   them, so surface them too, clearly marked. Run the script with a Python that has openpyxl for
   the `--xlsx` path (prefer `/opt/homebrew/bin/python3`).

6. **Summarize in chat:** the ranked list (name, trigger, points, date, reason, source link),
   off-ICP flags carried through, which territory/verticals were used, and how many were excluded
   as previously seen. Then **offer**: (a) the spreadsheet export, (b) a research-account run on the
   top pick.

   **Reconciliation / quiet-territory signal.** The three state locations are distinct, don't
   conflate them: `territory.md` (region + verticals), `Account Research/` subfolders (already-
   researched exclusions), and `Account Discovery/seen-candidates.json` (already-surfaced
   exclusions). When the list comes back thin, surface "territory looks quiet — only N strong leads
   found across M sources swept" so the rep can tell a genuinely quiet territory from a shallow
   sweep (and decide whether to widen the sweep or accept fewer).

7. **Only if the rep wants the export**, rerun step 5 with
   `--xlsx "$HOME/Documents/ObservePoint Revenue/Account Discovery/<YYYY-MM-DD> - discovery radar.xlsx"`
   AND `--include-seen` (step 5 already logged these names — without it the rerun would drop them
   all and write an empty radar). Rep folder override honored; `mkdir -p` first.

## Red flags — stop and fix

| Rationalization | Reality |
|---|---|
| "Great fit, just outside the territory." | Out of territory = out. It belongs to a different AE. When in doubt, leave it out. |
| "Only found 3 strong ones, I'll add 2 weaker." | Never pad. Fewer, stated plainly, is the honest result. |
| "I'm sure there's a lawsuit, I'll cite a likely URL." | Never fabricate a company, trigger, or source URL. Real sources only. |
| "Their subsidiary isn't technically in the pipeline." | Subsidiaries/duplicates of excluded accounts are excluded. |
| "This breach is close enough to web tracking." | Triggers need a web-tracking nexus (no BIPA-only, antitrust, product-safety stretches). |
| "I'll invent a trigger category for this." | `triggerKey` must exist in scoring-config; the script hard-errors otherwise. |

## What this skill does not do (v1)

Deep research (research-account), auto-running research on candidates, contact work, outreach copy,
Salesforce sync, scheduled sweeps, paid data sources.
