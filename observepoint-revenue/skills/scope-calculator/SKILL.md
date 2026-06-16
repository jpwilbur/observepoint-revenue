---
name: scope-calculator
description: Use when a revenue or sales rep needs to scope or price an ObservePoint contract — "scope this account", "how many pages do they need", "how many pages does X have", "size a deal", "price out X", "price a known page count", "build a usage proposal". Derives a defensible page count, sizes annual page-scan usage, prices it against ObservePoint's live pricing, and produces a customer proposal + evidence workbook. Runs the whole job or any single stage. To discover which domains an org owns use owned-properties; to research/qualify a prospect use research-account.
---

# Scope Calculator

The single tool reps use to scope and price an ObservePoint contract. It is **one job in three stages** — run all three (the default) or jump to the stage you need. You orchestrate and judge; the scripts do every calculation and render the deliverables. **Never invent a page count, multiplier, cadence, or price — a guessed number presented as fact is the failure this tool exists to prevent.**

Set `SCRIPTS=${CLAUDE_PLUGIN_ROOT}/skills/scope-calculator/scripts` and `REFS=${CLAUDE_PLUGIN_ROOT}/skills/scope-calculator/references`. Scripts: `compute_scope.py`, `fetch_pricing.py`, `fetch_samples.py`, `check_artifacts.py`, `build_proposal.py`, `build_evidence_appendix.py`. Read the reference for whichever stage you run.

**Interpreter note:** `build_proposal.py` requires `python-docx` and `build_evidence_appendix.py` requires `openpyxl`. Invoke scripts with a Python that has the plugin deps (prefer `/opt/homebrew/bin/python3`). If you hit `ModuleNotFoundError`, install the repo requirements first — do NOT silently skip the deliverable.

## Entry paths

- **Full scope** (default — "scope this account", "price out X"): Stage 1 → 2 → 3.
- **Known page count** ("just price ~50k pages", "what would 50k pages cost"): skip Stage 1; start Stage 2 with the count the rep gives (treat it as `anchor`, with `low`/`high` = the same unless they give a range).
- **Count only** ("how many pages does X have"): run Stage 1 and stop with the `{rollup, per_domain}` result.

## Stage 1 — Derive the page count

**REQUIRED READING before you produce a number:** `$REFS/site-census-methodology.md` (failure modes, MCP tools, range methodology, output contract, Gallagher calibration). Produce a **narrow, defensible range + anchor + confidence** from the internal Site Census crawler — as large as is legitimately defensible, never inflated past customer scrutiny, **never fabricated.**

> **Cold start — "no census found" is a first-class outcome, not a buried branch.** If NO Site Census exists for the account, the flagship "scope this account" **cannot produce a number** — there is nothing to derive from, and fabricating one is the exact failure this tool exists to prevent. The correct move: tell the rep plainly that no census exists, **offer to create + start one** (behind the write gate), and **set expectations** that a fresh crawl takes **hours-to-days**. Then hand off — never block waiting on the crawl; the rep returns when it completes. For a **live demo**, pre-seed a census for the training account ahead of time so the flow has data to run against.

> **Input — owned→scope inbound handoff.** If the rep supplies a **confirmed-domains list** (e.g. from the owned-properties skill), use it to scope/disambiguate the Site Census search (which domains belong to this account) and to **validate per_domain coverage** (every confirmed domain should appear in `per_domain[]` or the tail aggregate).

**Stage-1 checklist (do not skip any of these — even if no spiral is flagged):**
- **Artifact-check tell:** `patterns` ≪ `raw_urls` while the url/path ratio is ~1 (TKO `patterns`=79 vs `raw_urls`=306) — in-path `%22`/doubled-slash junk the spiral gate is blind to. **Path-recursion traps are sneakier still:** they defeat the patterns tell too (`patterns` ≈ `paths` ≈ `urls`, all inflated equally), so the *only* reliable catch is the raw-sample → `check_artifacts.py` gate (step 5). Tell: one domain is an implausible share of `url_total` or implausibly large for the business (Gallagher: stevenson-insurance.com reported 1.71M URLs for a ~150-page agency — 93% of the account, no flag).
- **Incompleteness uplift (push HIGH only):** if `urlsToVisit > 0`, add ≈ `urlsToVisit × (pathFloor / visitedUrls)` to HIGH.
- **Sampling cost rule:** sample every **spiral-flagged** domain, **any host that is an outsized share of `url_total`** (recursion-trap candidates — always sample the single biggest host), plus the **top ~8–10 remaining** by page count (~12–16 grid queries total) — never every domain; the long tail is the aggregate row.
- **Do NOT skip the threshold sweep or the artifact check even if no spiral is flagged.**

