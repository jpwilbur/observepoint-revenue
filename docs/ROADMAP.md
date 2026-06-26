# observepoint-revenue — roadmap / backlog

A living backlog for the revenue-team plugin. Tags: **[you]** requested by Jarrod ·
**[deferred]** explicitly punted earlier · **[idea]** suggestion · **[next]** queued in the Active
sequence · **[in design]** spec in progress. Check items off as they ship.

**Shipped so far (5 skills):** `find-accounts` → territory discovery (in-territory triggered prospects, ranked, seen-log dedup); `owned-properties` → domain-footprint discovery (crt.sh + WHOIS + web research →
confirmable `.xlsx` + confirmed domains printed for scoping); `scope-calculator` → the single scope/price tool (3 internal stages: derive page count → size usage → price → proposal `.docx` + evidence `.xlsx`); `research-account` → dark NERD-styled
HTML→PDF dossier; `branding-guide` → ObservePoint brand authority, branded document maker, brand checker, and live-site drift watcher. Uniform output under `~/Documents/ObservePoint Revenue/<tool>/<Account>/`. Plugin at v0.16.0.

> **v0.10.0 — pricing skills consolidated.** `derive-page-count` and `size-and-price` were merged into `scope-calculator` (they were three front doors to one job). The deterministic engine is unchanged — `compute_scope.py`, `fetch_pricing.py`, `build_evidence_appendix.py` just moved under `scope-calculator/scripts/`; the SKILL.md now has three entry paths (full scope / known page count / count only). 111 tests still green.

> **v0.10.1 — docs cleanup.** Added a dev-facing `CLAUDE.md`; trimmed the two long SKILLs by moving exhaustive detail into references.

> **v0.11.0 — census-pricing post-mortem fixes.** (1) `build_proposal` page-count display rounded to the nearest 1,000, which read "approximately 0 pages" for a ~80-page prospect and collapsed 4,722 & 5,398 both to "5,000" — replaced with 2-sig-fig rounding (`_round_sig`) matching the methodology. (2) New `check_artifacts.py` + a **required pre-quote gate**: in-path `%22`/doubled-slash crawler junk defeats the spiral gate (it inflates URLs and paths equally), so a ~80-page census read as 306 (~4× over-scope); the tell is `patterns ≪ raw_urls` at url/path ratio ~1. 120 tests. MCP-side counterparts are catalogued in `docs/mcp-issues-from-census-pricing-postmortem.md` (for the OP_MCP repo).

---

## 🔜 Active sequence — Salesforce MCP unlock (decided 2026-06-25)
The Salesforce MCP is now connected, unblocking items long deferred on "needs a SF connector."
Agreed build order — **CSMs are ahead of sales on adoption, so CS tooling is bumped up**:
1. **SF access foundation + find-accounts territory** — *shipped in v0.18.0.* A shared, read-first
   Salesforce access layer (query/read + a write-payload discipline, match-before-write upsert, and
   an owned-custom-fields governance contract with rev ops). Its first consumer replaces
   find-accounts' `territory.md` with a live SF-derived territory **and** an overlap-guard exclusion
   list (never surface a name already owned / in pipeline). Honors the architecture principle: a
   script runs the SOQL and emits the boundary + exclusions; the model still judges fit/triggers.
2. **Customer review builder (CSM, on-demand)** — top priority after the foundation. See CS section.
3. **expansion-signal radar** — alongside the review builder; see CS section.
4. **research-account → SF write-back** — quick follow; first real exercise of the write discipline.
5. **scope-calculator page-estimate field** — trivial write extension; gated on a rev-ops field def.

> **Architecture guardrail for everything SF/reporting:** scripts pull and compute every number
> (SOQL, roll-ups, deltas, pacing); Claude reads the computed result and judges/narrates — never does
> the arithmetic and never holds state. Writes go through a deterministic payload builder; the model
> only relays it through the MCP. Write **only** namespaced custom fields we own — never core
> AE/CSM-owned fields — sandbox-first, idempotent, with a dry-run mode.

## ✅ Recently shipped
- [x] **branding-guide (brand authority + document maker + brand checker)** — single source of
  truth for ObservePoint branding (colors, fonts, logos, dark/light themes, voice, boilerplate);
  shared `brand_kit.py` render kit imported by all skill renderers; `brand_check.py` draft checker;
  `verify_brand.py` live-site drift watcher; net-new branded document maker (one-pager, report,
  letter, memo, deck). Shipped in v0.16.0 (2026-06-17).
- [x] **find-accounts (territory discovery)** **[deferred→shipped]** — NERD Stage-0 ported:
  in-territory, ICP-fit, *triggered* accounts not already in pipeline; ranked with the shared
  trigger weights + recency decay; seen-log so re-runs only surface new names; chat-first with an
  optional `.xlsx` discovery radar. Shipped in v0.9.0.
