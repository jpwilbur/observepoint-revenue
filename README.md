# observepoint-revenue

A growing suite of Claude Code tools for the **ObservePoint revenue team** — packaged as a plugin
(and marketplace) so any rep can run them from Claude.

## Capabilities

1. **find-accounts** — *surface new prospects for your territory.* Sweeps public litigation /
   enforcement / breach / hiring signals for in-territory, ICP-fit companies with a current "why-now"
   trigger, ranks them by the shared trigger weights + recency decay, and keeps a seen-log so re-runs
   only show new names. Chat-first; optional `.xlsx` discovery radar. Feeds research-account.
2. **research-account** — *research and qualify a named prospect.* Runs a light ObservePoint scan
   (CMP detection + a homepage tag/pixel inventory) and public web research, scores the account
   against ObservePoint's ICP **deterministically**, and produces a scored, evidence-backed
   **dossier (PDF)** with dated/sourced "why-now" triggers and real, source-verified contacts.
3. **owned-properties** — *map an org's full web footprint.* From an org/seed domain, discovers owned
   registrable domains (Certificate Transparency + WHOIS + SEC Exhibit-21 / brand-page research),
   tiers them by ownership confidence, and produces a confirmable **inventory (`.xlsx`)** plus a
   confirmed-domain list that feeds scope-calculator.
4. **scope-calculator** — *size and price a contract, end to end.* One tool with three stages you can
   run whole or individually: derive a defensible page count (Site Census), size annual page-scan
   usage from geographies × scenarios × environments × test cadences, and price it against
   ObservePoint's *live* pricing — producing a customer **proposal (`.docx`)** plus an **evidence
   workbook (`.xlsx`)**.

More revenue tooling (outreach sequencing, enrichment, QBR prep) is planned.

## Install (private repo)

You need read access to this repo and to be authenticated for github.com (e.g. `gh auth login`).

```
/plugin marketplace add jpwilbur/observepoint-revenue
/plugin install observepoint-revenue@observepoint-revenue
```

Update later, after new commits are pushed:

```
/plugin marketplace update observepoint-revenue
```

Optional — for background auto-updates at startup against this private repo, set a token with
`repo` scope in your shell profile:

```
export GH_TOKEN=...        # or GITHUB_TOKEN
```

## Layout

- `observepoint-revenue/` — the plugin (skills, scripts, tests)
- `.claude-plugin/marketplace.json` — marketplace manifest (makes the repo installable)
- `docs/superpowers/specs/` — design specs (methodology, pricing model, contracts, research-account)
- `docs/superpowers/plans/` — implementation plans

## Tests

```
python3 -m pytest observepoint-revenue/tests -q     # 63 passing
```
