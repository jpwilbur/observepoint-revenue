# revenue-insights — Plan 1: Foundation (`lib/` libraries + Domo probe) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the shared, non-invokable foundation the `revenue-insights` engine needs: migrate `salesforce-core` into `lib/salesforce/`, create `lib/domo/`, and discover the Domo dataset map (so later recipes query real datasets, not guesses).

**Architecture:** Foundations are *libraries*, not skills — they have no `SKILL.md` and are referenced only by path (consumers read their docs and `import` their scripts via a relative-path shim / `conftest.py` sys.path). The rule: `SKILL.md` ⇒ invokable skill; no `SKILL.md` ⇒ `lib/` library. The model calls the SF/Domo MCPs (gather); deterministic Python only digests the returned JSON (compute). Read-only — no writes.

**Tech Stack:** Python 3 (stdlib only), pytest, the Salesforce MCP (`soqlQuery`/`find`/`getUserInfo`), the Domo MCP (`SearchTool`, `DomoSqlQueryTool`, `FileSetQueryTool`).

## Global Constraints

- **Interpreter:** always `/opt/homebrew/bin/python3`; bare `python3` may resolve to CLT 3.9 (no pytest/openpyxl).
- **Test command:** `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q` (must stay green; baseline 338 passing). Never pipe pytest through `| tail` in an `&&` chain.
- **Architecture rule:** no Python script calls SF/Domo; no model arithmetic; no model-held state. **Read-only** throughout this plan.
- **Commit email:** `16406437+jpwilbur@users.noreply.github.com` (the GitHub noreply) — keep it.
- **Plugin root:** `observepoint-revenue/`. `${CLAUDE_PLUGIN_ROOT}` resolves to it. `lib/` lives at `observepoint-revenue/lib/`.
- **Stdlib only** in `lib/` scripts (mirrors `sf_io.py`).

---

### Task 1: Migrate `salesforce-core` → `lib/salesforce/` (code + path refs)

Pure refactor: move the two artifacts, drop the skill manifest, repoint the three path references. **No behavior change** — the existing suite is the guardrail (this task's "test" is the full suite staying green, since no new behavior is added).

**Files:**
- Move: `observepoint-revenue/skills/salesforce-core/scripts/sf_io.py` → `observepoint-revenue/lib/salesforce/sf_io.py`
- Move: `observepoint-revenue/skills/salesforce-core/references/salesforce-org.md` → `observepoint-revenue/lib/salesforce/salesforce-org.md`
- Convert: `observepoint-revenue/skills/salesforce-core/SKILL.md` → `observepoint-revenue/lib/salesforce/README.md` (drop YAML frontmatter; keep dev orientation)
- Modify: `observepoint-revenue/tests/conftest.py:9`
- Modify: `observepoint-revenue/skills/find-accounts/scripts/resolve_territory.py:3,14`
- Modify: `observepoint-revenue/skills/find-accounts/scripts/classify_overlap.py:19`
- Modify: `observepoint-revenue/skills/find-accounts/SKILL.md:19,35`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `lib/salesforce/sf_io.py` exposing the unchanged API — `parse_records(mcp_result) -> list`, `normalize_domain(url_or_host) -> str`, `SalesforceResultError(ValueError)`. Importable as `import sf_io` once `lib/salesforce` is on sys.path. Reference doc at `lib/salesforce/salesforce-org.md`.

- [ ] **Step 1: Baseline — run the full suite green before touching anything**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q`
Expected: PASS (338 passed). Record the number; it must not drop.

- [ ] **Step 2: Move the two artifacts and the manifest with git (preserve history)**

```bash
cd "observepoint-revenue"
mkdir -p lib/salesforce
git mv skills/salesforce-core/scripts/sf_io.py            lib/salesforce/sf_io.py
git mv skills/salesforce-core/references/salesforce-org.md lib/salesforce/salesforce-org.md
git mv skills/salesforce-core/SKILL.md                     lib/salesforce/README.md
rm -rf skills/salesforce-core      # remove now-empty scripts/, references/, __pycache__
```

- [ ] **Step 3: Strip the YAML frontmatter from the new README**

Edit `observepoint-revenue/lib/salesforce/README.md`: delete the leading `---` … `---` frontmatter block (the `name:`/`description:` lines that made it a skill). Keep the body. Add one line at the top so its nature is unambiguous:

```markdown
# lib/salesforce — shared read-side Salesforce foundation (library, not a skill)

Referenced by path: skills read `salesforce-org.md` and `import sf_io` via a relative-path
shim (`parents[3] / "lib" / "salesforce"`) / the `tests/conftest.py` sys.path entry.
```

- [ ] **Step 4: Repoint the test sys.path**

In `observepoint-revenue/tests/conftest.py`, change line 9:

```python
    "skills/salesforce-core/scripts",
```
to:
```python
    "lib/salesforce",
```

- [ ] **Step 5: Repoint the two find-accounts script shims**

In `observepoint-revenue/skills/find-accounts/scripts/resolve_territory.py`, change line 14 from:

```python
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "salesforce-core" / "scripts"))
```
to:
```python
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib" / "salesforce"))
```

And its docstring line 3 (`see salesforce-core/references/salesforce-org.md`) → `see lib/salesforce/salesforce-org.md`.

In `observepoint-revenue/skills/find-accounts/scripts/classify_overlap.py`, change line 19 identically (`parents[2] / "salesforce-core" / "scripts"` → `parents[3] / "lib" / "salesforce"`).

- [ ] **Step 6: Repoint the find-accounts SKILL.md read paths**

In `observepoint-revenue/skills/find-accounts/SKILL.md`, lines 19 and 35, change both occurrences of:

```
${CLAUDE_PLUGIN_ROOT}/skills/salesforce-core/references/salesforce-org.md
```
to:
```
${CLAUDE_PLUGIN_ROOT}/lib/salesforce/salesforce-org.md
```

- [ ] **Step 7: Run the full suite — verify still green**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q`
Expected: PASS, same count as Step 1 (338). `test_sf_io.py`, `test_resolve_territory.py`, `test_classify_overlap.py` all pass via the new path.

