# observepoint-revenue — roadmap / backlog

A living backlog for the revenue-team plugin. Tags: **[you]** requested by Jarrod ·
**[deferred]** explicitly punted earlier · **[idea]** suggestion. Check items off as they ship.

**Shipped so far:** `scope-calculator` (+ `derive-page-count`, `size-and-price`) → proposal `.docx` +
evidence `.xlsx`; `research-account` → dark NERD-styled HTML→PDF dossier. Uniform output under
`~/Documents/ObservePoint Revenue/<tool>/<Account>/`. Plugin at v0.7.2.

---

## ▶ Next up
- [ ] **owned-properties (domain-footprint discovery)** **[you]** — given an org (name or seed
  domain), discover *all* owned web properties: subsidiaries/brands, ccTLDs, acquired companies,
  microsites. Mostly free public data: certificate transparency (crt.sh), reverse-WHOIS, DNS,
  `ads.txt`/`sellers.json`, SEC/10-K subsidiary exhibits, trademark records, `site:` sweeps, the
  org's own brand/footer pages. Output: a deduped, categorized, evidence-tagged domain inventory
  that feeds Site Census / scope-calculator / research-account. *Closes the "they don't know what
  they own" gap.* Low external dependency.

## Top-of-funnel / discovery
- [ ] **find-accounts (Discovery)** **[deferred]** — NERD discovery stage: in-territory, ICP-fit,
  *triggered* accounts not already in pipeline. Reuses the ported trigger/fit engine.

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
