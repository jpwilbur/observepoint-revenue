# Spec: bulk sample-page retrieval (`sample_site_census_pages`)

**For:** the ObservePoint MCP server (sibling of the existing `size_site_census`).
**Consumed by:** the `observepoint-revenue` plugin's `derive-page-count` skill, to populate the
evidence workbook's **Sample Pages** sheet.
**Status:** proposal. **Date:** 2026-06-07.

---

## 1. The problem this solves (and the principle behind it)

The evidence workbook wants ~4–6 real example pages per property ("proof the page count isn't
junk"). Today the agent gets those by firing **one `op_api_call` per domain** to the links grid —
40 calls on a big account.

The cost isn't the census queries (they're cheap reads server-side). The cost is that **every MCP
tool result is injected into the agent's context by protocol.** The agent is the only bridge between
the remote OP API and the local workbook script, so the URLs travel:

```
OP API  →  [agent context]  →  agent writes samples.json  →  build_evidence_appendix.py
```

The agent doesn't need to *reason about* the URLs — it's just piping them — yet it pays the token
cost (and latency) of 40 request bodies + 40 responses.

**Principle:** don't route bulk payload through the agent. A function should **fetch the data and
deposit it where the artifact builder consumes it**, returning to the agent only a *status*
(`{ok, domains, samples}`). The agent orchestrates; it never reads the URLs.

This spec is the server-side realization of that principle.

---

## 2. Design options (ordered by how completely they remove payload from context)

| Option | What the agent receives | Context cost | Build effort | Notes |
|---|---|---|---|---|
| **A. Bulk tool → compact map** | one small `{hostname:[urls]}` JSON | ~1 small response (≈95% less than 40 calls) | low | Reuses MCP auth. Payload still transits context, but once and tiny. |
| **B. Bulk tool → downloadable artifact** | `{ok, counts, exportId}` only | **zero** URL payload in context | low–med | Reuses the **Links-export** path `size_site_census` already falls back to. The local builder downloads the file directly. The agent never sees URLs. |
| **C. Local fetcher (no MCP change)** | `{ok, counts}` only | **zero** | med | A local script calls the OP REST API with an admin token and writes samples itself. No MCP change, but adds a local-auth surface (token + impersonation handled in code). |

**Recommendation:** ship **A** first (it already solves ~95% of the cost and is a tiny addition to
the MCP server), then evolve to **B** for true zero-context on large accounts. Choose **C** only if
you'd rather keep sampling entirely local and already have an admin API token available to the
plugin's environment. All three share the same grid-query core (§4).

**Avoid:** the "one giant query, bucket client-side" shortcut — it trades 40 small responses for one
huge 500–1000-URL response (as costly in context, sometimes worse) and gives unbalanced per-domain
coverage.

---

## 3. The tool

### Signature

```
sample_site_census_pages({
  censusId: number,                 // or censusIds: number[]
  hostnames?: string[],             // explicit hosts to sample; if omitted, the tool selects (see below)
  perDomain?: number = 5,           // samples per host (clamped 1..10)
  topN?: number = 10,               // when auto-selecting: top-N hosts by real-page count
  includeSpirals?: boolean = true,  // always also sample spiral-flagged hosts (best evidence)
  output?: "map" | "export" = "map" // A vs B
})
```

### Behavior

1. **Resolve the host set.**
   - If `hostnames` is given, use it.
   - Else auto-select using the same per-host rollup `size_site_census` already computes: take every
     **spiral-flagged** host (their real pages are the most persuasive evidence) **plus the top
     `topN` remaining hosts by real-page count**. Skip the long tail. This bounds the work to
     ~12–16 hosts regardless of account size.
2. **For each host, run the clean-pages grid query** (§4) and collect up to `perDomain` distinct,
   query-stripped, non-asset page URLs.
3. **Return** per `output`:
   - `"map"` (Option A): `{ census_id, sampled: [{hostname, samples: [url,...]}], counts:{domains, samples} }`
   - `"export"` (Option B): kick off a filtered **Links export** (the mechanism `size_site_census`
     already uses on grid failure), and return `{ ok, counts:{domains, samples}, exportId, downloadUrl }`
     — **no URLs in the response.** The plugin downloads the file directly into the workbook builder.

