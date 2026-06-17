# observepoint-revenue — working notes

A Claude Code plugin: a suite of tools for the **ObservePoint revenue team**, packaged as a
plugin + marketplace (private repo `github.com/jpwilbur/observepoint-revenue`). One plugin on
purpose — splitting it would be harder to manage.

## Architecture principle (applies to every skill)

**Claude gathers and judges → deterministic Python scripts compute and render.** No LLM math, no
LLM-maintained state. The model classifies/researches/decides; scripts do the arithmetic, the
network I/O, the file rendering, and any persisted state. This keeps results reproducible and tuning
a config edit. When adding or editing a skill, preserve this boundary.

## Skills (4)

- **scope-calculator** — size/price a contract end to end. Three stages (derive page count → size
  usage → price); the default deliverable is the live **Scope of Work** workbook (`.xlsx`), and a
  clean proposal `.docx` is recomputed from the AE-edited workbook on request. Runs whole or one stage.
- **research-account** — qualify a named prospect → scored ICP dossier (HTML→PDF).
- **owned-properties** — discover an org's owned domains → confirmable `.xlsx` + confirmed-domain list.
- **find-accounts** — surface new in-territory triggered prospects → ranked list (+ optional `.xlsx`).

## Conventions the skills enforce (each SKILL.md is self-sufficient — don't rely on this file at runtime)

- **Never fabricate** a number, domain, contact, source URL, or page count. Missing input → labeled
  default + an "assumptions to verify" note, or an honest "none found".
- **Pricing = the live calculator only** (`fetch_pricing.py`); no in-skill rate override.
- **Output location:** `~/Documents/ObservePoint Revenue/<tool>/<Account>/` (rep override honored;
  `mkdir -p`; never a temp dir). `territory.md` and `Account Discovery/` live at that root.
- Single shared scoring config: `skills/research-account/references/scoring-config.json` (find-accounts
  reads it by path — never copy it).

## Dev

- **Tests:** `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q` (243 passing).
  **Interpreter trap:** bare `python3` may resolve to `/usr/bin/python3` (CLT 3.9, no pytest/openpyxl);
  always use `/opt/homebrew/bin/python3`. Never pipe pytest through `| tail` in an `&&` chain — it
  masks a missing-pytest failure.
- Each skill's scripts dir is added to `tests/conftest.py` sys.path so tests `import` them by module name.
- Specs/plans live in `docs/superpowers/`; backlog in `docs/ROADMAP.md`.
- Commit email is the GitHub noreply (`16406437+jpwilbur@users.noreply.github.com`) — keep it.

## Install / update

```
/plugin marketplace add jpwilbur/observepoint-revenue      # first time
/plugin marketplace update observepoint-revenue            # after pushing
/plugin install observepoint-revenue@observepoint-revenue
```
