---
name: scope-calculator
description: Use when a revenue or sales rep needs to scope or price an ObservePoint contract — "scope this account", "how many pages do they need", "how many pages does X have", "size a deal", "price out X", "price a known page count", "build a usage proposal". Derives a defensible page count, sizes annual page-scan usage, prices it against ObservePoint's live pricing, and produces a live Scope of Work workbook (and a clean proposal on request). Runs the whole job or any single stage. To discover which domains an org owns use owned-properties; to research/qualify a prospect use research-account.
---

# Scope Calculator

The single tool reps use to scope and price an ObservePoint contract. It is **one job in three stages** — by default Stage 3 builds the **Scope of Work** workbook for the rep to edit, then the proposal is recomputed from that edited workbook on request; jump to the stage you need. You orchestrate and judge; the scripts do every calculation and render the deliverables. **Never invent a page count, multiplier, cadence, or price — a guessed number presented as fact is the failure this tool exists to prevent.**

Set `SCRIPTS=${CLAUDE_PLUGIN_ROOT}/skills/scope-calculator/scripts` and `REFS=${CLAUDE_PLUGIN_ROOT}/skills/scope-calculator/references`. Scripts: `compute_scope.py`, `fetch_pricing.py`, `fetch_samples.py`, `check_artifacts.py`, `build_proposal.py`, `build_model.py`, `customer_clean.py`, `build_internal_evidence.py`, `anchor_guard.py`. Read the reference for whichever stage you run.

## Phase 0 — Frame

There is **no audience prompt** — do NOT ask "will these files ever reach the customer?". The **Scope of Work** workbook is clean by construction (no confidence, census IDs, raw-URL math, spiral/recursion notes), so it is always safe to hand to the rep and on to the customer. All internal context (derivation, confidence, census IDs, spiral/recursion notes, assumptions-to-verify, price-by-band) lives in the working JSONs and the pre-built internal-evidence xlsx, which Stage 3 writes to a **hidden `<Customer>/.work/` subfolder** by default and never surfaces unless the rep asks for it.

**Interpreter note:** `build_proposal.py` requires `python-docx` and `build_model.py` requires `openpyxl`. Invoke scripts with a Python that has the plugin deps (prefer `/opt/homebrew/bin/python3`). If you hit `ModuleNotFoundError`, install the repo requirements first — do NOT silently skip the deliverable.

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

7. **Anchor confirmation gate — REQUIRED before Stage 2.** The derived anchor does NOT proceed to
   pricing until the rep confirms it. Run `python3 "$SCRIPTS/anchor_guard.py" <rollup_perdomain.json>`
   (the `{rollup, per_domain}` object from step 6) and present the rep with: the **anchor + range +
   confidence**, plus any flags — the step-5 recursion/artifact verdict AND the gate's
   **dominant-host** signal. Then:
   - **HARD STOP** if ANY of: the gate reports `requires_confirmation` (a dominant host > 40% of the
     anchor, OR confidence MEDIUM/LOW), OR step 5 found a recursion/`%22` host. The rep must
     explicitly acknowledge, and for a dominant/recursion host you MUST run the step-5
     `check_artifacts.py` sample on that host and EXCLUDE it if it's a trap, then re-derive — before
     pricing. Never price past a hard stop on the rep's silence.
   - **Quick confirm** if the gate is clean (HIGH confidence, no dominant host, step-5 clean): show
     the anchor and get a one-line "confirmed" before Stage 2.
   This gate is why a silent ~15× over-count (Gallagher) cannot reach a quote: the anchor is always
   seen and OK'd, and an outsized single host is always investigated. (Applies on the full-scope
   path; "known page count" entry skips Stage 1, so the rep-supplied number is the confirmation.)

**Spiral-adjusted rule:** `defensible_pages` per domain = **paths for spiral-flagged domains, distinct URLs otherwise.** A domain is a spiral only when BOTH gates trip (overage > threshold AND ratio > threshold). Substitute paths for a spiral domain — do not drop it, do not apply paths to non-spiral domains. Per-domain `defensible_pages` MUST sum to the anchor.

## Stage 2 — Size usage + price

**REQUIRED READING:** `$REFS/usage-methodology.md` (multipliers, defaults, ask-the-customer map), `$REFS/pricing-model.md` (graduated tiers, buffer, live fetch + fallback, no-override rule), and `$REFS/frequency-advisor.md` (the cadence ladder — read this before the cadence walk in step 3). **Never invent a value, never block, never do the math in your head.** For any missing input apply the labeled default and add a line to an **"Assumptions to verify with the customer"** list. Never quote a $/page or $/scan rate from memory.

**Soft inputs — recommend-first.** Walk the rep through each input one at a time. For each: lead with an **anchored best-practice recommendation + the reasoning** (pre-filled); the rep accepts, adjusts, or says "I don't know." "I don't know" → apply the labeled default AND add an **assumptions-to-verify** line (goes to the internal-evidence file and the rep chat; never to the customer proposal).

