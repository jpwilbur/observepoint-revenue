# Site Census methodology — deriving a defensible page-count range

Reference for the `derive-page-count` skill. Goal: given a customer (name and/or domains), return
the count of distinct **real** web pages across their domains as a **narrow, defensible range +
point estimate + confidence level**. The number drives usage-based contract sizing, so the bias is:
**as large as is legitimately defensible, never inflated past what survives customer scrutiny.**
A good answer looks like "≈84,000–97,000 pages (anchor ~84k)". "Somewhere between 100k and a
million" is a failure.

## 1. What Site Census is — and why it is unreliable

Site Census is a cheap, **unrendered GET crawler** that walks a customer's domains to estimate page
count. It is internal and flaky. Defend against these failure modes:

1. **Query-param spirals (the #1 problem).** One page reachable via session IDs / tracking params /
   faceted-nav combos / calendar pickers explodes into thousands of distinct URLs that are the SAME
   page. Counting raw URLs over-states page count by 5–50× on affected domains. This is what
   separates a defensible number from an indefensible one.
2. **No JavaScript rendering.** Can miss JS-injected links (undercount) or count app-shell variants
   (overcount). Usually small/qualitative — flag it, don't precisely model it.
3. **API flakiness.** 500s, 504 timeouts, request timeouts — worse on big accounts. The MCP tools
   retry with backoff; still handle a final failure gracefully.
4. **Suspect-zero rollups.** The list rollup sometimes reports 0 uniqueUrls for a census that has
   data. `size_site_census` handles this; never trust a raw 0 at face value.
5. **Incomplete / paused crawls.** Censuses auto-pause (default 24h, often set to the 168h/7-day
   max) and frequently stop with a large queue unvisited. An incomplete crawl UNDER-counts.

## 2. The MCP tools (this skill is a CONSUMER — do not re-implement them)

- `list_site_censuses({search, runningOnly, limit})` — find a census. `search` is a server-side,
  case-insensitive substring match on the census NAME. Names follow a rep-tag convention like
  `[Rep][Rep] CustomerName` (e.g. `[Wilbur][Bryce] Gallagher`), so search the customer's
  surname/brand, not their domain.
- `size_site_census({censusId | censusIds, spiralOverageThreshold, spiralRatioThreshold})` — THE
  workhorse. Returns, per hostname: distinct URLs, distinct PATHS (query-stripped), distinct
  PATTERNS (templated; diagnostic only), spiral flags, and three rolled-up totals:
  - **URL total** = Σ distinct URLs → the inflated ceiling; **NEVER quote this as "the number".**
  - **path floor** = Σ distinct paths → absolute defensible minimum (every path is a real page).
  - **spiral-adjusted** = URLs everywhere EXCEPT flagged spiral domains, where it substitutes paths
    → **THE ANCHOR / recommended point estimate.**
  A domain is flagged a spiral only when BOTH gates trip: overage (URLs−paths) > `spiralOverageThreshold`
  (default 10000) AND ratio (URLs/paths) > `spiralRatioThreshold` (default 1.5). Both gates matter —
  it prevents flagging domains with modest, legitimate query variety. `censusIds[]` merges several
  censuses.
- `start_site_census({ids})` — starts OR resumes a census (same endpoint). A resume only improves a
  LATER run (crawl takes hours-to-days), not the current one.
- `create_site_censuses` / `update_site_censuses` / `delete_site_censuses` — full CRUD, bulk-capable,
  support `dryRun`. Used for cold-start and cleanup.

## 3. Procedure (ordered)

1. **Context & location.** Censuses live in a central admin account (id **32527**, "Site Census" —
   treat as a configurable input, not hardcoded). The tools are admin-gated. `whoami`; if not
   already there, impersonate the central account (`login_as_account`). Reads are live immediately.
2. **Find the census.** `list_site_censuses({search: <customer name/brand>})`. Handle: exactly-one
   (proceed); multiple (disambiguate with the user — show names/ids/status); none (→ cold start).
3. **Cold start** (no census, or it covers the wrong domains). DETECT + HAND OFF: report no usable
   census; offer to create from the customer's domains (`create_site_censuses` → `start_site_census`,
   behind the write gate); tell the user a fresh crawl takes hours-to-days and to return when it
   completes. **NEVER block waiting on a crawl. NEVER fabricate a count.**
4. **Size it.** `size_site_census({censusId})`. Read the per-domain breakdown, spiral flags, the
   three totals, and completeness (done / under-crawled / running / suspect-zero).
5. **Assess completeness.** Running / paused-with-queue / under-crawled → the count is a FLOOR and
   confidence drops. You MAY offer to resume to tighten a future run — but compute and report the
   best range from current data now regardless.
6. **Derive the range** (§4) and emit the output contract (§5).

## 4. The range methodology (data-driven band + sanity ceiling)

Principle: build the range from the REAL uncertainty in THIS census, then clamp by a sanity ceiling
so it can never be absurd. The absolute band widens with magnitude; the PROPORTIONAL band tightens
as the number grows (more crawled pages = more confidence).

