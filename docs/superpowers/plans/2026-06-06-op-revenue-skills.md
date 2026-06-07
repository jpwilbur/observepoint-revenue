# ObservePoint Revenue — Scope Calculator Skills Layer (Plan 2 of 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan (inline, controller-driven). The SKILL.md tasks ALSO require superpowers:writing-skills (TDD-for-documentation) and superpowers:testing-skills-with-subagents — the controller authors each skill and runs the subagent pressure tests directly, because those tests spawn their own subagents (nesting an implementer subagent under them is awkward). The deterministic tasks (script, references, requirements) may be subagent-driven if preferred. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build the rep-facing skill layer that turns the tested engine (Plan 1) into a usable plugin: a single `scope-calculator` entry skill that orchestrates Site Census page-count derivation (Part 1) and consultative usage+pricing (Parts 2–3), then emits a customer proposal `.docx` and evidence `.xlsx`.

**Architecture:** Three skills under `observepoint-revenue/skills/` — `scope-calculator` (the only entry reps invoke; orchestrates the other two and assembles deliverables), `derive-page-count` (drives the ObservePoint Site Census MCP tools per the Part 1 brief → defensible page-count range + per-domain evidence), and `size-and-price` (consultative multipliers/cadence → runs the Plan-1 scripts → breakdown). Plus one new deterministic script `build_proposal.py` (python-docx) for the customer one-pager. SKILL.md files are authored with writing-skills TDD; the script is authored with code TDD (pytest).

**Tech Stack:** Markdown SKILL.md + references; Python 3 + `python-docx` (new) for the proposal; `openpyxl` (existing) for the appendix; `pytest`; the ObservePoint MCP tools (`mcp__ObservePoint__*`) for live Site Census + the live pricing fetch from Plan 1.

**Reference docs:** Spec `docs/superpowers/specs/2026-06-06-op-revenue-scope-calculator-design.md` (esp. §3 architecture, §4 engine, §5 ask-map, §6 use-case profiles, §7 range, §8 outputs, §9 guardrails, §13 Plan-2 contract notes). Part 1 brief: `/Users/jarrodwilbur/Downloads/SCOPE CALCULATOR SKILL.md` (the Site Census procedure + range methodology + calibration). Plan 1: `docs/superpowers/plans/2026-06-06-op-revenue-engine.md`.

**Engine contracts this layer drives (from Plan 1, do not re-implement):**
- `size-and-price/scripts/fetch_pricing.py` → CLI prints `{tiers, source}`.
- `size-and-price/scripts/compute_scope.py` → CLI reads inputs JSON, prints full breakdown (accepts `source` as alias for `pricing_source`).
- `derive-page-count/scripts/build_evidence_appendix.py` → CLI reads per-domain JSON + out path, writes `.xlsx`.

---

## File Structure

```
observepoint-revenue/
├── requirements.txt                 # MODIFY: runtime deps only (openpyxl, python-docx)
├── requirements-dev.txt             # CREATE: pytest
├── .gitignore                       # CREATE: per-plugin ignores
├── tests/
│   ├── conftest.py                  # MODIFY: add scope-calculator/scripts to sys.path
│   └── test_build_proposal.py       # CREATE
└── skills/
    ├── scope-calculator/
    │   ├── SKILL.md                 # CREATE (writing-skills TDD) — the single entry point
    │   └── scripts/build_proposal.py# CREATE (code TDD) — customer .docx one-pager
    ├── derive-page-count/
    │   ├── SKILL.md                 # CREATE (writing-skills TDD) — Site Census Part 1
    │   └── references/site-census-methodology.md   # CREATE — distilled Part 1 brief
    └── size-and-price/
        ├── SKILL.md                 # CREATE (writing-skills TDD) — consultative Parts 2-3
        └── references/
            ├── usage-methodology.md # CREATE — multipliers, cadence, use-case profiles, ask-map
            └── pricing-model.md     # CREATE — official model, tiers, fetch+fallback, refresh
```

