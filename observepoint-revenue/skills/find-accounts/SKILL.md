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

**Tool fence:** The web sweep uses `WebSearch` (and `WebFetch` to read a specific result) ONLY — no
browser / Playwright / Claude-in-Chrome or any page-rendering/scraping tool. Territory and the
overlap-guard use the **Salesforce MCP read tools** (`getUserInfo`, `soqlQuery`, `find`) — read-only;
never `create`/`update`. Run the canonical queries from
`${CLAUDE_PLUGIN_ROOT}/skills/salesforce-core/references/salesforce-org.md`.

Set `SKILL=${CLAUDE_PLUGIN_ROOT}/skills/find-accounts` and
`SCORING=${CLAUDE_PLUGIN_ROOT}/skills/research-account/references/scoring-config.json`.
Read first: `$SKILL/references/discovery-sources.md` (sources, hard rules) and the `whyNow` keys +
`targetVerticals` in `$SCORING`.

## Inputs

- **Count** (default 5). **Territory override** (optional, this run only).
- **Pipeline list** (optional — pasted names or a file path; all excluded).
- **"Include previously seen" / "refresh"** (optional — re-show seen-log names).

## Workflow

1. **Territory (Salesforce-first).** Resolve the boundary from Salesforce, not a hand-kept file.
   Read `${CLAUDE_PLUGIN_ROOT}/skills/salesforce-core/references/salesforce-org.md` for the queries.

   a. **Identify the target AE/ADM.** Call `getUserInfo`. This is a *hint only* — the SF MCP
      authenticates as whoever connected it, who may not be the human running this. If the connected
      user is an AE/ADM and no target was named, confirm and use them. Otherwise ask whose territory
      to run, and resolve them: `SELECT Id, Name, Email FROM User WHERE Email = :email AND IsActive = true`.

   b. **Pull the territory** (key on the target's actual role — never assume AE≡ADM):
      ```sql
      SELECT Id, Name, Name__c, Segment__c, World_Region__c, Sub_Region__c,
             Country__c, State__c, AE__r.Name, ADM__r.Name, CSM__r.Name
      FROM OP_Territories__c WHERE AE__c = :targetUserId      -- or ADM__c = :targetUserId
      ```
      Save the result to `/tmp/territory-soql.json` and normalize it:
      ```bash
      python3 "$SKILL/scripts/resolve_territory.py" /tmp/territory-soql.json > /tmp/territory-boundary.json
      ```
      The boundary gives `regions / sub_regions / countries / states / segments` (the geographic +
      segment patch) and `territory_ids` (used by the overlap-guard). **Verticals are NOT in SF** —
      take them from the `targetVerticals` list in `$SCORING` (+ any per-run narrowing the rep asks
      for). A per-run override adjusts THIS run only.

   c. **No territory found** (`territory_ids` empty): the target has no AE/ADM territory. Say so and
      ask for an explicit region + segment (or a different target) — do not guess a boundary.

   **Fallback.** If the Salesforce MCP is unavailable, fall back to
   `~/Documents/ObservePoint Revenue/territory.md` (region + verticals); if that's missing too, ask
   the rep and write it (the legacy `# Territory — <rep name>` format). SF is the source of truth
   when connected; the file is only a cache/override.

2. **Exclusions.** Two layers:
   - **Local** (unchanged): subfolder names under `~/Documents/ObservePoint Revenue/Account Research/`
     (already researched — `ls` it), any rep-supplied pipeline list, and the seen-log (the ranker
     enforces that one). Skip obvious duplicates/subsidiaries of excluded names.
   - **Salesforce overlap-guard** (applied after the sweep, in step 5): the model matches the swept
     candidates against SF and `classify_overlap.py` enforces the policy — **hard-exclude** anything
     in the target's territory or owned by the target (this catches named accounts in other
     territories) and any `Type = Customer`; **flag but keep** companies already in SF under another
     rep or as Prospect/Previous Customer/Defunct, annotated `already in SF — owner: X, type: Y`.

3. **Sweep** (`WebSearch`/`WebFetch`) per `$SKILL/references/discovery-sources.md`. Build each
   candidate: `name`, `domain` (when obvious), `vertical`, one-line `reason`, `triggerKey` (must be
   a `whyNow` key in `$SCORING`), `triggerDate` (YYYY-MM-DD if known), real `sourceUrl`. Fewer than
   requested is a valid result — say so; never pad.

4. **Assemble** `/tmp/discovery-candidates.json`: `territory{region,verticals,override}`,
   `prepared_by`, `date` (today), `requested`, `candidates[]`.

5. **Rank:**

   **First, the Salesforce overlap-guard.** Collect the candidate domains and match them against SF
   (domain-first; `find` by name for any without a website match), per the account-match query in
   `salesforce-org.md`. Save the result to `/tmp/sf-account-matches.json`, then:

   ```bash
   python3 "$SKILL/scripts/classify_overlap.py" /tmp/discovery-candidates.json \
     /tmp/sf-account-matches.json --territory /tmp/territory-boundary.json \
     --target-user "<targetUserId>" --out /tmp/discovery-candidates.sf.json
   ```

   It drops hard-excludes, annotates the survivors with `sf_status`, and prints a one-line summary to
   stderr. (`resolve_territory.py` and `classify_overlap.py` are stdlib-only — any `python3` runs them;
   only the ranker below needs openpyxl for the `--xlsx` path, so prefer `/opt/homebrew/bin/python3`
   there.) **Then rank the annotated file** (note: `discovery-candidates.sf.json`, not the raw one):

   ```bash
   python3 "$SKILL/scripts/rank_candidates.py" /tmp/discovery-candidates.sf.json "$SCORING" \
     --seen "$HOME/Documents/ObservePoint Revenue/Account Discovery/seen-candidates.json"
   ```

   Add `--include-seen` only when the rep asked to refresh/re-include. The script drops
   previously-seen names, appends new ones to the log, and prints the ranked list. It also
   deprioritizes and flags off-ICP verticals (`⚠ off-ICP vertical: …`) — it never silently drops
   them, so surface them too, clearly marked. Run the script with a Python that has openpyxl for
   the `--xlsx` path (prefer `/opt/homebrew/bin/python3`). Flagged candidates carry an `already in SF`
   note in chat and an **In SF?** column in the radar — surface them, clearly marked; they are not
   silently dropped.

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
Salesforce *write-back* (read-only today), scheduled sweeps, paid data sources.