### Why server-side selection matters
The tool already has the per-host page counts (it computed them for sizing), so **it** can pick
"spirals + top-N" without the agent shuttling the candidate list back and forth. The agent's whole
interaction becomes: *"sample census 711"* → *"ok, 14 domains, 62 pages, exportId=…"*.

---

## 4. The clean-pages grid query (reference — proven against census 711)

Per host `H`, one `POST /v3/reports/grid/links`:

```json
{
  "columns": [{ "columnId": "LINK_URL", "groupBy": true }],
  "filters": { "conditionMatchMode": "all", "allAccounts": false, "conditions": [
    { "operator": "integer_in",     "filteredColumn": {"columnId": "SITE_CENSUS_ID"},      "args": [711], "negated": false },
    { "operator": "string_contains","filteredColumn": {"columnId": "LINK_URL"}, "arg": "//<H>", "wildcardStart": true, "wildcardEnd": true, "negated": false },
    { "operator": "string_contains","filteredColumn": {"columnId": "LINK_URL"}, "arg": "?",     "wildcardStart": true, "wildcardEnd": true, "negated": true },
    { "operator": "string_contains","filteredColumn": {"columnId": "LINK_URL"}, "arg": "%22",   "wildcardStart": true, "wildcardEnd": true, "negated": true },
    { "operator": "string_contains","filteredColumn": {"columnId": "LINK_URL"}, "arg": ".pdf",  "wildcardStart": true, "wildcardEnd": true, "negated": true },
    { "operator": "string_contains","filteredColumn": {"columnId": "LINK_URL"}, "arg": ".jpg",  "wildcardStart": true, "wildcardEnd": true, "negated": true }
  ]},
  "page": 0, "size": 10
}
```

Hard-won filtering rules (each fixes real garbage seen in census 711):

- **`groupBy: LINK_URL`** → distinct URLs (not the 49M raw link instances).
- **`//<H>` host match** (e.g. `//jobs.ajg.com`) isolates a single host — works for apex *and*
  subdomains. Do **not** filter on `LINK_URL_BASE_DOMAIN`: it keys on the *registrable* domain, so it
  can't separate `jobs.ajg.com` from `www.ajg.com`, and a `www.`/subdomain arg returns 0.
- **exclude `?`** → strips the query-string spiral (e.g. `/AboutUs?ufprt=…` × thousands) so you get
  the real page, not a token variant.
- **exclude `%22`** → removes crawler artifacts like `/%22//page///%22` **and** cross-host
  contamination (artifacts that embed another host inside an escaped-quote path). This one matters a
  lot — without it, several domains return almost entirely junk.
- **exclude `.pdf` / `.jpg`** (extend with `.png`, `.gif`, `.zip`, etc.) → page URLs, not assets.
- **`size` must be ≥ 10** (server min); take the first `perDomain` rows.
- Some file-heavy hosts still yield mostly docs — take the cleanest page-like rows; if none, return
  an empty list for that host (the workbook shows a "(none captured)" note). **Never fabricate URLs.**

---

## 5. How the plugin changes once this exists

`derive-page-count` (SKILL) replaces the per-domain loop with a single call:

- **Today:** for each itemized host → `op_api_call(...)` → read rows → assemble `url_samples`.
- **With A:** one `sample_site_census_pages({censusId})` → write its `sampled` map into the
  per-domain JSON → build the workbook. One small response in context.
- **With B:** one `sample_site_census_pages({censusId, output:"export"})` → get `{exportId}` →
  `build_evidence_appendix.py` downloads that export and fills the Sample Pages sheet itself. The
  agent only ever sees `{ok, counts, exportId}` — zero URLs in context.

The plugin's `url_samples` contract and the workbook's Sample Pages sheet are unchanged; only the
*fetch* path gets cheaper. Until the tool ships, the documented fallback (sample spirals + top-N via
`op_api_call`, ~12–16 calls) stays the default — see `derive-page-count/references/site-census-methodology.md`.

---

## 6. Summary

- The waste is the **agent-as-pipe** pattern, not the queries.
- Fix = a function that **fetches and deposits**, returning only status.
- Quickest: bulk tool → compact map (A). True zero-context: bulk tool → downloadable export (B),
  reusing the Links-export path. Both share the §4 query and the spirals+top-N selection.