- [ ] **Step 8: Grep for any stale reference, then commit**

```bash
cd "observepoint-revenue"
grep -rn "salesforce-core" . --include=*.py --include=*.md && echo "STALE REFS ABOVE — fix before commit" || echo "clean"
```
Expected: `clean` (no matches outside intentional history). Then:

```bash
git add -A
git -c user.email="16406437+jpwilbur@users.noreply.github.com" commit -m "refactor: migrate salesforce-core skill into lib/salesforce library

Foundations are path-referenced libraries, not skills. Drop the SKILL.md (now a
README), move sf_io.py + salesforce-org.md to lib/salesforce, and repoint the three
path references (conftest, two find-accounts shims, find-accounts SKILL.md reads).
No behavior change; suite stays green.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Drop `salesforce-core` from the manifests + CLAUDE.md

Prose-only follow-up: stop listing salesforce-core as one of the skills now that it's a library. Separate from Task 1 so a reviewer can approve the code move independently of the doc wording.

**Files:**
- Modify: `observepoint-revenue/.claude-plugin/plugin.json:8` (description string)
- Modify: `.claude-plugin/marketplace.json:15` (description string)
- Modify: `CLAUDE.md` (the "## Skills (7)" header + the `salesforce-core` bullet)

**Interfaces:**
- Consumes: Task 1 (the library exists at `lib/salesforce`).
- Produces: nothing code-facing.

- [ ] **Step 1: Trim both manifest description strings**

In both `observepoint-revenue/.claude-plugin/plugin.json` (line 8) and `.claude-plugin/marketplace.json` (line 15), remove the trailing clause that enumerates salesforce-core as a skill:

`", and salesforce-core (shared read-side Salesforce foundation: org map + sf_io)"` → delete it (end the sentence after the `op-mcp-post-mortem` clause). The plugin description must stay under the 500-char upload cap (it already is; this only shortens it).

- [ ] **Step 2: Update CLAUDE.md**

In `CLAUDE.md`: change the `## Skills (7)` heading to `## Skills (6) + shared libraries`. Move the `salesforce-core` bullet out of the skill list into a new short section:

```markdown
## Shared libraries (`lib/`, not skills — no SKILL.md, referenced by path)

- **`lib/salesforce`** — read-side Salesforce foundation: the canonical org map
  (`salesforce-org.md`) + `sf_io.py` (digests SF MCP result JSON). Imported by find-accounts
  (and, later, revenue-insights) via a relative-path shim. Read-only.
```

