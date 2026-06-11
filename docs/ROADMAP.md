# observepoint-revenue — roadmap / backlog

A living backlog for the revenue-team plugin. Tags: **[you]** requested by Jarrod ·
**[deferred]** explicitly punted earlier · **[idea]** suggestion. Check items off as they ship.

**Shipped so far (4 skills):** `find-accounts` → territory discovery (in-territory triggered prospects, ranked, seen-log dedup); `owned-properties` → domain-footprint discovery (crt.sh + WHOIS + web research →
confirmable `.xlsx` + confirmed domains printed for scoping); `scope-calculator` → the single scope/price tool (3 internal stages: derive page count → size usage → price → proposal `.docx` + evidence `.xlsx`); `research-account` → dark NERD-styled
HTML→PDF dossier. Uniform output under `~/Documents/ObservePoint Revenue/<tool>/<Account>/`. Plugin at v0.10.0.

> **v0.10.0 — pricing skills consolidated.** `derive-page-count` and `size-and-price` were merged into `scope-calculator` (they were three front doors to one job). The deterministic engine is unchanged — `compute_scope.py`, `fetch_pricing.py`, `build_evidence_appendix.py` just moved under `scope-calculator/scripts/`; the SKILL.md now has three entry paths (full scope / known page count / count only). 111 tests still green.

> **v0.10.1 — docs cleanup.** Added a dev-facing `CLAUDE.md`; trimmed the two long SKILLs by moving exhaustive detail into references.

> **v0.11.0 — census-pricing post-mortem fixes.** (1) `build_proposal` page-count display rounded to the nearest 1,000, which read "approximately 0 pages" for a ~80-page prospect and collapsed 4,722 & 5,398 both to "5,000" — replaced with 2-sig-fig rounding (`_round_sig`) matching the methodology. (2) New `check_artifacts.py` + a **required pre-quote gate**: in-path `%22`/doubled-slash crawler junk defeats the spiral gate (it inflates URLs and paths equally), so a ~80-page census read as 306 (~4× over-scope); the tell is `patterns ≪ raw_urls` at url/path ratio ~1. 120 tests. MCP-side counterparts are catalogued in `docs/mcp-issues-from-census-pricing-postmortem.md` (for the OP_MCP repo).

---

## ✅ Recently shipped
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
- [ ] **QBR preparation** **[you]** — aggregate known customer context → an executive-summary report
  for the decision-maker + an account-planning view for the CSM. Pulls ObservePoint account
  health/usage/config (have it) + emails (Gmail) + Gong/AskElephant notes. **Crux: data ingestion** —
  no Gong/AskElephant/Salesforce connector attached today, so v1 ≈ ObservePoint + Gmail + pasted/
  exported call notes; real connectors are a follow-on.
- [ ] **consumption pacing monitor** **[idea]** — track a customer's page-scans vs. contract; flag
  over-pacing (expansion) / under-pacing (churn risk). Pure ObservePoint usage data.
- [ ] **expansion-signal radar** **[idea]** — run the trigger engine against *existing customers*
  (new lawsuit, new exec, new site) → warm expansion plays. Reuses research-account's trigger logic.

## Platform / integrations
- [ ] **`sample_site_census_pages` MCP tool** **[deferred]** — spec'd in
  `docs/mcp-sample-pages-tool-spec.md`; build in the MCP server repo for zero-context sample-page
  retrieval.
- [ ] **Salesforce sync** **[deferred]** — overlap-guard + write-back (NERD had it). Needs a SF connector.
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
- [ ] **Refresh the baked pricing table** on a cadence — `fetch_pricing.py`'s live fetch can fail in
  an agent sandbox and fall back to the baked tiers (worked as designed; keep them recent). Plugin/
  environment, not MCP.
- [ ] Optional **OP logo mark** in the dossier header (currently a text wordmark); dark/light tuning.
