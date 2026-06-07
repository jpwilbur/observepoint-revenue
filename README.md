# observepoint-revenue

Claude Code plugin (and marketplace) for the ObservePoint revenue team.

**First capability:** a contract **scope calculator** — derive a defensible page count, size annual
usage, price it against ObservePoint's *live* pricing, and produce a customer proposal plus an
evidence appendix.

> **Status:** Plan 1 (the deterministic engine) is **complete and tested** (33 passing tests, live
> pricing verified). Plan 2 (the rep-facing skill orchestration — the `SKILL.md` files + `.docx`
> proposal + Site Census wiring) is **not yet built**. Until Plan 2 lands, the repo installs as a
> plugin but does not yet surface rep-facing skills.

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
- `docs/superpowers/specs/` — the design spec (methodology, pricing model, contracts)
- `docs/superpowers/plans/` — the implementation plans

## Run the engine tests

```
python3 -m pytest observepoint-revenue/tests -q
```
