# observepoint-revenue

A growing suite of Claude Code tools for the **ObservePoint revenue team** — packaged as a plugin
(and marketplace) so any rep can run them from Claude.

## Capabilities

1. **scope-calculator** — *size and price a contract.* Derive a defensible page count (Site Census),
   size annual page-scan usage from geographies × scenarios × environments × test cadences, price it
   against ObservePoint's *live* pricing, and produce a customer **proposal (`.docx`)** plus an
   **evidence workbook (`.xlsx`)**. Sub-skills: `derive-page-count`, `size-and-price`.
2. **research-account** — *research and qualify a named prospect.* Runs a light ObservePoint scan
   (CMP detection + a homepage tag/pixel inventory) and public web research, scores the account
   against ObservePoint's ICP **deterministically**, and produces a scored, evidence-backed
   **dossier (`.docx`)** with dated/sourced "why-now" triggers and real, source-verified contacts.

More revenue tooling (account discovery, outreach sequencing, enrichment) is planned.

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