1. **Pick the use case** (privacy / analytics / accessibility) — seeds multiplier + cadence defaults. Lead with a recommendation based on what you know about the account; if unknown, offer all three and let the rep choose; if still unknown, default to privacy (broadest scenario multiplier).
2. **Set multipliers** — walk each one recommend-first:
   - **Geographies:** "Which regulated regions need verified behavior? I recommend anchoring to all that plausibly apply." Default if unknown: 1.
   - **Consent scenarios:** "Which consent states matter? CCPA → 3 (Default + Opt-Out + GPC), GDPR → 2 (Accept-All + Reject-All)." Default by regulation (CCPA→3, GDPR→2, else 1).
   - **Environments:** "Do they validate staging/pre-prod before release? If so, prod + staging → 1.5." Default if unknown: 1 (prod only).
   Flag every defaulted multiplier in the assumptions-to-verify list.
3. **Set cadence via the frequency-advisor walk** (`$REFS/frequency-advisor.md`): open at the default ladder — **four layers** plus an **additive buffer**. Walk the four layers top to bottom — state the customer-facing **why** + default %, then the rep **keeps**, **adjusts the %**, or **drops** the layer:
   - **Baseline inventory** — Yearly — **100%** (one full-footprint pass a year).
   - **High Priority** — Weekly — **1.5%** (the pages that must never break).
   - **Moderate Priority Pages** — Monthly — **7.5%**.
   - **Low Priority Pages** — Quarterly — **20%**.
   Then confirm the **Buffer %** (default **15%**): it is **additive** — one extra pass of `combined × 15%` added on top of the layer scans, not a tier nudge. "I don't know" on any layer or the buffer → keep the default and log an assumption-to-verify. Capture each retained layer with its `{name, pct, runs_per_year, why}` plus `buffer_pct` for `compute_scope.py`. **Note: the old 5-layer ladder (Baseline 100%, Inventory refresh 50%×4, Compliance 15%×12, Release catch 5%×52, Critical watch 1%×365) and the per-use-case cadence presets are retired — this 4-layer + additive-buffer ladder is the single seed for every deal.**
4. **Fetch live pricing:** `python3 "$SCRIPTS/fetch_pricing.py"` → `{tiers, source}`.
5. **Compute:** assemble the inputs JSON (`page_count` low/anchor/high, `multipliers`, `cadence_layers`, `buffer_pct`, plus fetched `tiers` + `source`) → `python3 "$SCRIPTS/compute_scope.py" <inputs.json>`. The buffer is **additive**: `predicted_scans = Σ(layer: combined × pct × runs) + round(combined × buffer%)`, and price = the **exact** `graduated_price(predicted_scans)`. Use its numbers verbatim — `predicted_scans`, the per-layer breakdown, the price, and the emitted `multipliers` block.
6. **Present** the rep-facing breakdown: each multiplier + rationale (defaulted?); the cadence table (four layers + the additive buffer row); the **combined_pages** figure; the **predicted_scans** total (Σ layers + the additive buffer pass) with its low/anchor/high range; tier; live price-by-band + total range; the recommended quote (`recommended_quote`, which exposes `predicted_scans` priced directly at the exact graduated price for the anchor); the implied-blended-frequency note; the pricing **`source`** stamp; the assumptions-to-verify checklist. There is **no** "predicted vs purchased" split, no purchased-scans, and no recommended-contract back-solve — the single predicted total is priced directly. If `source` starts with `"FALLBACK"` (live pricing unavailable), add a "pricing may be stale — verify/refresh before sending" warning.

> **Journeys (funnel/login testing) default to the free $0 tier in v1.** The journey meter silently defaults to $0 — so if the deal involves **meaningful funnel/login/form testing**, FLAG it as **un-priced** and note that separate journey tiers exist (up to ~$30K). Do not let a journey-heavy deal go out priced as if journeys were free without saying so.

## Stage 3 — Build the Scope of Work (then proposal on request)