All commands assume working dir `/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill`. Commit after each task; append the trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` to every commit. Stay on `main` (no new branch). Push at the end (`git push`).

---

### Task 1: Dependency hygiene + proposal-script test path

**Files:**
- Modify: `observepoint-revenue/requirements.txt`
- Create: `observepoint-revenue/requirements-dev.txt`
- Create: `observepoint-revenue/.gitignore`
- Modify: `observepoint-revenue/tests/conftest.py`

- [ ] **Step 1: Split runtime vs dev deps.** Overwrite `observepoint-revenue/requirements.txt` with:
```
openpyxl>=3.1
python-docx>=1.1
```
Create `observepoint-revenue/requirements-dev.txt` with:
```
pytest>=8.0
```

- [ ] **Step 2: Per-plugin .gitignore.** Create `observepoint-revenue/.gitignore`:
```
__pycache__/
*.pyc
.pytest_cache/
.DS_Store
*.xlsx
*.docx
```

- [ ] **Step 3: Install the new runtime dep.** Run: `python3 -m pip install --break-system-packages python-docx`
Expected: installs `python-docx` (and `lxml`). Verify: `python3 -c "import docx; print(docx.__version__)"` prints a version.

- [ ] **Step 4: Add the orchestrator scripts dir to the test path.** In `observepoint-revenue/tests/conftest.py`, add `"skills/scope-calculator/scripts"` to the `rel` tuple so it reads:
```python
for rel in (
    "skills/size-and-price/scripts",
    "skills/derive-page-count/scripts",
    "skills/scope-calculator/scripts",
):
```

- [ ] **Step 5: Confirm nothing broke.** Run: `python3 -m pytest observepoint-revenue/tests -q` → expect 33 passed (unchanged).

- [ ] **Step 6: Commit.**
```bash
git add observepoint-revenue/requirements.txt observepoint-revenue/requirements-dev.txt observepoint-revenue/.gitignore observepoint-revenue/tests/conftest.py
git commit -m "chore: split runtime/dev deps, per-plugin gitignore, proposal test path

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `build_proposal.py` — customer proposal one-pager (code TDD)

**Files:**
- Create: `observepoint-revenue/skills/scope-calculator/scripts/build_proposal.py`
- Test: `observepoint-revenue/tests/test_build_proposal.py`

- [ ] **Step 1: Write the failing tests.** Create `observepoint-revenue/tests/test_build_proposal.py`:
```python
import json
import pathlib
import subprocess
import sys

import pytest
from docx import Document

import build_proposal as bp

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "scope-calculator" / "scripts" / "build_proposal.py"

DATA = {
    "customer": "Acme Corp",
    "use_case": "privacy",
    "domains": ["acme.com", "shop.acme.com"],
    "regulations": ["CCPA"],
    "monitoring_summary": "Full-site privacy sweep annually, with a critical slice re-checked monthly.",
    "page_universe": {"low": 180_000, "anchor": 197_000, "high": 210_000, "confidence": "MEDIUM"},
    "scope": {"predicted_scans": 1_664_256, "purchased_scans": 1_830_682, "buffer_pct": 0.10,
              "tier": "professional", "price_total": 139_687.28,
              "pricing_source": "live @ https://app.observepoint.com/www-pricing/main.js"},
}


def _text(doc):
    return "\n".join(p.text for p in doc.paragraphs)


def test_proposal_contains_key_fields():
    t = _text(bp.build_proposal(DATA))
    assert "Acme Corp" in t
    assert "acme.com" in t and "shop.acme.com" in t
    assert "CCPA" in t
    assert "1,830,682" in t          # purchased
    assert "1,664,256" in t          # predicted
    assert "10% buffer" in t
    assert "$139,687" in t
    assert "professional" in t


def test_proposal_no_buffer_phrasing_when_zero():
    d = json.loads(json.dumps(DATA))
    d["scope"]["buffer_pct"] = 0.0
    d["scope"]["purchased_scans"] = d["scope"]["predicted_scans"]
    t = _text(bp.build_proposal(d))
    assert "buffer" not in t.lower()
    assert "1,664,256" in t


def test_proposal_omits_internal_pricing_source():
    # The bundle URL / source stamp is internal-only; it must not appear in the customer doc.
    t = _text(bp.build_proposal(DATA))
    assert "app.observepoint.com" not in t
    assert "live @" not in t


def test_clean_guard_rejects_internal_terms():
    d = json.loads(json.dumps(DATA))
    d["monitoring_summary"] = "We discounted query-param spiral URLs."
    doc = bp.build_proposal(d)
    with pytest.raises(ValueError):
        bp._assert_clean(doc)


def test_cli_writes_docx(tmp_path):
    f = tmp_path / "in.json"; f.write_text(json.dumps(DATA))
    out = tmp_path / "p.docx"
    res = subprocess.run([sys.executable, str(SCRIPT), str(f), str(out)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == str(out)
    assert "Acme Corp" in _text(Document(out))
```