1. **Admin safety.** `whoami` → if not in the central census account (default id 32527) `login_as_account` into it. Reads are immediate. For ANY write (create/start/update/delete): state account + plan, get explicit go-ahead, `confirm_account_plan`, act, then `stop_impersonation`. **Impersonation can auto-revert (idle) mid-session.** A census-scoped read that lands back on your own admin account returns an empty success — `totalCount: 0`, HTTP 200 — carrying an "auto-reverted / ran on your admin account" warning, **not** an error. Treat any response with that warning as an **invalid read**: re-assert `login_as_account` and retry — NEVER consume the `0`/empty as real data. Don't fire a long batch of census reads expecting one impersonation to survive the whole batch; re-check between groups.
2. **Find the census.** `list_site_censuses({search:<customer surname/brand>})` (names are `[Rep][Rep] Customer`; if the rep gave a confirmed-domains list, use it to disambiguate). One → proceed. Multiple → disambiguate. None → **cold start** (see the callout above): do NOT invent a number; offer to create + start one (behind the write gate), tell the rep a fresh crawl takes hours-to-days, never block waiting.
3. **Size + sweep.** `size_site_census({censusId})` at default thresholds, then sweep (5000/1.3, 10000/1.5, 20000/2.0). Read per-hostname URLs/paths/spiral flags + the three totals.
4. **Derive the range** per the reference: anchor = spiral-adjusted total; band from the sweep spread; HIGH gets the incompleteness uplift `urlsToVisit × pathFloor/visitedUrls`; clamp to the sanity ceiling; round to ~2 sig figs; assign confidence.
5. **Artifact check — MANDATORY GATE before you quote.** "No spiral flagged" ≠ clean. Two classes of in-path junk inflate URLs and paths equally, so the spiral gate misses both: **(a) `%22`/escaped-quote/doubled-slash artifacts** (TKO: 306 raw → ~80 real, ~4×); **(b) path-recursion traps** — a nav segment re-appended over and over (`/biz/biz/biz/…`), which ALSO defeat the patterns tell (Gallagher: stevenson-insurance.com 1.71M URLs for a ~150-page agency — a silent ~15× that was 93% of the account total). **You MUST run the raw-mode sample through `check_artifacts.py` before quoting** — build the raw query with `python3 "$SCRIPTS/fetch_samples.py" <censusId> <hostname> --raw` (bump `size` to ~50–100 for a firmer rate on suspect hosts), call `op_api_call` with it, `parse_samples` to a `<urls.json>`, then `python3 "$SCRIPTS/check_artifacts.py" <urls.json>`. Act on the verdict:
   - **`inflated` with `recursion_count` dominant** → even the *path* count for that host is junk. **EXCLUDE the host from the anchor** (do NOT substitute paths — unlike a spiral), itemize the discount (`why: "recursion trap — N URLs collapse to ~M real pages"`, M = `collapsed_distinct`), and recommend a corrected re-crawl with recursion/param handling.
   - **`inflated` with `artifact_count` (`%22`) dominant** → quote the clean `patterns` count for that host, never its raw/spiral-adjusted total.
   - **`clean`** → quote as normal. See `$REFS/site-census-methodology.md`.
6. **Emit `{rollup, per_domain[]}`** + the discounted-spiral transparency line. `size_site_census` itemizes only the top ~40 hostnames — on bigger accounts add a single labeled **tail-aggregate row** so `per_domain` sums to the anchor. Pull ~5–6 real sample pages per itemized domain into `url_samples`: build the query with `python3 "$SCRIPTS/fetch_samples.py" <censusId> <hostname>`, call `op_api_call` with it, and parse with `parse_samples` (clean pages, never fabricated, never hand-authored filter JSON).

**Spiral-adjusted rule:** `defensible_pages` per domain = **paths for spiral-flagged domains, distinct URLs otherwise.** A domain is a spiral only when BOTH gates trip (overage > threshold AND ratio > threshold). Substitute paths for a spiral domain — do not drop it, do not apply paths to non-spiral domains. Per-domain `defensible_pages` MUST sum to the anchor.

## Stage 2 — Size usage + price

**REQUIRED READING:** `$REFS/usage-methodology.md` (multipliers, defaults, layered cadence, use-case profiles, ask-the-customer map) and `$REFS/pricing-model.md` (graduated tiers, buffer, live fetch + fallback, no-override rule). **Never invent a value, never block, never do the math in your head.** For any missing input apply the labeled default and add a line to an **"Assumptions to verify with the customer"** list. Never quote a $/page or $/scan rate from memory.

1. **Pick the use case** (privacy / analytics / accessibility) — seeds multiplier + cadence defaults.
2. **Set multipliers** — geographies, scenarios, environments — via regulation-based defaults (CCPA→3, GDPR→2, else 1; prod+staging→1.5). Flag every defaulted one.
3. **Set cadence layers** — risk-framed ("how long can you tolerate an undetected issue?"), additive.
4. **Fetch live pricing:** `python3 "$SCRIPTS/fetch_pricing.py"` → `{tiers, source}`.
5. **Compute:** assemble the inputs JSON (`page_count` low/anchor/high, `multipliers`, `cadence_layers`, `buffer_pct`, plus fetched `tiers` + `source`) → `python3 "$SCRIPTS/compute_scope.py" <inputs.json>`. Use its numbers verbatim.
6. **Present** the rep-facing breakdown: each multiplier + rationale (defaulted?); cadence table; annual_scans range; predicted vs purchased (if buffer — and if `tier_changed_by_buffer` is true, **call out that the buffer pushed the deal into a different pricing tier**); tier; live price-by-band + total range; the recommended quote (anchor); the **recommended contract** (`recommended_contract` — a clean round price and the **exact** scans that reconcile to it); the implied-blended-frequency note; the pricing **`source`** stamp; the assumptions-to-verify checklist. If `source` starts with `"FALLBACK"` (live pricing unavailable), add a "pricing may be stale — verify/refresh before sending" warning.

