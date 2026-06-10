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
   previously-seen names, appends new ones to the log, and prints the ranked list.

6. **Summarize in chat:** the ranked list (name, trigger, points, date, reason, source link), which
   territory/verticals were used, and how many were excluded as previously seen. Then **offer**:
   (a) the spreadsheet export, (b) a research-account run on the top pick.

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
