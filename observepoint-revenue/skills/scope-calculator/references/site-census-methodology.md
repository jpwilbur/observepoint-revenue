# Site Census methodology — deriving a defensible page-count range

Reference for scope-calculator's **page-count stage** (Stage 1). Goal: given a customer (name and/or domains), return
the count of distinct **real** web pages across their domains as a **narrow, defensible range +
point estimate + confidence level**. The number drives usage-based contract sizing, so the bias is:
**as large as is legitimately defensible, never inflated past what survives customer scrutiny.**
A good answer looks like "≈84,000–97,000 pages (anchor ~84k)". "Somewhere between 100k and a
million" is a failure.

## 1. What Site Census is — and why it is unreliable

Site Census is a cheap, **unrendered GET crawler** that walks a customer's domains to estimate page
count. It is internal and flaky. Defend against these failure modes:

1. **Count inflation (the #1 problem) — three flavors, all discount-or-die.** Counting raw URLs
   through any of these is what separates a defensible number from an indefensible one.
   - **Query-param spirals.** One page reachable via session IDs / tracking params / faceted-nav
     combos / calendar pickers explodes into thousands of distinct URLs that are the SAME page (5–50×
     on affected domains). `size_site_census`'s spiral gate (distinct URLs ≫ distinct paths) catches
     these.
   - **`%22` / doubled-slash artifacts.** The unrendered crawler mis-parses escaped-quote hrefs into
     junk like `/%22//news///%22`. This lives in the PATH, so URLs and paths inflate EQUALLY — the
     spiral gate is blind to it (TKO: 306 raw → ~80 real). Caught only by the artifact check (§5).
   - **Path-recursion traps.** A relative-link loop re-appends a nav segment onto the path over and
     over (`/contact/biz/biz/biz/…`). No query string, no `%22`, no doubled slash — so it defeats the
     spiral gate, the `%22` check, AND the `patterns` backstop (each depth is a structurally distinct
     template, so `patterns` ≈ `paths` ≈ `urls`). One trap can be 90%+ of an account (Gallagher 711,
     2026-06-15: stevenson-insurance.com 1.71M URLs for a ~150-page agency, a silent ~15×). Caught
     only by the recursion-aware artifact check (§5); the remedy is to EXCLUDE the host and re-crawl.
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

## 5. Output contract (what Stage 1 returns)

A JSON object (consumed by the usage+price stage and by `build_evidence_appendix.py` for the
customer workbook):

```
per_domain[] = { hostname, raw_urls, paths, patterns, spiral_flag, spiral_ratio,
                 defensible_pages, discounted, why, url_samples }
   # why         e.g. "349x query-param spiral"
   # url_samples a small capped list (~5–10) of real sample URLs for that domain, pulled from the
   #             census — populates the evidence workbook's "URL Samples" sheet so the customer can
   #             eyeball that these are genuine pages. Capture them when you size the census.
rollup = { url_total, path_floor, spiral_adjusted_anchor, low, high, confidence,
           census_ids, crawl_status, thresholds_swept }
```

`defensible_pages` = paths for spiral-flagged domains, distinct URLs otherwise. The per-domain
`defensible_pages` MUST sum to `rollup.spiral_adjusted_anchor` (the evidence-appendix builder
enforces this invariant).

**Truncated per-domain list → tail-aggregate row.** `size_site_census` lists only the top ~40
hostnames in detail and rolls the rest into the totals. When the account has more domains than that
(big accounts often have 200+), build `per_domain[]` from the rows you can see PLUS one labeled
tail-aggregate row so the invariant still holds:
`{ hostname: "(N additional domains — long tail, aggregated)",
   defensible_pages: spiral_adjusted_anchor − Σ(shown defensible_pages),
   raw_urls: url_total − Σ(shown raw_urls), spiral_flag: false,
   why: "not individually itemized in the Site Census summary" }`.
This is honest (top domains in detail + a transparent tail) and keeps the per-domain sum exact.

**`url_samples` — pull real sample pages from the links grid.** `size_site_census` doesn't return
sample URLs. **Do NOT hand-author the grid filter JSON** — that POST body is the most error-prone
manual step in Stage 1. Build it deterministically with `fetch_samples.py`, then call `op_api_call`
with it and parse the response with `parse_samples`:

```
# 1. build the exact POST body (normal mode: junk filtered out → clean real pages)
python3 "$SCRIPTS/fetch_samples.py" <censusId> <hostname>
# 2. call the grid endpoint with that body
op_api_call(method="POST", path="/v3/reports/grid/links", body=<the JSON above>)
# 3. parse the LINK_URLs out of the response (in Python, or copy the values):
python3 -c "import json,sys,fetch_samples; print(fetch_samples.parse_samples(json.load(sys.stdin)))"
```

`build_query(census_id, hostname)` returns the body for `POST /v3/reports/grid/links`: groupBy
`LINK_URL`; `SITE_CENSUS_ID integer_in [censusId]`; `LINK_URL contains "//<hostname>"`; and (normal
mode) negated-contains on `?`, `%22`, `.pdf`, `.jpg`. `parse_samples(response_json)` returns the list
of `LINK_URL` values (empty on missing/empty). For the artifact check use `--raw` (below).

Notes (all learned from live use, read-only query):
- **Isolate the host with `LINK_URL contains "//<hostname>"`** (e.g. `//jobs.acme.com`) — this works for
  apex AND subdomains. (`LINK_URL_BASE_DOMAIN` keys on the *registrable* domain, so it can't separate
  `jobs.acme.com` from `www.acme.com`; and a `www.`/subdomain arg against it returns 0.)
- **Exclude `?`** (strips the query-string spiral → clean real pages), **`%22`** (removes crawler
  artifacts like `/%22//page///%22` AND cross-host contamination, since those embed via escaped quotes),
  and **`.pdf` / `.jpg`** (and other asset extensions as needed).
- `size` must be ≥10. Take ~4–6 page URLs per itemized domain into `url_samples`.
- **Never fabricate sample URLs.** If the grid returns none, leave it empty — the workbook shows a
  "(none captured)" note. Some domains (file-heavy media libraries) may yield mostly docs; pick the
  cleanest page-like URLs.
- **How many to sample (cost control — important).** Do NOT query every itemized domain; that's one
  API round-trip per domain and the responses land back in context (token-heavy on big accounts).
  Instead sample: (a) every **spiral-flagged** domain — their real pages are the single most
  persuasive evidence (266k URLs → a handful of real pages) — plus (b) the **top ~8–10 remaining**
  domains by page count. ~12–16 queries total is bounded and token-light; the long tail is already
  represented by the aggregate row. For full per-domain coverage at scale without the token cost, a
  **server-side bulk endpoint** (one call returning a compact `{hostname: [urls]}` map) is the right
  tool — see the SKILL's note; until it exists, the top-N + spirals rule is the default.

**Artifact check (REQUIRED before you quote a count).** The spiral gate is blind to junk that lives
in the PATH, because it inflates distinct URLs AND distinct paths **equally** (url/path ratio ~1, no
spiral flag). Two kinds:
- **`%22`/doubled-slash artifacts** — the crawler mis-parses escaped-quote hrefs into `/%22//news///%22`
  (TKO: 306 raw → ~80 real, ~4×). The free tell is **`patterns` ≪ `raw_urls` at url/path ratio ~1**
  (TKO `patterns`=79 vs `raw_urls`=306).
- **Path-recursion traps** — a relative-link loop re-appends a nav segment (`/biz/biz/biz/…`). This
  defeats the `patterns` tell too (each depth is a distinct template, so `patterns` ≈ `paths` ≈ `urls`),
  so there is **no aggregate tell** — one trap reported 1.71M URLs for a ~150-page agency (Gallagher
  711), 93% of the account total, with no flag from any gate.

Because recursion has no aggregate tell, run the artifact check **on every account before quoting** —
not only when the `%22` tell fires — and **always on the single biggest host** and any host that is an
outsized share of the total. Use a sample that does NOT filter the junk:

- Build the RAW-mode query — `python3 "$SCRIPTS/fetch_samples.py" <censusId> <hostname> --raw` — which
  keeps ONLY the `SITE_CENSUS_ID` + `//<hostname>` filters (the junk is NOT filtered, so it CAN be
  measured; bump `size` to ~50–100 on suspect hosts for a firmer rate). Call `op_api_call` with it,
  `parse_samples` the response, and write the returned `LINK_URL`s to a JSON list. (A plain raw sample
  needs no negated multi-condition filter — avoid those on huge hosts; they 504. See §6.)
- Run `python3 "$SCRIPTS/check_artifacts.py" <urls.json>`. It flags `%22`/quotes/doubled-slash
  (`artifact_count`) AND repeated-segment recursion (`recursion_count`), and reports `collapsed_distinct`
  (the host's real templates once repeats collapse). **Verdict `inflated`** (≥20% junk) means that
  host's raw total is parser junk:
  - **recursion-dominant** → even its *path* count is junk. **EXCLUDE the host from the anchor** (do
    NOT substitute paths, unlike a spiral), itemize the discount with `collapsed_distinct` as the floor,
    lower confidence, and recommend a corrected re-crawl with recursion/param handling.
  - **`%22`-dominant** → quote the **clean** count for it (its `patterns` count, or
    `raw_urls × (1 − artifact_pct)`), note it in the evidence, lower confidence.

  **`clean`** → quote as normal. This is the check the `%22`-excluding sample query above CANNOT do —
  that query hides the junk by design, so it can't measure the junk rate.

Also surface, in the rep-facing summary: the range (narrow, rounded), the anchor, a recommended
quoting number within the band, confidence + one-line reason, the **inflation discounted**
(e.g. "excluded ~388k query-param URLs across 6 domains; largest www.1stagency.com 266,042 → 761 real
pages, 349× spiral"), the completeness caveat + remediation when confidence < HIGH, and the inputs
used (census id/name, domains, thresholds swept).

## 6. Operational guardrails

- Admin-gated; operate in the central census account via impersonation. `whoami` first; impersonate
  before reading; for ANY write (create/resume/update/delete) state the account + plan, get explicit
  go-ahead, `confirm_account_plan`, act, then `stop_impersonation` when done. **Impersonation can
  auto-revert (idle) mid-session:** a census-scoped read that lands on your admin account returns an
  empty success (`totalCount: 0`, HTTP 200) with an "auto-reverted / admin account" warning — NOT an
  error. Treat that as an invalid read (re-`login_as_account` + retry); never consume the `0` as data.
- **Never** quote the raw URL total as "the number." **Never** emit an absurd range — the ceiling
  prevents it. **Never** fabricate a count when no census exists — cold-start hand-off instead.
- **Never quote a count without the artifact check (§5).** "No spiral flagged" does NOT mean clean —
  in-path `%22`/doubled-slash junk AND path-recursion traps defeat the spiral gate (both inflate URLs
  and paths equally); recursion defeats the `patterns` tell too, so there is no aggregate signal — run
  `check_artifacts.py` on the biggest host(s) of every account before quoting.
- A single census can hold many starting URLs (Gallagher had ~240 domains under one census).
  Customers may be split across censuses — use `censusIds[]` to merge, or ask which to include.
- **Grid 504 on huge hosts.** A `string_contains` filter — especially negated, or several at once —
  over a multi-million-row host times out (504). The recursion/artifact check does NOT need that: a
  plain raw sample (`SITE_CENSUS_ID` + `//<host>` only, the `--raw` mode) returns fine. Don't try to
  *quantify* a trap with negated multi-filters; sample it and exclude it.
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