- [ ] **Step 2: Run to verify failure.** Run: `python3 -m pytest observepoint-revenue/tests/test_build_proposal.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'build_proposal'`.

- [ ] **Step 3: Implement the script.** Create `observepoint-revenue/skills/scope-calculator/scripts/build_proposal.py`:
```python
"""Render the customer-facing proposal one-pager (.docx) from the scope/compute output.
Customer-facing: NO internal discounting, spiral, or pricing-source language.

Input JSON: {customer, use_case, domains[], regulations[], monitoring_summary,
page_universe:{low,anchor,high,confidence},
scope:{predicted_scans, purchased_scans, buffer_pct, tier, price_total, pricing_source?}}.
`pricing_source` is accepted but intentionally NOT rendered (internal only)."""
import json
import sys

from docx import Document
from docx.shared import Pt

# Internal-only language that must never reach a customer-facing proposal.
_FORBIDDEN = ("spiral", "discount", "query-param", "raw url", "indefensible", "fallback")


def _int(n):
    return f"{int(round(n)):,}"


def _usd(n):
    return f"${n:,.0f}"


def build_proposal(data):
    s = data["scope"]
    pu = data["page_universe"]
    doc = Document()

    doc.add_heading("ObservePoint — Proposed Scope & Investment", level=0)
    doc.add_paragraph(data.get("customer", ""))

    doc.add_heading("Scope", level=1)
    doc.add_paragraph("Properties: " + ", ".join(data.get("domains", [])))
    doc.add_paragraph(
        f"Page universe: ~{_int(pu['low'])}–{_int(pu['high'])} pages "
        f"(planning anchor ~{_int(pu['anchor'])})."
    )
    if data.get("regulations"):
        doc.add_paragraph("Regulations covered: " + ", ".join(data["regulations"]))

    doc.add_heading("What ObservePoint will monitor", level=1)
    doc.add_paragraph(data.get("monitoring_summary", ""))

    doc.add_heading("Recommended annual usage", level=1)
    if s.get("buffer_pct"):
        doc.add_paragraph(
            f"{_int(s['purchased_scans'])} page-scans / year "
            f"({_int(s['predicted_scans'])} projected + {round(s['buffer_pct'] * 100)}% buffer)."
        )
    else:
        doc.add_paragraph(f"{_int(s['purchased_scans'])} page-scans / year.")

    doc.add_heading("Investment", level=1)
    doc.add_paragraph(f"{_usd(s['price_total'])} per year ({s.get('tier', '')} tier).")
    foot = doc.add_paragraph()
    run = foot.add_run("Pricing reflects ObservePoint's published usage-based rates.")
    run.italic = True
    run.font.size = Pt(8)

    return doc


def _assert_clean(doc):
    """Defense-in-depth: no internal-only language leaked into the customer doc."""
    text = "\n".join(p.text for p in doc.paragraphs).lower()
    leaked = [w for w in _FORBIDDEN if w in text]
    if leaked:
        raise ValueError(f"proposal contains internal-only term(s): {leaked}")


def main(argv):
    if len(argv) > 1:
        with open(argv[1]) as fh:
            raw = fh.read()
    else:
        raw = sys.stdin.read()
    out = argv[2] if len(argv) > 2 else "proposal.docx"
    doc = build_proposal(json.loads(raw))
    _assert_clean(doc)
    doc.save(out)
    print(out)


if __name__ == "__main__":
    main(sys.argv)
```

- [ ] **Step 4: Run to verify pass.** Run: `python3 -m pytest observepoint-revenue/tests/test_build_proposal.py -q` → expect 5 passed.

- [ ] **Step 5: Full suite.** Run: `python3 -m pytest observepoint-revenue/tests -q` → expect 38 passed.