> **Journeys (funnel/login testing) default to the free $0 tier in v1.** The journey meter silently defaults to $0 — so if the deal involves **meaningful funnel/login/form testing**, FLAG it as **un-priced** and note that separate journey tiers exist (up to ~$30K). Do not let a journey-heavy deal go out priced as if journeys were free without saying so.

## Stage 3 — Assemble deliverables

Produce **BOTH** files — never just one; the proposal references the workbook. The exact field
mappings for both inputs are in `$REFS/deliverables-mapping.md` (and `build_proposal.py`'s docstring).

- **Evidence workbook:** `python3 "$SCRIPTS/build_evidence_appendix.py" <perdomain.json> "<Customer> - evidence appendix.xlsx"` — fed the Stage-1 `{rollup, per_domain}` (with `url_samples`) plus a `usage` object for the Annual Usage Breakdown sheet.
- **Proposal:** `python3 "$SCRIPTS/build_proposal.py" <proposal.json> "<Customer> - proposal.docx"` — a comprehensive, rep-first ObservePoint-themed doc that SHOWS the derivation and ends with a strippable `[INTERNAL — REMOVE BEFORE SENDING]` section. Build `proposal.json` per the mapping reference; keep internal terms out of `monitoring_summary` (the generator rejects them).
- **Output location (uniform across the plugin) — one folder per account:** rep-named base folder, else default `~/Documents/ObservePoint Revenue/Scoping & Pricing/`. Create a **per-account subfolder** (`.../Scoping & Pricing/<Customer>/`); expand `~`, `mkdir -p` first, never a temp dir. Report both **absolute paths** with the rep-facing breakdown.

## The single-source consistency rule

There is **one** Stage-1 object and it feeds BOTH pricing and the deliverables. The anchor in pricing (`page_count.anchor`), in the appendix (`rollup.spiral_adjusted_anchor`), and in the proposal MUST be the **same number**. Use the **precise** anchor everywhere (e.g. `95721`, not `96000`) — a rounded anchor breaks the sum-to-anchor invariant and the cross-deliverable match. Round only in customer-facing display text.

## Red Flags — STOP

| Rationalization | Reality |
|---|---|
| "No census yet, the rep needs a number — I'll estimate ~10k." | A fabricated count is the failure this tool prevents. Cold-start hand-off; return when the crawl completes. |
| "Quote the raw URL total — it's the biggest number." | Query-param inflation; dies under scrutiny. Anchor = spiral-adjusted. |
| "No spiral flagged, so the count is clean." | In-path `%22`/doubled-slash crawler junk defeats the spiral gate (inflates URLs and paths equally). `patterns` ≪ `raw_urls` at ratio ~1 is the tell — run `check_artifacts.py` before quoting. |
| "One domain is 1.7M pages — it's a huge account!" | Implausible for the business = a **recursion trap** (`/biz/biz/biz/…`), invisible to every gate (patterns ≈ paths ≈ urls). Raw-sample it → `check_artifacts.py`; if `recursion`, **EXCLUDE it** from the anchor (even paths are junk) and re-crawl. |
| "That spiral domain isn't real pages — exclude it." | It has real pages (its paths). Spiral-ADJUST, don't exclude. (A *recursion* trap is the opposite — exclude that one.) |
| "A census read returned `totalCount: 0` — that domain is empty." | Check for the impersonation auto-revert warning. A `0` from a reverted read is your ADMIN account, not the customer's — re-`login_as_account` and retry; never quote the 0. |
| "I'll add 20% headroom for safety/growth." | The range is data-driven (sweep + uplift + ceiling), not an invented percentage. |
| "The rep's in a hurry — use the flat $0.135." | That rate is dead. The live graduated price from the scripts IS the quote; no in-skill override. |
| "I'll state a rate / total I know roughly." | Run `fetch_pricing.py` + `compute_scope.py`. Live tiers are the only truth. No mental math. |
| "I don't know their geos/cadence — I'll bake in sensible numbers." | Apply the labeled default AND add it to the assumptions-to-verify list. |
| "The proposal, appendix, and price show different anchors." | STOP — you re-derived instead of passing one object through. |
| "I'll hand over just the proposal." | Reps need the chat breakdown AND both files (proposal `.docx` + evidence `.xlsx`). |
