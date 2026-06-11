---
name: scope-calculator
description: Use when a revenue or sales rep needs to scope or price an ObservePoint contract — "scope this account", "how many pages do they need", "how many pages does X have", "size a deal", "price out X", "price a known page count", "build a usage proposal". Derives a defensible page count, sizes annual page-scan usage, prices it against ObservePoint's live pricing, and produces a customer proposal + evidence workbook. Runs the whole job or any single stage. To discover which domains an org owns use owned-properties; to research/qualify a prospect use research-account.
---

# Scope Calculator

The single tool reps use to scope and price an ObservePoint contract. It is **one job in three stages** — run all three (the default) or jump to the stage you need. You orchestrate and judge; the scripts do every calculation and render the deliverables. **Never invent a page count, multiplier, cadence, or price — a guessed number presented as fact is the failure this tool exists to prevent.**

Set `SCRIPTS=${CLAUDE_PLUGIN_ROOT}/skills/scope-calculator/scripts` and `REFS=${CLAUDE_PLUGIN_ROOT}/skills/scope-calculator/references`. Scripts: `compute_scope.py`, `fetch_pricing.py`, `build_proposal.py`, `build_evidence_appendix.py`. Read the reference for whichever stage you run.

## Entry paths

- **Full scope** (default — "scope this account", "price out X"): Stage 1 → 2 → 3.
- **Known page count** ("just price ~50k pages", "what would 50k pages cost"): skip Stage 1; start Stage 2 with the count the rep gives (treat it as `anchor`, with `low`/`high` = the same unless they give a range).
- **Count only** ("how many pages does X have"): run Stage 1 and stop with the `{rollup, per_domain}` result.

## Stage 1 — Derive the page count

**REQUIRED READING before you produce a number:** `$REFS/site-census-methodology.md` (failure modes, MCP tools, range methodology, output contract, Gallagher calibration). Produce a **narrow, defensible range + anchor + confidence** from the internal Site Census crawler — as large as is legitimately defensible, never inflated past customer scrutiny, **never fabricated.**

1. **Admin safety.** `whoami` → if not in the central census account (default id 32527) `login_as_account` into it. Reads are immediate. For ANY write (create/start/update/delete): state account + plan, get explicit go-ahead, `confirm_account_plan`, act, then `stop_impersonation`.
2. **Find the census.** `list_site_censuses({search:<customer surname/brand>})` (names are `[Rep][Rep] Customer`). One → proceed. Multiple → disambiguate. None → **cold start**: do NOT invent a number; offer to create + start one (behind the write gate), tell the rep a fresh crawl takes hours-to-days, never block waiting.
3. **Size + sweep.** `size_site_census({censusId})` at default thresholds, then sweep (5000/1.3, 10000/1.5, 20000/2.0). Read per-hostname URLs/paths/spiral flags + the three totals.
4. **Derive the range** per the reference: anchor = spiral-adjusted total; band from the sweep spread; HIGH gets the incompleteness uplift `urlsToVisit × pathFloor/visitedUrls`; clamp to the sanity ceiling; round to ~2 sig figs; assign confidence.
5. **Artifact check (required before quoting).** "No spiral flagged" ≠ clean: in-path crawler junk (`%22`/escaped-quote/doubled-slash) inflates URLs and paths equally, so the spiral gate misses it (TKO: 306 raw → ~80 real, ~4×). Tell = `patterns` ≪ `raw_urls` at url/path ratio ~1. Pull a host sample **without** the `%22` filter and run `python3 "$SCRIPTS/check_artifacts.py" <urls.json>`; verdict `inflated` → quote the clean count (its `patterns` count), not the raw/spiral-adjusted total. See `$REFS/site-census-methodology.md`.
6. **Emit `{rollup, per_domain[]}`** + the discounted-spiral transparency line. `size_site_census` itemizes only the top ~40 hostnames — on bigger accounts add a single labeled **tail-aggregate row** so `per_domain` sums to the anchor. Pull ~5–6 real sample pages per itemized domain into `url_samples` via the links grid (clean pages, never fabricated).

**Spiral-adjusted rule:** `defensible_pages` per domain = **paths for spiral-flagged domains, distinct URLs otherwise.** A domain is a spiral only when BOTH gates trip (overage > threshold AND ratio > threshold). Substitute paths for a spiral domain — do not drop it, do not apply paths to non-spiral domains. Per-domain `defensible_pages` MUST sum to the anchor.

## Stage 2 — Size usage + price

**REQUIRED READING:** `$REFS/usage-methodology.md` (multipliers, defaults, layered cadence, use-case profiles, ask-the-customer map) and `$REFS/pricing-model.md` (graduated tiers, buffer, live fetch + fallback, no-override rule). **Never invent a value, never block, never do the math in your head.** For any missing input apply the labeled default and add a line to an **"Assumptions to verify with the customer"** list. Never quote a $/page or $/scan rate from memory.

1. **Pick the use case** (privacy / analytics / accessibility) — seeds multiplier + cadence defaults.
2. **Set multipliers** — geographies, scenarios, environments — via regulation-based defaults (CCPA→3, GDPR→2, else 1; prod+staging→1.5). Flag every defaulted one.
3. **Set cadence layers** — risk-framed ("how long can you tolerate an undetected issue?"), additive.
4. **Fetch live pricing:** `python3 "$SCRIPTS/fetch_pricing.py"` → `{tiers, source}`.
5. **Compute:** assemble the inputs JSON (`page_count` low/anchor/high, `multipliers`, `cadence_layers`, `buffer_pct`, plus fetched `tiers` + `source`) → `python3 "$SCRIPTS/compute_scope.py" <inputs.json>`. Use its numbers verbatim.
6. **Present** the rep-facing breakdown: each multiplier + rationale (defaulted?); cadence table; annual_scans range; predicted vs purchased (if buffer); tier; live price-by-band + total range; the recommended quote (anchor); the **recommended contract** (`recommended_contract` — a clean round price and the **exact** scans that reconcile to it); the implied-blended-frequency note; the pricing **`source`** stamp; the assumptions-to-verify checklist. If `source` starts with `"fallback"`, add a "pricing may be stale — verify/refresh" warning.

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
| "That spiral domain isn't real pages — exclude it." | It has real pages (its paths). Spiral-ADJUST, don't exclude. |
| "I'll add 20% headroom for safety/growth." | The range is data-driven (sweep + uplift + ceiling), not an invented percentage. |
| "The rep's in a hurry — use the flat $0.135." | That rate is dead. The live graduated price from the scripts IS the quote; no in-skill override. |
| "I'll state a rate / total I know roughly." | Run `fetch_pricing.py` + `compute_scope.py`. Live tiers are the only truth. No mental math. |
| "I don't know their geos/cadence — I'll bake in sensible numbers." | Apply the labeled default AND add it to the assumptions-to-verify list. |
| "The proposal, appendix, and price show different anchors." | STOP — you re-derived instead of passing one object through. |
| "I'll hand over just the proposal." | Reps need the chat breakdown AND both files (proposal `.docx` + evidence `.xlsx`). |