- [ ] **Step 6: Commit.**
```bash
git add observepoint-revenue/skills/scope-calculator/scripts/build_proposal.py observepoint-revenue/tests/test_build_proposal.py
git commit -m "feat: customer proposal one-pager generator (build_proposal.py)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Reference files (distilled from the spec + Part 1 brief)

These are **reference** content (no discipline rules to pressure-test) — write them directly from the cited sources, then sanity-check retrieval. Keep each focused.

**Files:**
- Create: `observepoint-revenue/skills/derive-page-count/references/site-census-methodology.md`
- Create: `observepoint-revenue/skills/size-and-price/references/usage-methodology.md`
- Create: `observepoint-revenue/skills/size-and-price/references/pricing-model.md`

- [ ] **Step 1: `site-census-methodology.md`.** Distill the Part 1 brief (`/Users/jarrodwilbur/Downloads/SCOPE CALCULATOR SKILL.md`). Required sections, each with the brief's specifics: (a) what Site Census is + its 5 failure modes (query-param spirals, no-JS, API flakiness, suspect-zero, incomplete crawls); (b) the MCP tools and their roles (`list_site_censuses` search by rep-tag name, `size_site_census` with `spiralOverageThreshold`/`spiralRatioThreshold`, `start_site_census`, CRUD); (c) the ordered procedure (impersonate central account → find → cold-start hand-off → size → assess completeness → derive range); (d) the range methodology — anchor = spiral-adjusted total; threshold sweep (tighter 5000/1.3, default 10000/1.5, looser 20000/2.0); incompleteness uplift = `urlsToVisit × pathFloor/visitedUrls`; the proportional sanity-ceiling table (N<1k ±20%, 1k–10k ±15%, 10k–100k ±15%, 100k–1M ±10%, >1M ±8%); rounding to ~2 sig figs; confidence bands (HIGH/MEDIUM/LOW); (e) the per-domain output contract (spec §4.6: `per_domain[]` + `rollup`) and the rule `defensible_pages` = paths for spiral domains else URLs; (f) the Gallagher calibration example (census 711, ~84k anchor, the spiral transparency line). Cross-link the live procedure to the `derive-page-count` SKILL.

- [ ] **Step 2: `usage-methodology.md`.** From spec §4.2, §4.3, §4.6 reconciliation, §5, §6. Required content (include the concrete tables verbatim): the multiplier definitions + defaults (geographies=1; scenarios by regulation CCPA 3 / GDPR 2 / HIPAA|none 1; environments prod=1, prod+staging=1.5); `use_case_pages = base × geos × scenarios × environments`; the layered-cadence model + the cadence/runs table (per-deploy/triggered, daily 365, weekly 52, monthly 12, quarterly 4, annual 1) with the account-config property-role mapping; the **risk-framed cadence principle** ("how long can you tolerate an undetected issue?"; privacy = legal-exposure window + evidentiary cadence; analytics = data-quality window); the three use-case profiles (privacy/analytics/accessibility) with their seed defaults; the implied-blended-frequency reconciliation (`annual_scans / use_case_pages`); and the §5 ask-the-customer map (table of input → default → question). Cross-link to the `size-and-price` SKILL.

- [ ] **Step 3: `pricing-model.md`.** From spec §4.4, §4.5, §4.7. Required content: the graduated tier table (1k free / 50k @.17 / 500k @.12 / 1M @.06 / 5M @.04 / 50M @.03) and that pricing is graduated/marginal; the tier classifier (<600k starter, ≤6M professional, else enterprise); the buffer rule (`purchased = round(predicted × (1+buffer))`; pricing+tier use purchased); journeys = free-tier default ($0), not metered in v1; the live-fetch contract (`fetch_pricing.py` → `{tiers, source}`; `source` startswith "fallback" → the SKILL must surface a refresh warning); the manual refresh/verify path (re-run `fetch_pricing.py`; update `BAKED_TIERS`/`BAKED_AS_OF` in `compute_scope.py` if the live table changes). State clearly: **live calculator is the sole source of truth; no in-skill price override.** Cross-link to the `size-and-price` SKILL.

- [ ] **Step 4: Retrieval check.** Spawn a subagent (general-purpose) given ONLY each reference file and ask three concrete retrieval questions per file (e.g. "What threshold sweep values does the anchor range use?", "What's the scenarios multiplier for CCPA and why?", "What price/page applies to the 500,001st page?"). Confirm it answers correctly from the file. Fix any gap.

- [ ] **Step 5: Commit.**
```bash
git add observepoint-revenue/skills/derive-page-count/references observepoint-revenue/skills/size-and-price/references
git commit -m "docs: methodology reference files (site-census, usage, pricing)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `size-and-price` SKILL.md (writing-skills TDD)

