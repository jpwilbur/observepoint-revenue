# observepoint-revenue — roadmap / backlog

A living backlog for the revenue-team plugin. Tags: **[you]** requested by Jarrod ·
**[deferred]** explicitly punted earlier · **[idea]** suggestion. Check items off as they ship.

**Shipped so far:** `find-accounts` → territory discovery (in-territory triggered prospects, ranked, seen-log dedup); `owned-properties` → domain-footprint discovery (crt.sh + WHOIS + web research →
confirmable `.xlsx` + confirmed domains printed for scoping); `scope-calculator` (+ `derive-page-count`,
`size-and-price`) → proposal `.docx` + evidence `.xlsx`; `research-account` → dark NERD-styled
HTML→PDF dossier. Uniform output under `~/Documents/ObservePoint Revenue/<tool>/<Account>/`. Plugin at v0.9.0.

---

## ✅ Recently shipped
- [x] **find-accounts (territory discovery)** **[deferred→shipped]** — NERD Stage-0 ported:
  in-territory, ICP-fit, *triggered* accounts not already in pipeline; ranked with the shared
  trigger weights + recency decay; seen-log so re-runs only surface new names; chat-first with an
  optional `.xlsx` discovery radar. Shipped in v0.9.0.
- [x] **owned-properties (domain-footprint discovery)** **[you]** — org/seed → crt.sh + WHOIS
  (+ optional paid) + SEC Exhibit-21 / brand-page web research → confidence-tiered, evidence-tagged
  inventory (Confirmed vs For-Review sheets) + a **confirmed-only** `domains.txt` that feeds
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
- [ ] Update the **research-account spec doc** (still says `.docx`; it's now HTML→PDF).
- [ ] Document the **PDF-engine fallback** (Chrome → weasyprint → HTML) / optional dep.
- [ ] Optional **OP logo mark** in the dossier header (currently a text wordmark); dark/light tuning.