**Default: build ONLY the Scope of Work workbook.** Write `"<Customer> - Scope of Work.xlsx"` to the customer folder, write the working JSONs (`scope_inputs`, `model`, `proposal`, `internal`) and a **pre-built internal-evidence xlsx** to the hidden `<Customer>/.work/` subfolder, then tell the rep: **edit the Scope of Work levers, then come back for a proposal.** Do NOT prompt — this is the default; the rep can override the base folder. The exact field mappings are in `$REFS/deliverables-mapping.md` (and each script's docstring).

**On request only:**
- *"Give me the internal evidence"* → **move** the pre-built internal-evidence xlsx from `<Customer>/.work/` up into the customer folder.
- *"Build the proposal"* → read the **AE-edited** Scope of Work xlsx, **recompute** from it, and build `"<Customer> - proposal.docx"` into the customer folder.

- **Proposal (clean, on request — built from the AE-edited Scope of Work):** when the rep asks for a proposal, read the edited `"<Customer> - Scope of Work.xlsx"`, recompute, then `python3 "$SCRIPTS/build_proposal.py" <proposal.json> "<Customer> - proposal.docx"` — a clean, customer-facing snapshot: footprint, cadence table (four layers + buffer) with per-row "why", recommended investment. **No `[INTERNAL]` section, no internal terms by construction.** Build `proposal.json` from the recomputed numbers per the mapping reference; agent-composed strings (monitoring_summary, cadence names, why lines) are guard-checked (the generator rejects internal terms). `proposal.json` must include `multipliers: {geographies, scenarios, environments}` — **copy these verbatim from the recompute's emitted `multipliers` block; do NOT re-type or re-derive them**, or a factor (most often `geographies`) can silently drop and the sweep table will omit a row. When `geographies > 1` or `environments > 1` those rows appear in the sweep table. The generator hard-checks that `anchor × geographies × scenarios × environments == usage.combined_pages` (and that the cadence layers + additive buffer sum to `usage.predicted_scans`) and **refuses to render** a non-reconciling proposal (friendly error naming the mismatch) — so the proposal can never drift from the edited workbook it was recomputed from. Cadence layers require `pct`; per-layer pages and scans are derived from it (not passed in).
- **Scope of Work workbook (the default deliverable):** `python3 "$SCRIPTS/build_model.py" <model.json> "<Customer> - Scope of Work.xlsx"` — the live workbook the rep edits. Four tabs: **Scope Detail** (top-20 domains then a single bottom aggregate row, each with per-domain `Include?` (bool) and `Sample Size` (%) **yellow levers**; `Total Pages Found = SUMPRODUCT(Include?, Pages, Sample Size)`), **Scope of Work** (the live calculator — yellow INPUT cells for multipliers and cadence % with Excel formulas so scans and price recompute), **Pricing** (graduated tier table + price formula), **Sample pages** (real example URLs). Sheets are **NOT protected**. Clean by construction: no Spiral? column, no raw-URL math, no census/crawl/confidence.
- **Internal evidence (rep-only, pre-built into `.work/`):** Stage 3 pre-builds `python3 "$SCRIPTS/build_internal_evidence.py" <internal.json> "<Customer> - internal evidence.xlsx"` into the hidden `<Customer>/.work/` subfolder — the page-count derivation (census ID, crawl status, raw/defensible/reduced), per-domain spiral/recursion notes, assumptions-to-verify, predicted-scans build-up, price-by-band, rollup-dominance flag. It stays in `.work/` by default; **on the rep's request, move it up into the customer folder.** It is never part of the clean Scope of Work or proposal.
- **Output location (one folder per account) — Scope-of-Work-first:** if the rep specified a preferred output folder, use that as the base; otherwise the default base is `~/Documents/ObservePoint Revenue/Scoping & Pricing/`. Create a **per-account subfolder** (`.../Scoping & Pricing/<Customer>/`); expand `~`, `mkdir -p` first (including the hidden `<Customer>/.work/`), never a temp dir. **Only `"<Customer> - Scope of Work.xlsx"` lives at the top level of `<Customer>/`;** the working JSONs (`scope_inputs`, `model`, `proposal`, `internal`) and the pre-built internal-evidence xlsx go to `<Customer>/.work/`. Report the **Scope of Work absolute path** with the rep-facing breakdown (and the internal-evidence / proposal path only when those are produced on request).

## The single-source consistency rule

There is **one** Stage-1 object and it feeds BOTH pricing and the Scope of Work. The anchor in pricing (`page_count.anchor`), in the internal evidence (`rollup.spiral_adjusted_anchor`), and in the Scope of Work MUST be the **same number**. Use the **precise** anchor everywhere (e.g. `95721`, not `96000`) — a rounded anchor breaks the sum-to-anchor invariant. Round only in customer-facing display text. When the rep asks for a proposal, the **edited Scope of Work xlsx is the single source**: recompute from it so the proposal can never drift from the workbook the rep actually tuned.

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
| "The Scope of Work and the recomputed proposal show different anchors/prices." | STOP — recompute the proposal FROM the edited Scope of Work xlsx; don't re-derive a fresh anchor. One object flows through; the proposal mirrors the workbook the rep tuned. |
| "I'll build all the files up front and hand them over." | Default Stage 3 builds **only** the Scope of Work xlsx (working JSONs + internal-evidence go to `<Customer>/.work/`). The rep edits it; the proposal is recomputed from that edited workbook **on request**, and internal-evidence is moved up only on request. |
| "I'll show the customer the confidence rating / page-count derivation / census ID." | That's the internal file in `<Customer>/.work/`. The Scope of Work workbook (and the on-request proposal) are clean by construction — confidence, census IDs, raw URL totals, spiral/recursion notes never appear in them. |
| "The anchor looks fine — I'll go straight to pricing." | Run the **anchor gate** (`anchor_guard.py`) and get explicit rep confirmation first. An unconfirmed anchor is exactly how a silent ~15× over-count reaches the quote. Hard-stop on a dominant host (>40%), a recursion/`%22` host, or MEDIUM/LOW confidence. |