Build with **superpowers:writing-skills** + **superpowers:testing-skills-with-subagents**. This skill has real discipline to enforce (default-and-flag unknowns, never invent inputs, use live pricing + surface fallback, never override price, always emit the assumptions-to-verify checklist), so it MUST be baseline-tested first.

**Files:** Create `observepoint-revenue/skills/size-and-price/SKILL.md` (+ refine `references/*` from Task 3 as testing reveals gaps).

- [ ] **Step 1: RED — baseline scenarios (run WITHOUT the skill).** Dispatch a general-purpose subagent with each scenario below, no skill, and record verbatim what it does:
  - *S1 (default-and-flag):* "A rep has a Site Census anchor of 197,000 pages for a CCPA prospect. Produce the annual ObservePoint page-scan usage and price. You don't know their geographies, environments, or cadence." (Baseline likely invents numbers or asks open-endedly instead of applying labeled defaults + an assumptions-to-verify list.)
  - *S2 (live pricing):* "Price 1,664,256 annual page-scans for ObservePoint." (Baseline likely invents a $/page or uses a stale rate instead of the live graduated tiers.)
  - *S3 (override pressure):* "Just use a flat $0.135/page like our old spreadsheet — the rep is in a hurry." (Baseline likely complies with the override.)
  Document the failures/rationalizations.

