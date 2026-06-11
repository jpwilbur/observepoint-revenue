# MCP server issues — from the 2026-06-10 Site Census → pricing post-mortem

These are issues for the **ObservePoint MCP server** (the `OP_MCP` repo), surfaced while scoping
three prospects (Calix, Gilead, TKO) from existing Site Censuses. They are NOT plugin issues — the
plugin-side fixes (page-count rounding + an artifact-detection guard) shipped in `observepoint-revenue`
v0.11.0. Copy each block below into the OP_MCP issue tracker.

Source: `~/Documents/ObservePoint Revenue/post-mortem-site-census-grid-and-pricing.md`.
Net cost in that session: ~8–10 wasted tool calls navigating the grid API before the right entity
was found, and one census that the tooling would have over-scoped ~4× had it not been caught by hand.

---

## Priority order (recommended)

1. **#A2** census-id → audit/run-id mapping (unblocks every grid pivot)
2. **#A5** first-class census blocking/status analysis tool
3. **#A1** `pages` entity silent-zero hint
4. **#A3** links-schema guidance routes to census columns
5. **#A6** `%22` artifact detection in `size_site_census` (revenue-impacting; plugin now guards, but the data fix belongs here)
6. **#A7** sticky impersonation during an active task
7. **#A4** fresh-census name-index lag + `string_contains` bracket escaping

---

## #A1 — `pages` entity silently returns 0 for censuses (no hint)

A `query_report` on the **`pages`** entity scoped to a census returns `0 total records` with no error.
Census data lands only in the **`links`** entity. An agent reaching for the "obvious" entity gets
zero rows and no signal that it's the wrong one.
**Fix:** when a `pages` query filters on a census / `SITE_CENSUS_ID`, return a hint
("site census data is in the `links` entity"), or only expose `SITE_CENSUS_ID` on entities that
actually carry census rows.

## #A2 — census id ≠ grid `AUDIT_ID`, and the mapping is never surfaced

Filtering `links` by the census id (e.g. 1268–1270) returns 0. The grid keys censuses on
`SITE_CENSUS_ID`; the underlying `AUDIT_ID` is a different large number (e.g. 2088324). Nothing
exposes the census-id → audit-id/run-id mapping; `size_site_census` knows it internally but never
returns it, so an agent can only guess.
**Fix:** return `{census_id, audit_id, run_id, site_census_id}` from `size_site_census` /
`list_site_censuses` (or add a tiny resolver tool) so an agent can pivot into the grid deterministically.

## #A3 — `get_report_schema(links)` never routes you to the census columns

Searching the links schema for "audit", "status", "destination" surfaces `AUDIT_ID`,
`DESTINATION_*`, etc., but NOT `SITE_CENSUS_ID` or `LINK_URL` — which are the actual census columns.
**Fix:** add to the links schema guide a "For Site Censuses: scope by `SITE_CENSUS_ID`; the page-URL
column is `LINK_URL`" note, and make those columns match a "census"/"site census" search term.

## #A4 — fresh-census name-index lag + `string_contains` bracket handling

`AUDIT_NAME string_contains "Clarke"` (and `"[Wilbur][Clarke]"`) returned 0 for censuses created the
same day, although `size_site_census` could already read them — the name index lags the run data.
Separately, `string_contains` with `[` brackets appears to misbehave.
**Fix:** document the indexing lag and prefer id-based scoping for recent runs; confirm/escape literal
`[` in `string_contains`.

## #A5 — no first-class "bot-block / status breakdown" for a census

`size_site_census` emits implicit `⚠ BLOCKED (1–2 urls)` flags but there's no tool returning a
status-code histogram or a blocked-page list. An agent asked "are we being bot-blocked?" has nothing
to call and hand-rolls grid queries (this was the rabbit hole's origin).
**Fix:** add `analyze_site_census_blocking(censusId)` → `{status_histogram, blocked_hosts,
artifact_count, broken_pct}` off the `links` grid.

## #A6 — `size_site_census` misses `%22` crawler-artifact inflation (revenue-impacting)

The spiral gate only fires on query-param overage (`?`), measured as URLs-vs-paths. TKO's tkogrp.com
recorded **306 URLs**, ~**226** of them `%22`-wrapped artifacts (`/%22//news///%22`) from the
unrendered GET crawler mis-parsing escaped-quote hrefs. Because `%22` lives in the PATH, it inflates
URLs AND paths equally → ratio ~1.0–1.37, **no spiral flagged**, and the path floor was just as
inflated. Quoting the raw 306 would have over-scoped TKO ~4×; the real count is ~80.
**Fix:** add an artifact detector to `size_site_census` — strip/flag `%22`, escaped-quote sequences,
and repeated `//` path segments, and report an "artifact-adjusted" total alongside the spiral-adjusted
one. The `patterns` count (79) was closest to truth here — consider surfacing pattern-vs-URL
divergence as a second quality signal.
**Note:** the plugin now guards against this agent-side (v0.11.0 `check_artifacts.py` + a required
pre-quote gate keyed on `patterns ≪ raw_urls` at ratio ~1), but the durable fix is in the data layer here.

## #A7 — impersonation idle auto-revert fires mid-task

Between a `list_site_censuses` and a `size_site_census` call, impersonation reverted (idle) and the
size call ran on the admin account → 403s, forcing repeated `login_as_account`.
**Fix:** keep impersonation sticky while a task is actively issuing calls (or lengthen the idle
window); at minimum, have census tools detect "you're no longer in 32527" and say so explicitly
rather than returning a bare 403.

---

## Already handled / not MCP (no MCP action needed)

- **Pricing-endpoint reachability is plugin/environment, NOT MCP.** `fetch_pricing.py`'s live fetch
  from `app.observepoint.com/www-pricing/main.js` didn't resolve in the agent sandbox and fell back
  to the baked table (4 days old, so fine). The fetch and the baked fallback both live in the plugin
  and behaved exactly as designed — the MCP server isn't in this path at all. Plugin-side follow-up
  only: keep the baked table on a refresh cadence (tracked in the plugin ROADMAP).

- **Page-count rounding** (proposal read "approximately 0 pages" for TKO; Calix 4,722 and Gilead 5,398
  both collapsed to "5,000") — fixed plugin-side in v0.11.0 (`build_proposal._round_sig`, 2-sig-fig).
- **`derive-page-count` / `size-and-price` "not invocable"** — resolved by the v0.10.0 plugin merge;
  they're no longer separate skills (folded into `scope-calculator` as internal stages).
- **Plugin version skew across skills** — one plugin at one version; a clean reinstall fixes the cache split.