(Leave the `## Dev` note about `tests/conftest.py` adding scripts dirs to sys.path; it's still accurate — the list now includes `lib/salesforce`.)

- [ ] **Step 3: Verify nothing references salesforce-core as a skill, then commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
grep -rn "salesforce-core" CLAUDE.md observepoint-revenue/.claude-plugin .claude-plugin && echo "CHECK matches" || echo "clean"
```
Expected: `clean`. Then:

```bash
git add CLAUDE.md observepoint-revenue/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git -c user.email="16406437+jpwilbur@users.noreply.github.com" commit -m "docs: list lib/salesforce as a library, not a skill (manifests + CLAUDE.md)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Discover the Domo dataset map (read-only probe → `lib/domo/domo-datasets.md` + fixtures)

A **discovery task** (research + documentation, not TDD). Inventory the Domo warehouse read-only, capture real result JSON for the metrics the four seed recipes need, and write the canonical map. Its output unblocks `domo_io.py` (Task 4) and Plan 3's recipes. **Never fabricate** a dataset, column, or value — if something isn't found, write "not found in Domo — to confirm with rev ops."

**Files:**
- Create: `observepoint-revenue/lib/domo/domo-datasets.md`
- Create: `observepoint-revenue/tests/fixtures/domo/` (**synthetic** result JSON — real envelope/columns, fake values — 1 per probed dataset)

**Interfaces:**
- Consumes: the Domo MCP (`SearchTool`, `DomoSqlQueryTool`, `FileSetQueryTool`).
- Produces: `domo-datasets.md` (named queries + which dataset is authoritative per metric + the result-envelope shape) and `tests/fixtures/domo/*.json` (synthetic fixtures for Task 4's tests and Plan 3's recipe tests).

**Data hygiene:** do **not** commit raw warehouse rows (real ARR / account names / revenue) to git. Read a tiny live sample only to learn the **envelope + column shape**, then hand-author synthetic fixtures with the real column names/types and representative fake values.

- [ ] **Step 1: Inventory datasets**

Use the Domo MCP `SearchTool` to list available datasets. Capture the names/ids and one-line purpose of each candidate that could feed the seed recipes:
- **ARR / NRR / GRR** (board): a dataset with ARR by account/period and movement (new/expansion/contraction/churn).
- **Quota / targets / plan** (coverage, attainment, pacing) — *this is the open question from the spec*: find where quota lives (Domo dataset? a column on a sales dataset?).
- **Renewals / forecast** (cross-check vs SF `Renewal_Forecast__c`): any curated renewal dataset.
- **Pipeline / bookings** trend (VP Sales): historical pipeline/bookings if present.

- [ ] **Step 2: Confirm columns + envelope shape (LIMIT-guarded, read-only) → author synthetic fixtures**

For each candidate dataset, run a small `DomoSqlQueryTool` read (e.g. `SELECT * FROM <dataset> LIMIT 5`) to confirm column names/types and the **result-envelope shape** (top-level keys: e.g. `rows`/`columns`/`data`/`metadata`). Record the envelope keys (Task 4's `parse_query_result` is written against them). Then **hand-author a synthetic fixture** per dataset at `observepoint-revenue/tests/fixtures/domo/<short-name>.json` — same envelope + real column names/types, **fake values** (no real ARR / account names). These are Task 4's parser fixtures and Plan 3's recipe fixtures.

- [ ] **Step 3: Confirm fiscal calendar + currency**

Determine the **fiscal year start** (spec implies Feb 1 from "Q2 FY26 = May 1–Jul 31") — confirm against a Domo date/period column or a fiscal-calendar dataset. Note whether any dataset carries **FX rates** (needed before any cross-currency total is ever computed).

- [ ] **Step 4: Write `lib/domo/domo-datasets.md`**

Author the canonical map, structured like `lib/salesforce/salesforce-org.md`:
- A **header** declaring it a library (not a skill), read-only, model-gathers/scripts-compute.
- **Datasets** section: each dataset's id, purpose, key columns (name + type), refresh cadence, and **which metric it is authoritative for**.
- **Named queries** section: the exact `DomoSqlQueryTool` SQL each seed recipe will run (ARR/NRR bridge inputs; pipeline/quota for coverage; renewal cross-check). Only queries confirmed to run in Step 2.
- **Hygiene/caveats**: stale-as-of dates, known dirty columns, the FX-availability finding, the fiscal-year-start finding, and **where quota lives** (or "not found — confirm with rev ops").
- **Result-envelope shape**: document the top-level keys for `domo_io` to parse.

- [ ] **Step 5: Commit the map + fixtures**

```bash
cd "observepoint-revenue"
git add lib/domo/domo-datasets.md tests/fixtures/domo/
git -c user.email="16406437+jpwilbur@users.noreply.github.com" commit -m "docs(lib/domo): canonical Domo dataset map + captured fixtures (read-only probe)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `lib/domo/domo_io.py` — deterministic Domo result digester + tests

Mirror `lib/salesforce/sf_io.py`: validate/extract rows from the Domo MCP envelope and coerce types. Tested against the **real fixtures captured in Task 3**, so the parser matches the actual envelope.

**Files:**
- Create: `observepoint-revenue/lib/domo/domo_io.py`
- Create: `observepoint-revenue/tests/test_domo_io.py`
- Modify: `observepoint-revenue/tests/conftest.py` (add `"lib/domo"` to the sys.path list)

**Interfaces:**
- Consumes: Task 3 synthetic fixtures (`tests/fixtures/domo/*.json`); the documented envelope shape.
- Produces: `domo_io.py` exposing `parse_query_result(mcp_result) -> list[dict]` (one dict per row), `coerce_number(value) -> float|None`, `coerce_date(value) -> str|None` (ISO `YYYY-MM-DD` or None), and `DomoResultError(ValueError)`. Importable as `import domo_io` once `lib/domo` is on sys.path.

- [ ] **Step 1: Add `lib/domo` to the test sys.path**

In `observepoint-revenue/tests/conftest.py`, add to the tuple (after the `lib/salesforce` entry):

```python
    "lib/domo",
```

- [ ] **Step 2: Write the failing tests**

Create `observepoint-revenue/tests/test_domo_io.py`. The first test loads a **real captured fixture** so the parser is validated against the true envelope; the rest pin the contract:

```python
import json
import pathlib
import pytest
import domo_io

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "domo"


def _load(name):
    return json.loads((FIXTURES / name).read_text())


def test_parses_a_representative_envelope_into_row_dicts():
    # Use any one synthetic fixture authored in Task 3 (real envelope shape, fake values).
    fixture = sorted(FIXTURES.glob("*.json"))[0]
    rows = domo_io.parse_query_result(json.loads(fixture.read_text()))
    assert isinstance(rows, list)
    assert rows and isinstance(rows[0], dict)


def test_passthrough_list_of_dicts():
    rows = [{"a": 1}, {"a": 2}]
    assert domo_io.parse_query_result(rows) == rows


def test_columns_plus_rows_envelope_zips_to_dicts():
    env = {"columns": ["arr", "stage"], "rows": [[100, "Closed Won"], [200, "Commit"]]}
    assert domo_io.parse_query_result(env) == [
        {"arr": 100, "stage": "Closed Won"},
        {"arr": 200, "stage": "Commit"},
    ]


def test_error_envelope_raises():
    with pytest.raises(domo_io.DomoResultError):
        domo_io.parse_query_result({"error": "bad query"})


def test_unrecognized_shape_raises():
    with pytest.raises(domo_io.DomoResultError):
        domo_io.parse_query_result(42)


def test_coerce_number_handles_currency_strings_and_blanks():
    assert domo_io.coerce_number("$1,234.50") == 1234.5
    assert domo_io.coerce_number("") is None
    assert domo_io.coerce_number(None) is None
    assert domo_io.coerce_number("12%") == 12.0


def test_coerce_date_normalizes_to_iso():
    assert domo_io.coerce_date("2026-05-01T00:00:00") == "2026-05-01"
    assert domo_io.coerce_date("") is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_domo_io.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'domo_io'`.

- [ ] **Step 4: Implement `domo_io.py`**

Create `observepoint-revenue/lib/domo/domo_io.py`. **If the synthetic fixture's envelope uses a key not handled below, extend `parse_query_result` to that key** — the fixture (which mirrors the real Domo envelope from the probe) is the source of truth:

```python
"""Deterministic helpers for digesting Domo MCP results (read side).

The MODEL calls the Domo MCP (gather); this module only parses/normalizes the JSON
it returns (compute). Nothing here calls Domo. Shared via the lib/domo sys.path entry
(tests) or a relative-path shim (runtime CLI). Mirrors lib/salesforce/sf_io.py.
"""
import re


class DomoResultError(ValueError):
    """A Domo MCP result that isn't a usable query-success envelope."""


def parse_query_result(mcp_result):
    """Return a list of row dicts from a DomoSqlQueryTool/FileSetQueryTool result.

    Handles the shapes Domo returns: an already-extracted list of dicts; a
    {"columns":[...], "rows":[[...], ...]} envelope (zipped to dicts); a nested
    {"data": <one of the above>} wrapper. Raises DomoResultError on an error envelope
    or unrecognized shape so callers fall back cleanly instead of computing on garbage.
    """
    if isinstance(mcp_result, list):
        return mcp_result
    if not isinstance(mcp_result, dict):
        raise DomoResultError(f"expected dict or list, got {type(mcp_result).__name__}")
    if "error" in mcp_result:
        raise DomoResultError(str(mcp_result["error"]))
    if "data" in mcp_result:
        return parse_query_result(mcp_result["data"])
    rows = mcp_result.get("rows")
    cols = mcp_result.get("columns")
    if isinstance(rows, list):
        if cols and rows and isinstance(rows[0], (list, tuple)):
            names = [c if isinstance(c, str) else c.get("name") for c in cols]
            return [dict(zip(names, r)) for r in rows]
        if all(isinstance(r, dict) for r in rows):
            return rows
    raise DomoResultError("no usable rows — not a Domo query-success envelope")


_NUM = re.compile(r"[^0-9.\-]")


def coerce_number(value):
    """Best-effort float from a number or a currency/percent string. '' / None -> None."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = _NUM.sub("", str(value))
    if cleaned in ("", "-", ".", "-."):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def coerce_date(value):
    """ISO YYYY-MM-DD from a date or ISO-ish datetime string. '' / None -> None."""
    if not value:
        return None
    return str(value).strip()[:10]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_domo_io.py -v`
Expected: PASS (all tests). If `test_parses_a_representative_envelope_into_row_dicts` fails, adjust `parse_query_result` to the fixture's actual envelope keys and re-run.

- [ ] **Step 6: Run the full suite + commit**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q`
Expected: PASS (now 345+: 338 baseline + the new `test_domo_io` cases).

```bash
cd "observepoint-revenue"
git add lib/domo/domo_io.py tests/test_domo_io.py tests/conftest.py
git -c user.email="16406437+jpwilbur@users.noreply.github.com" commit -m "feat(lib/domo): domo_io result digester + tests against captured fixtures

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Discover the SF renewal/health schema (read-only) → org-map entry + synthetic fixture

A **discovery task** that unblocks Plan 2's renewals-at-risk anchor. The spec lists the renewal shape as to-verify: the object/field behind `Renewal_Forecast__c`, the health-score field, `Renewable_ARR__c`, close date, and currency. Confirm them live (read-only), document them in the SF org map, and author a synthetic fixture for Plan 2's recipe tests. **Never fabricate** a field name — if one isn't found, record "not found — confirm with rev ops."

**Files:**
- Modify: `observepoint-revenue/lib/salesforce/salesforce-org.md` (add a "Renewals (revenue-insights)" section)
- Create: `observepoint-revenue/tests/fixtures/sf/renewals_sample.json` (**synthetic** — real fields, fake accounts/ARR)

**Interfaces:**
- Consumes: the Salesforce MCP (`getObjectSchema`, `soqlQuery`); `lib/salesforce` from Task 1.
- Produces: a documented renewal query + a normalized-record field map (which raw SF field → the recipe's `account`/`status`/`health`/`arr`/`currency`/`close_date` keys) that Plan 2 Task 3 consumes; a synthetic SF-shaped fixture.

- [ ] **Step 1: Find the renewal object + fields**

Run `getObjectSchema` on the likely renewal carrier (start with `Opportunity`; if `Renewal_Forecast__c` isn't there, search custom objects). Confirm the API names for: the renewal-forecast status (`Renewal_Forecast__c` — its picklist values, e.g. Will Renew / Undetermined / Will Not Renew), the **renewable ARR** field (`Renewable_ARR__c`), the **health-score** field (the Green/Yellow/Red/Black field — find its API name + values), `CloseDate`, account name (`Account.Name`), and `CurrencyIsoCode`.

- [ ] **Step 2: Confirm the query runs (LIMIT-guarded, read-only)**

Run a small `soqlQuery` (e.g. `SELECT Account.Name, Renewal_Forecast__c, <HealthField>, Renewable_ARR__c, CloseDate, CurrencyIsoCode FROM <object> WHERE <renewal filter> LIMIT 5`) to confirm field names resolve and note the result envelope (standard SOQL `{records:[...]}`, already handled by `sf_io.parse_records`).

- [ ] **Step 3: Author the synthetic fixture**

Write `observepoint-revenue/tests/fixtures/sf/renewals_sample.json` — a `{"records":[...]}` SOQL envelope with the **real field names** but **synthetic** rows engineered to exercise Plan 2's recipe:
- mixed currency (USD + GBP rows),
- all three statuses (Will Renew / Undetermined / Will Not Renew),
- mixed health (Green / Yellow / Red / Black),
- the **Green-but-Will-Not-Renew** edge (a row with health Green and status Will Not Renew → drives the auto-caveat),
- in-window and out-of-window close dates.

- [ ] **Step 4: Document it in the SF org map**

Add a "Renewals (revenue-insights)" section to `observepoint-revenue/lib/salesforce/salesforce-org.md`: the confirmed object/fields, the picklist values for status and health, the **named renewal query**, and the **field map** (raw SF field → normalized recipe key: `Account.Name`→`account`, `Renewal_Forecast__c`→`status`, `<HealthField>`→`health`, `Renewable_ARR__c`→`arr`, `CurrencyIsoCode`→`currency`, `CloseDate`→`close_date`). Plan 2 Task 3's mapper uses this map.

- [ ] **Step 5: Commit**

```bash
cd "observepoint-revenue"
git add lib/salesforce/salesforce-org.md tests/fixtures/sf/renewals_sample.json
git -c user.email="16406437+jpwilbur@users.noreply.github.com" commit -m "docs(lib/salesforce): renewal/health schema + synthetic fixture (read-only probe)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage (Plan 1 scope):**
- *Foundations are libraries under `lib/`, no `SKILL.md`* → Tasks 1–2 (salesforce migration), Task 4 (domo_io in `lib/domo`). ✓
- *Migrate `salesforce-core` incl. the three path refs + manifests + CLAUDE.md, suite green* → Task 1 (paths, tests) + Task 2 (manifests/CLAUDE.md). ✓
- *`lib/domo` = `domo-datasets.md` + `domo_io.py`* → Tasks 3–4. ✓
- *Live read-only Domo probe; discover quota location + fiscal year + FX* → Task 3 explicitly. ✓
- *Discover the SF renewal/health schema (assumptions-to-verify)* → Task 5. ✓
- *Tests against fixture MCP JSON, no live source in suite; never fabricate* → Tasks 4–5 use **synthetic** fixtures (real shape, fake values), so no live revenue data lands in git. ✓
- *Read-only throughout* → no create/update calls anywhere. ✓

**Placeholder scan:** Tasks 3 & 5 are discovery tasks (no fabricated code/values — synthetic fixtures are explicitly authored from the real shape); Task 4's parser is concrete with a fixture-driven adjustment note, not a TODO. No "TBD"/"add error handling"/"similar to" placeholders. ✓

**Type consistency:** `sf_io.parse_records`/`normalize_domain`/`SalesforceResultError` unchanged by the move; `domo_io.parse_query_result`/`coerce_number`/`coerce_date`/`DomoResultError` used consistently in tests and impl; the normalized renewal keys (`account`/`status`/`health`/`arr`/`currency`/`close_date`) defined in Task 5 are exactly what Plan 2 Task 3 consumes; `parents[3] / "lib" / "salesforce"` and `conftest` entries `"lib/salesforce"`,`"lib/domo"` agree on `observepoint-revenue/lib/`. ✓

## Execution Handoff

This is Plan 1 of 3. Plan 2 (engine + renewals-at-risk anchor) is authored next and consumes Task 5's renewal field map + fixture; Plan 3 (remaining three recipes) is authored after the Task 3 probe so its Domo/OP queries are real.
