---
name: salesforce-core
description: Shared read-side Salesforce foundation for the revenue plugin — the canonical org map, the named SOQL/SOSL queries other skills run, and sf_io.py (the deterministic helper that digests Salesforce MCP results). Not a standalone task; read/imported by find-accounts (territory + overlap-guard) and, later, research-account write-back, the CSM review builder, and expansion radar. Use it to look up how this org is modeled or which query to run; it does NOT itself sell, scope, or research.
---

# Salesforce Core (shared read foundation)

The single place that knows how ObservePoint's Salesforce org is shaped and how this plugin reads it.

**Architecture rule (do not break):** the MODEL calls the Salesforce MCP (the *gather* step);
deterministic Python only parses the returned JSON (the *compute* step). No Python script calls
Salesforce; no model arithmetic; no model-held state. **Read-only today** — there are no write
helpers here yet. Writes (research-account → SF, the scope page-count field) are deferred and gated
on a rev-ops owned-custom-fields governance contract; they will arrive as payload builders in
`sf_io.py` with their own design.

## What's here
- **`references/salesforce-org.md`** — the canonical org map: objects/fields this plugin reads, the
  field-hygiene rules, and the named queries (territory, user lookup, account-match). Read it before
  writing any SOQL against this org. When the org schema changes, change that file.
- **`scripts/sf_io.py`** — `parse_records(mcp_result)` (validate + extract a SOQL/SOSL record list)
  and `normalize_domain(url_or_host)` (comparable host for account matching). Imported by SF-backed
  skills: `skills/salesforce-core/scripts` is on the test sys.path; CLI scripts add it via a
  relative-path shim.

## Using it from another skill
1. Read `references/salesforce-org.md` for the query you need.
2. Have the model run that query via the Salesforce MCP (`soqlQuery` / `find` / `getUserInfo`).
3. Pass the returned JSON to the consuming skill's script, which uses `sf_io` to digest it.
