---
name: revenue-insights
description: Use when a revenue-team member wants an analysis, report, dashboard, or metric from Salesforce / Domo / ObservePoint usage data — "renewals at risk", "pipeline coverage", "how are we pacing", "ARR/NRR", "build me a revenue report", "show me the numbers for QBR/board/forecast". Produces a branded in-chat visual (exports on request). For account research use research-account; for scoping/pricing use scope-calculator.
---

# revenue-insights

World-class revenue insight at every altitude (board → AE → CSM) from a question in chat.
**The model gathers (SF/Domo/OP MCP) and judges; deterministic scripts compute every number
and render the branded visual. No LLM math, no LLM-held state. Read-only.**

## Request flow (every report)
1. **Classify** the ask → altitude + recipe (see `references/recipe-catalog.md`) or ad-hoc
   + sources + parameters (period, segment, territory). For territory/segment, resolve via
   `lib/salesforce` (the same `resolve_territory` flow find-accounts uses).
2. **Gather** — run the recipe's queries via MCP (SF `soqlQuery`, Domo `DomoSqlQueryTool`,
   OP usage tools). Pass `--today <today's date>` to compute scripts (they don't read the clock).
3. **Compute** — pipe the returned JSON to the recipe's script; it computes every number.
4. **Render** — the script emits a branded HTML visual to
   `~/Documents/ObservePoint Revenue/revenue-insights/` (`mkdir -p`); show it in chat and
   narrate the "so what" + the script-computed caveats.
5. **Export on request** — PDF/deck/`.xlsx` via `branding-guide`.

## Recipe: renewals-at-risk
1. Read `${CLAUDE_PLUGIN_ROOT}/lib/salesforce/salesforce-org.md` ("Renewals") → run the renewal
   SOQL via `soqlQuery`; save to `<renewals.json>`. **Health is not in SF.**
2. Read `${CLAUDE_PLUGIN_ROOT}/lib/domo/domo-datasets.md` ("Account health") → run the health query
   via `DomoSqlQueryTool` (name the columns so it routes correctly); save to `<health.json>`.
3. `python3 ${CLAUDE_PLUGIN_ROOT}/skills/revenue-insights/scripts/renewals_at_risk.py <renewals.json>
   --health <health.json> --today <YYYY-MM-DD>
   --out "~/Documents/ObservePoint Revenue/revenue-insights/renewals-at-risk-<date>.html"`
   (the script joins SF renewals + Domo health on account name and computes every number).
4. Show the HTML; narrate the caveats it computed. Methodology: `references/metrics-canon.md`.

## Ad-hoc fallback (no matching recipe)
Use `references/metrics-canon.md` for definitions, write the SF/Domo SQL yourself, pipe the rows
to `scripts/adhoc_aggregate.py` for the arithmetic (never compute in your head), render via
`viz_kit`. **Label the output "ad-hoc — computed live, methodology per canon, not yet a vetted
recipe."** If it's useful and repeatable, propose promoting it to a recipe.

## Conventions
- Never fabricate a number/account/source. Missing input → labeled default + "assumptions to
  verify", or an honest "none found".
- Brand values come from `branding-guide` only. Pricing (if ever needed) = the live calculator.
- Allowed MCP tools: SF read (`soqlQuery`, `find`, `getUserInfo`, `getObjectSchema`),
  Domo read (`DomoSqlQueryTool`, `SearchTool`, `FileSetQueryTool`), OP usage read. No writes.