- [x] **owned-properties (domain-footprint discovery)** **[you]** — org/seed → crt.sh + WHOIS
  (+ optional paid) + SEC Exhibit-21 / brand-page web research → confidence-tiered, evidence-tagged
  inventory (Confirmed vs For-Review sheets) + a **confirmed-only** domains list (stdout since v0.8.1) that feeds
  scope-calculator. Shipped in v0.8.0.

## Research & pre-call
- [ ] **free-scan "tear sheet" generator** **[idea]** — the live "what's firing vs. captured consent
  state" one-pager the dossier's opening angle keeps promising. `detect_cmp` + a small live scan.
- [ ] **research-account hardening** **[deferred/polish]** — when the homepage tag fetch is
  JS-blocked (e.g. Home Depot 403), fall back to a real quick ObservePoint scan; finish the opt-in
  `--deep-scan` Site Census path.

## Outreach
- [ ] **sequence-contacts (Sequencer)** **[deferred]** — multi-touch outreach copy under NERD's tone
  governor; drop **Gmail drafts** via the connected Gmail. Consumes a research dossier.
- [ ] **contact enrichment** **[deferred]** — email/phone for held-back contacts. Needs a
  ZoomInfo/Apollo key.
- [ ] **prospect orchestrator** **[deferred]** — chain find → research → sequence (mirrors how
  scope-calculator wraps its sub-skills).

## Customer success / renewal / expansion
- [ ] **customer review builder (CSM, on-demand)** **[you] [next]** — *reframed from "QBR prep":
  cadence is NOT the point.* Whenever a CSM wants to start a review with their customer, quickly
  gather + assemble the resources so their prep is done for them — an executive-summary for the
  customer's decision-maker + an account-planning view for the CSM. Sources: **ObservePoint account
  data** (health/usage/config — have it) + **Salesforce** (account, contract, opps, history — now
  connected) + **Gong** and **AskElephant** call intel (CSMs use both) + **"win stories"** +
  optionally Gmail. **Data-ingestion status:** SF ✓ live; Gong + AskElephant connectors NOT attached
  yet → graceful-degradation v1 = ObservePoint + Salesforce (+ pasted/exported call notes & win
  stories), with Gong/AskElephant as fast-follow connectors. Reuses branding-guide for the
  deliverable; scripts compute, Claude narrates.
- [ ] **expansion-signal radar** **[idea] [next]** — run the trigger engine against *existing
  customers* (new lawsuit, new exec, new site) → warm expansion plays. Reuses research-account's
  trigger logic, now cross-referenced with **SF contract/usage** to prioritize by account value and
  whitespace. Pairs with the review builder.
- [ ] **consumption pacing monitor** **[idea]** — track a customer's page-scans vs. contract; flag
  over-pacing (expansion) / under-pacing (churn risk). Pure ObservePoint usage data; SF contract
  terms sharpen the "vs. contract" baseline.

## Platform / integrations
- [ ] **`sample_site_census_pages` MCP tool** **[deferred]** — spec'd in
  `docs/mcp-sample-pages-tool-spec.md`; build in the MCP server repo for zero-context sample-page
  retrieval.
- [ ] **Salesforce sync** — read foundation + territory shipped in v0.18.0 (salesforce-core: org map + sf_io, resolve_territory, classify_overlap; find-accounts territory live). Write-back (research-account → SF) still pending.
  (NERD had this.)
- [ ] **journeys as a 2nd usage meter** in scope-calculator **[deferred]**.

## Hygiene / polish
- [ ] **Sub-threshold prospect path** **[idea]** — a ~80-page prospect (TKO) lands in the free
  page-scan band; consider a dedicated "below metered threshold / platform + Journeys" proposal
  template instead of the standard volume proposal. (Raised in the census-pricing post-mortem.)
- [ ] **MCP-side census/grid fixes** **[OP_MCP repo]** — see `docs/mcp-issues-from-census-pricing-postmortem.md`
  (census→audit-id mapping, `analyze_site_census_blocking`, `pages`-entity hint, `%22` artifact
  detection in `size_site_census`, sticky impersonation).
- [ ] Update the **research-account spec doc** (still says `.docx`; it's now HTML→PDF).
- [ ] Document the **PDF-engine fallback** (Chrome → weasyprint → HTML) / optional dep.
- [ ] **Keep the baked pricing table fresh** — it's the fallback when the live fetch fails. (The live
  fetch itself was silently broken by a bundle var-name churn `Gt→Yt` and fixed in **v0.11.1** by
  anchoring the parser on the tier-array *shape* instead of the var name; re-verify if ObservePoint
  ever restructures the pricing bundle further.)
- [ ] Optional **OP logo mark** in the dossier header (currently a text wordmark); dark/light tuning.