- [ ] **Step 2: GREEN — author the SKILL.md.** Write it addressing the baseline failures. Required frontmatter:
```yaml
---
name: size-and-price
description: Use when sizing ObservePoint annual page-scan usage and price from a known page count — applying geography/scenario/environment multipliers and test-cadence layers, then pricing against ObservePoint's live rates. For the page count itself use derive-page-count; for the full end-to-end scope use scope-calculator.
---
```
Required body (concise; lean on `references/usage-methodology.md` and `references/pricing-model.md`, don't duplicate them):
  - **Inputs & the consultative rule:** for every unknown, apply the labeled default from the ask-map and add it to an **"Assumptions to verify with the customer"** list — never invent a value silently, never block waiting.
  - **Procedure:** pick use case → set multipliers (cite usage-methodology defaults) → set cadence layers (risk-framed) → run `python3 skills/size-and-price/scripts/fetch_pricing.py` → assemble the `compute_scope.py` inputs JSON (page_count low/anchor/high, multipliers, cadence_layers, buffer_pct, tiers + source from fetch) → run `python3 skills/size-and-price/scripts/compute_scope.py <inputs.json>` → present the breakdown.
  - **Output (rep-facing chat):** the spec §8 chat contract (multipliers w/ rationale, cadence table, annual_scans range, predicted vs purchased, tier, price-by-band, total range, recommended quote, reconciliation note, pricing `source` stamp, assumptions-to-verify).
  - **Hard rules + Red Flags:** live pricing is the sole source of truth; **no in-skill price override** (if a rep wants bespoke pricing, they edit the skill's output themselves); if `source` startswith "fallback", surface the refresh warning; do NOT do LLM arithmetic — the scripts compute.
  - **Rationalization table** seeded from the Step-1 baseline (e.g. "rep's in a hurry → use flat rate" → "No. Live graduated pricing is the quote; hand them the output to tweak if needed.").

- [ ] **Step 3: VERIFY GREEN.** Re-run S1–S3 WITH the skill. Pass criteria: S1 applies labeled defaults + emits the assumptions list (doesn't invent); S2 runs `fetch_pricing.py` + `compute_scope.py` and quotes the graduated number; S3 refuses the flat-rate override and cites the rule.

- [ ] **Step 4: REFACTOR.** For any new rationalization, add an explicit counter + red-flag + rationalization-table row; re-test until all three scenarios pass under pressure.

- [ ] **Step 5: Commit.**
```bash
git add observepoint-revenue/skills/size-and-price
git commit -m "feat: size-and-price skill (consultative usage + live pricing)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: `derive-page-count` SKILL.md (writing-skills TDD)

Build with writing-skills + testing-skills-with-subagents. Discipline to enforce: never quote raw URL totals as "the number"; never fabricate a count when no census exists (cold-start hand-off instead); follow the admin-impersonation safety sequence; treat suspect-zero/incomplete crawls as floors with lowered confidence.

**Files:** Create `observepoint-revenue/skills/derive-page-count/SKILL.md` (uses `references/site-census-methodology.md` + `scripts/build_evidence_appendix.py`).

- [ ] **Step 1: RED — baseline scenarios (WITHOUT skill).** Dispatch subagents, record verbatim:
  - *S1 (raw-total trap):* Give mock `size_site_census` output where one domain shows 266,042 URLs / 761 paths (349× spiral) and ask "How many real pages does this customer have?" (Baseline likely sums raw URLs → wildly inflated.)
  - *S2 (no census):* "Scope customer FooCorp; there's no Site Census for them." (Baseline likely guesses a page count instead of a cold-start hand-off.)
  - *S3 (incomplete crawl):* mock census paused with 16,732 of 483,936 URLs queued — "give the number." (Baseline likely reports it as final/HIGH confidence.)

- [ ] **Step 2: GREEN — author the SKILL.md.** Required frontmatter:
```yaml
---
name: derive-page-count
description: Use when determining how many real web pages a customer's domains have for ObservePoint contract scoping — driving the internal Site Census crawler to a defensible page-count range with a confidence level. Handles query-param spiral inflation, incomplete crawls, and cold starts. For multipliers/pricing use size-and-price; for the full scope use scope-calculator.
---
```
Required body (lean on `references/site-census-methodology.md`):
  - **Admin safety sequence:** `whoami` → impersonate the central census account (default id 32527, configurable) → reads → for ANY write (create/start/update/delete) state account+plan, get explicit go-ahead, `confirm_account_plan`, act → `stop_impersonation` when done.
  - **Procedure:** `list_site_censuses({search})` by rep-tag/brand name → handle one / multiple (disambiguate) / none (cold-start hand-off: offer create+start, tell rep crawl takes hours-to-days, never block) → `size_site_census` swept at tighter/default/looser thresholds → assess completeness → derive range + per-domain table per the reference.
  - **Output contract:** the spec §4.6 `{rollup, per_domain[]}` JSON, plus a transparency line on discounted spirals. Then offer to build the evidence `.xlsx`: `python3 skills/derive-page-count/scripts/build_evidence_appendix.py <perdomain.json> <out.xlsx>`.
  - **Hard rules + Red Flags:** NEVER quote the raw URL total as "the number"; NEVER fabricate a count (no census → cold start); incomplete/suspect-zero → floor + lowered confidence; both spiral gates must trip to flag a domain.
  - **Rationalization table** seeded from Step-1 baselines.

- [ ] **Step 3: VERIFY GREEN.** Re-run S1–S3 WITH the skill: S1 reports the spiral-adjusted ~real count (not 266k) and explains the discount; S2 does the cold-start hand-off (no invented number); S3 reports a floor + MEDIUM/LOW confidence + the incompleteness uplift, not a final HIGH number.

- [ ] **Step 4: REFACTOR** until bulletproof (new rationalizations → counters + red flags + table rows).

- [ ] **Step 5: Commit.**
```bash
git add observepoint-revenue/skills/derive-page-count
git commit -m "feat: derive-page-count skill (Site Census Part 1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: `scope-calculator` SKILL.md — the single entry point (writing-skills TDD)

Build with writing-skills. This is the only skill reps must remember; its description must trigger on natural rep phrasings. It orchestrates the other two and assembles both deliverables.

**Files:** Create `observepoint-revenue/skills/scope-calculator/SKILL.md` (uses `scripts/build_proposal.py` + the other two skills).

- [ ] **Step 1: RED — baseline scenarios (WITHOUT skill).** Dispatch subagents, record verbatim:
  - *S1 (end-to-end):* "Scope an ObservePoint contract for Acme (acme.com, shop.acme.com), CCPA privacy use case." (Baseline likely improvises an inconsistent flow / single number / no deliverables.)
  - *S2 (consistency):* Confirm whether the baseline keeps the SAME page-count anchor flowing into both the price and the evidence appendix (spec §13 — they must match). Baseline likely re-states/diverges.

- [ ] **Step 2: GREEN — author the SKILL.md.** Required frontmatter:
```yaml
---
name: scope-calculator
description: Use when a revenue/sales rep needs to size or price an ObservePoint contract for a prospect or customer — "scope this account", "how many pages do they need", "size/price a deal", "build a usage proposal". Orchestrates page-count derivation, usage+pricing, and produces a customer proposal and evidence workbook.
---
```
Required body:
  - **Orchestration flow:** gather customer + domains + use case → invoke `derive-page-count` (Part 1) to get the `{rollup, per_domain}` object → invoke `size-and-price` (Parts 2–3) feeding `page_count` = the SAME `rollup` low/anchor/high (spec §13: one Part-1 object feeds BOTH price and evidence — never re-state the anchor) → assemble deliverables.
  - **Deliverables:** (a) rep-facing chat breakdown (full internal detail + assumptions-to-verify); (b) `python3 skills/derive-page-count/scripts/build_evidence_appendix.py` → `<customer>-evidence-appendix.xlsx`; (c) `python3 skills/scope-calculator/scripts/build_proposal.py` → `<customer>-proposal.docx`. Report both file paths.
  - **Single-source consistency rule + Red Flag:** the appendix `rollup.spiral_adjusted_anchor` and the price `page_count.anchor` MUST be the same number (the build_evidence invariant enforces the per-domain side; the orchestrator must not pass a different anchor to pricing).
  - Keep it thin — delegate detail to the two sub-skills; reps only invoke this one.

- [ ] **Step 3: VERIFY GREEN.** Re-run S1 WITH the skill using mock Part-1 data (so no live MCP needed): confirm it runs the full flow, feeds one consistent anchor to both sides, and produces the chat breakdown + both files. S2: confirm the anchor in the proposal matches the appendix.

- [ ] **Step 4: REFACTOR** as needed.

- [ ] **Step 5: Commit.**
```bash
git add observepoint-revenue/skills/scope-calculator/SKILL.md
git commit -m "feat: scope-calculator entry skill (orchestrator)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: End-to-end integration dry-run (mock data, no live MCP)

**Files:** none (verification). Use a temp dir for outputs.

- [ ] **Step 1: Build a realistic mock Part-1 object** (a `perdomain.json` matching spec §4.6 with 2–3 domains incl. one spiral, rollup low/anchor/high). Save to a temp path.
- [ ] **Step 2: Drive the engine manually end-to-end:** run `fetch_pricing.py` → build a `compute_scope.py` inputs JSON using the mock rollup's low/anchor/high → run `compute_scope.py` → from its output + the mock build a `build_proposal.py` input JSON and a `build_evidence_appendix.py` input → generate `<customer>-evidence-appendix.xlsx` and `<customer>-proposal.docx` in the temp dir.
- [ ] **Step 3: Verify the artifacts:** appendix opens with the 4 sheets and the per-domain anchor equals the rollup anchor (invariant held); proposal opens and the recommended-usage number equals `compute_scope`'s `purchased_scans`; the proposal contains NO forbidden internal terms (the `_assert_clean` guard ran in `main`). Confirm the price equals the live graduated price for that purchased number.
- [ ] **Step 4: Commit** a short integration note (optional `--allow-empty`) documenting the dry-run commands actually used:
```bash
git commit --allow-empty -m "test: end-to-end scope dry-run (mock Part-1 -> .xlsx + .docx) verified

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: (OPTIONAL, supervised) live Site Census + live pricing smoke

**Do NOT run without explicit user go-ahead** — it impersonates the central ObservePoint census admin account and reads live customer data.

- [ ] **Step 1: Ask the user** for a real customer/brand to test and confirm go-ahead for admin impersonation.
- [ ] **Step 2:** Following the `derive-page-count` skill exactly, run the live flow (`whoami` → impersonate → `list_site_censuses({search})` → `size_site_census`) to produce a real `{rollup, per_domain}`; then run the full `scope-calculator` flow to produce a real proposal + appendix. `stop_impersonation` when done.
- [ ] **Step 3:** Sanity-check the range/anchor against the skill's methodology; confirm the live pricing `source` is `live`. Report results to the user. (No commit unless the user wants the sample artifacts saved — and never commit real customer data.)

---

### Task 9: Final suite, review, version bump, push

- [ ] **Step 1: Full deterministic suite.** Run: `python3 -m pytest observepoint-revenue/tests -q` → expect 38 passed.
- [ ] **Step 2: Bump the plugin version.** In `observepoint-revenue/.claude-plugin/plugin.json`, set `"version": "0.2.0"` (skills layer added). Commit.
- [ ] **Step 3: Final review.** Dispatch a final reviewer (most-capable model) over the whole Plan-2 diff: confirms the three SKILL.md descriptions trigger correctly and don't summarize workflow (CSO rule from writing-skills), the single-source-anchor rule is consistent across scope-calculator + the two sub-skills, no internal language can reach the proposal, and the references match the engine contracts. Address findings (fix → re-verify) before finishing.
- [ ] **Step 4: Push.** Run: `git push` (origin/main already tracked). Confirm the new skills are on the remote.
- [ ] **Step 5:** Tell the user the install/update commands to pull the now-functional plugin:
  `/plugin marketplace update observepoint-revenue` (or first-time: `/plugin marketplace add jpwilbur/observepoint-revenue` → `/plugin install observepoint-revenue@observepoint-revenue`).

---

## Self-Review

**1. Spec coverage:**
- §3 architecture (3 skills, single entry) → Tasks 4/5/6; entry = scope-calculator. ✓
- §4.2/§4.3 multipliers + layered cadence, §4.4/§4.5 pricing+fetch, §4.7 buffer → encoded in `usage-methodology.md`/`pricing-model.md` (Task 3) and driven by `size-and-price` (Task 4) via the Plan-1 scripts. ✓
- §4.6 per-domain contract + evidence appendix → `derive-page-count` (Task 5) emits it; `build_evidence_appendix.py` (Plan 1) renders it; consistency enforced by Task 6. ✓
- §5 ask-the-customer map + default-and-flag → `usage-methodology.md` + `size-and-price` discipline (Task 4). ✓
- §6 use-case profiles + risk-framed cadence → `usage-methodology.md` (Task 3). ✓
- §7 range + reconciliation → carried by compute_scope (Plan 1); surfaced by `size-and-price` output (Task 4). ✓
- §8 outputs: chat breakdown (Task 4 §output), `.docx` proposal (Task 2 + Task 6), `.xlsx` appendix (Plan 1 + Task 5/6). ✓
- §9 guardrails: no fabricated count / no raw totals / admin safety (Task 5); no LLM math / live pricing / no override (Task 4); proposal excludes internal terms (Task 2 `_assert_clean`). ✓
- §13 contract notes: orchestrator owns input validation + single Part-1 object + source alias + tier-on-purchased → Tasks 4/6. ✓
- Part 1 brief (Site Census procedure, methodology, calibration) → `site-census-methodology.md` (Task 3) + `derive-page-count` (Task 5). ✓
- Deferred Plan-1 cleanups (dev-deps split, per-plugin gitignore) → Task 1. ✓

**2. Placeholder scan:** Deterministic tasks (1, 2) carry complete code/commands. Reference tasks (3) cite exact sources + the concrete tables to include. SKILL.md tasks (4–6) deliberately do NOT pre-write body prose (writing-skills Iron Law: no skill before a failing baseline) but DO give the exact `description`, required sections, hard rules, and concrete RED/GREEN scenarios — the executor authors prose via writing-skills. This is intentional, not a placeholder gap.

**3. Type/contract consistency:** `build_proposal.py` input (`scope:{predicted_scans,purchased_scans,buffer_pct,tier,price_total,pricing_source?}` + `page_universe` + `domains`/`regulations`/`monitoring_summary`) is fed from `compute_scope`'s output (`anchor.purchased_scans`, `anchor.tier`, `anchor.price.total`, `recommended_quote`) + the Part-1 rollup (`low/anchor/high`) — the orchestrator (Task 6) maps these. The evidence appendix input is the unchanged Plan-1 §4.6 shape. `fetch_pricing` `source` → `compute_scope` `pricing_source` alias is honored (Plan 1). Test counts: 33 (Plan 1) → 38 after Task 2 (+5 proposal tests).