- **Anchor (point estimate)** = spiral-adjusted total at default thresholds.
- **Classification uncertainty (measure it — don't hand-derive).** Call `size_site_census` 2–3× with
  bracketing thresholds:
  - tighter → overage 5000, ratio 1.3 (flags MORE domains → lower spiral-adjusted total)
  - default → overage 10000, ratio 1.5
  - looser → overage 20000, ratio 2.0 (flags FEWER domains → higher spiral-adjusted total)
  The spread in spiral-adjusted total across these runs IS the band contribution from "which domains
  are borderline spirals." Marginal domains move; unambiguous ones don't.
- **Incompleteness uplift (push HIGH up only).** If `urlsToVisit > 0`, estimate additional real pages
  ≈ `urlsToVisit × (pathFloor / visitedUrls)` — the realized real-page yield per visited URL. Add to HIGH.
- **Rendering allowance.** Small qualitative upward nudge for JS-missed links; mention, don't model.
- **Assemble:**
  - `LOW  = max(pathFloor, anchor − downside-classification-spread)`
  - `HIGH = min(urlTotal, anchor + upside-classification-spread + incompleteness uplift + rendering allowance)`
  - **Clamp** the band to a proportional sanity ceiling (calibrate against real censuses):

  | N | ceiling |
  |---|---|
  | < 1k | ±20% |
  | 1k–10k | ±15% |
  | 10k–100k | ±15% (loosen toward ±12% if data is clean & complete) |
  | 100k–1M | ±10% |
  | > 1M | ±8% |

  If the data-driven band is NARROWER than the ceiling → use it (good data earns a tight range). If
  WIDER → that is a DATA-QUALITY signal: report the band clamped to the ceiling, DOWNGRADE confidence,
  and recommend the concrete fix (resume/recrawl, raise crawl limits, add param handling). Do NOT fake
  precision by clamping silently. Round bounds to ~2 significant figures (84,000 / 97,000, not 83,784).
- **Confidence:** HIGH = crawl done, few/no marginal domains, tight band. MEDIUM = paused/under-crawled
  with a modest queue, or a borderline domain swinging the band. LOW = large queue, suspect-zero,
  heavy marginal load, or band hit the ceiling.

## 5. Output contract (what `derive-page-count` returns)

A JSON object (consumed by `size-and-price` for pricing and by `build_evidence_appendix.py` for the
customer workbook):

```
per_domain[] = { hostname, raw_urls, paths, patterns, spiral_flag, spiral_ratio,
                 defensible_pages, discounted, why }   # why e.g. "349x query-param spiral"
rollup = { url_total, path_floor, spiral_adjusted_anchor, low, high, confidence,
           census_ids, crawl_status, thresholds_swept }
```

`defensible_pages` = paths for spiral-flagged domains, distinct URLs otherwise. The per-domain
`defensible_pages` MUST sum to `rollup.spiral_adjusted_anchor` (the evidence-appendix builder
enforces this invariant).

Also surface, in the rep-facing summary: the range (narrow, rounded), the anchor, a recommended
quoting number within the band, confidence + one-line reason, the **inflation discounted**
(e.g. "excluded ~388k query-param URLs across 6 domains; largest www.1stagency.com 266,042 → 761 real
pages, 349× spiral"), the completeness caveat + remediation when confidence < HIGH, and the inputs
used (census id/name, domains, thresholds swept).

## 6. Operational guardrails

- Admin-gated; operate in the central census account via impersonation. `whoami` first; impersonate
  before reading; for ANY write (create/resume/update/delete) state the account + plan, get explicit
  go-ahead, `confirm_account_plan`, act, then `stop_impersonation` when done.
- **Never** quote the raw URL total as "the number." **Never** emit an absurd range — the ceiling
  prevents it. **Never** fabricate a count when no census exists — cold-start hand-off instead.
- A single census can hold many starting URLs (Gallagher had ~240 domains under one census).
  Customers may be split across censuses — use `censusIds[]` to merge, or ask which to include.
- On a final grid failure the tool falls back to kicking off a Links export (downloadable only in the
  OP UI, NOT API-pollable) — surface that to the user rather than hanging.

## 7. Calibration ground truth (verify your range logic reproduces ~this)

Census 711, `[Wilbur][Bryce] Gallagher`, ~240 domains, crawl PAUSED with 16,732 of 483,936 queued.
- URL total = 472,228 (do NOT quote)
- path floor = 72,791
- spiral-adjusted = 83,784 ← anchor
- 6 spirals flagged, contributing 414,696 URLs that collapse to 26,252 real pages (388,444 discounted).
  Worst: www.1stagency.com 266,042 → 761 (349×); 3 jobs.* ATS subdomains (~4–5×); carefreesavings
  (254×); atlas.us.com (5.2×, the lone MARGINAL one — overage 10,917, barely over the 10k gate).

Expected behavior: anchor ~84k. Threshold sweep moves only atlas (un-flagging it at the looser
setting adds +10,917 → ~94.7k). Incompleteness uplift ≈ 16,732 × (72,791/467,204) ≈ +2,600. LOW barely
drops below the anchor. Result ≈ **84,000–97,000, point estimate ~84k, recommend quoting ~90k,
confidence MEDIUM** (paused + one borderline domain). The story: "the floor is firm because the
discounted spirals are unambiguous; the upside is one borderline domain plus the unfinished queue."
