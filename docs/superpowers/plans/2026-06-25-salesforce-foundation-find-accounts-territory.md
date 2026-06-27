# Salesforce foundation + find-accounts territory — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace find-accounts' hand-maintained `territory.md` with a live Salesforce-derived territory boundary and an "own hard, others flagged" overlap-guard, built on a new shared `salesforce-core` read foundation.

**Architecture:** The model calls the Salesforce MCP (the *gather* step); deterministic Python only digests the returned JSON (the *compute* step). A new `salesforce-core` skill hosts the canonical org map + `sf_io.py`. find-accounts gains `resolve_territory.py` (territory boundary) and `classify_overlap.py` (overlap policy), and `rank_candidates.py` learns to display an `sf_status` annotation. Read-only — no Salesforce writes in this plan.

**Tech Stack:** Python 3 (stdlib + openpyxl, already a dep), pytest, the Salesforce MCP (server id `9d60ec8c-…`; read tools `getUserInfo`, `soqlQuery`, `find`).

## Global Constraints

- **Interpreter:** always `/opt/homebrew/bin/python3` — bare `python3` may resolve to CLT 3.9 with no pytest/openpyxl.
- **Test command:** `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q` (currently 291 passing). Never pipe pytest through `| tail` in an `&&` chain.
- **Architecture principle (do not break):** Claude gathers via the MCP; deterministic scripts compute on the returned JSON. No Python script calls Salesforce. No LLM math, no LLM-maintained state.
- **Read-only:** this plan performs zero SF writes (no `create`/`update`). Writes are a later roadmap item gated on a rev-ops governance contract.
- **No live SF in tests:** every test runs against inline fixture JSON shaped like real MCP results.
- **Never fabricate** a number, domain, contact, or source.
- **Cross-skill import shim** (runtime CLI; conftest covers tests): a consuming script in `find-accounts/scripts` reaches `sf_io` via
  ```python
  import pathlib, sys
  sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "salesforce-core" / "scripts"))
  import sf_io  # noqa: E402
  ```
- **Execution happens on a feature branch / worktree** (per superpowers:using-git-worktrees), not `main`.
- **Commit author email:** `16406437+jpwilbur@users.noreply.github.com`.

---

### Task 1: `salesforce-core` foundation (SKILL.md, org map, `sf_io.py`)

**Files:**
- Create: `observepoint-revenue/skills/salesforce-core/SKILL.md`
- Create: `observepoint-revenue/skills/salesforce-core/references/salesforce-org.md`
- Create: `observepoint-revenue/skills/salesforce-core/scripts/sf_io.py`
- Modify: `observepoint-revenue/tests/conftest.py` (add the new scripts dir)
- Test: `observepoint-revenue/tests/test_sf_io.py`

**Interfaces:**
- Produces: `sf_io.parse_records(mcp_result) -> list[dict]` (raises `sf_io.SalesforceResultError`); `sf_io.normalize_domain(url_or_host: str|None) -> str`.

- [ ] **Step 1: Add the scripts dir to the test path**

In `observepoint-revenue/tests/conftest.py`, add `"skills/salesforce-core/scripts",` to the `rel` tuple (put it first so `sf_io` is importable):

```python
for rel in (
    "skills/salesforce-core/scripts",
    "skills/scope-calculator/scripts",
    "skills/research-account/scripts",
    "skills/owned-properties/scripts",
    "skills/find-accounts/scripts",
    "skills/branding-guide/scripts",
    "skills/op-mcp-post-mortem/scripts",
):
```

- [ ] **Step 2: Write the failing test**

Create `observepoint-revenue/tests/test_sf_io.py`:

```python
import pytest
import sf_io


def test_parse_records_success_dict():
    assert sf_io.parse_records({"records": [{"Id": "1"}], "done": True, "totalSize": 1}) == [{"Id": "1"}]


def test_parse_records_list_passthrough():
    assert sf_io.parse_records([{"Id": "1"}]) == [{"Id": "1"}]


def test_parse_records_error_envelope_raises():
    with pytest.raises(sf_io.SalesforceResultError):
        sf_io.parse_records({"error": "Tool call timed out waiting for server response."})


def test_parse_records_missing_records_raises():
    with pytest.raises(sf_io.SalesforceResultError):
        sf_io.parse_records({"totalSize": 0, "done": True})


def test_parse_records_non_dict_raises():
    with pytest.raises(sf_io.SalesforceResultError):
        sf_io.parse_records("nope")


def test_normalize_domain_strips_scheme_www_path():
    assert sf_io.normalize_domain("https://www.Acme-Corp.com/path?q=1") == "acme-corp.com"


def test_normalize_domain_bare_host_and_port():
    assert sf_io.normalize_domain("Acme.com:443") == "acme.com"


def test_normalize_domain_keeps_subdomain():
    assert sf_io.normalize_domain("https://shop.acme.com") == "shop.acme.com"


def test_normalize_domain_empty_and_none():
    assert sf_io.normalize_domain("") == ""
    assert sf_io.normalize_domain(None) == ""
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_sf_io.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sf_io'`.

- [ ] **Step 4: Write `sf_io.py`**

Create `observepoint-revenue/skills/salesforce-core/scripts/sf_io.py`:

```python
"""Deterministic helpers for digesting Salesforce MCP results (read side).

The MODEL calls the Salesforce MCP (the gather step); this module only parses and
normalizes the JSON it returns (the compute step). Nothing here calls Salesforce.
Shared across SF-backed skills via the skills/salesforce-core/scripts sys.path entry
(tests) or a relative-path shim (runtime CLI).
"""
import re


class SalesforceResultError(ValueError):
    """An MCP result that isn't a usable SOQL/SOSL success envelope."""


def parse_records(mcp_result):
    """Return the records list from a soqlQuery/find result.

    Accepts the dict the MCP returns ({"records": [...], "done": true, ...}) or an
    already-extracted list. Raises SalesforceResultError on an error envelope or an
    unrecognized shape, so callers fall back cleanly instead of computing on garbage.
    """
    if isinstance(mcp_result, list):
        return mcp_result
    if not isinstance(mcp_result, dict):
        raise SalesforceResultError(f"expected dict or list, got {type(mcp_result).__name__}")
    if "error" in mcp_result:
        raise SalesforceResultError(str(mcp_result["error"]))
    recs = mcp_result.get("records")
    if not isinstance(recs, list):
        raise SalesforceResultError("no 'records' list — not a SOQL success envelope")
    return recs


_SCHEME = re.compile(r"^[a-z][a-z0-9+.\-]*://", re.I)


def normalize_domain(url_or_host):
    """Bare, comparable host for account matching.

    'https://www.Acme-Corp.com/path?q=1' -> 'acme-corp.com'. Lowercases; drops scheme,
    userinfo, leading 'www.', port, path/query/fragment, and surrounding dots/space.
    Returns '' for falsy/junk input (a candidate with no usable domain won't match by domain).
    """
    if not url_or_host:
        return ""
    s = str(url_or_host).strip().lower()
    s = _SCHEME.sub("", s)
    s = s.split("@")[-1]
    s = re.split(r"[/?#]", s, 1)[0]
    s = s.split(":")[0]
    if s.startswith("www."):
        s = s[4:]
    return s.strip(". ")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_sf_io.py -q`
Expected: PASS (9 passed).

- [ ] **Step 6: Write the `salesforce-org.md` canonical map**

Create `observepoint-revenue/skills/salesforce-core/references/salesforce-org.md`:

````markdown
# ObservePoint Salesforce — canonical org map (read side)

How this plugin reads the ObservePoint SF org. The MODEL runs these queries via the
Salesforce MCP; scripts only digest the JSON. **Read-only** — no write queries here yet.

## Field hygiene (read before writing SOQL)
- `Account.Region__c` is labeled **"Region (OLD DONT USE)"** → use `Country_Region__c`
  (label "Region"), `Continental_Region__c`, or `Sub_Region__c`.
- Confirm the canonical ARR field (`ARR__c` vs `Calc_ARR__c`) via `getObjectSchema` admin
  guidance before trusting either. (Not used by find-accounts.)
- `getObjectSchema` returns admin-authored guidance — read it before constructing queries.

## Territories — `OP_Territories__c`
Only **AEs and ADMs** have territories. Accounts link via `Account.OP_Territory__c`.
Fields: `AE__c`, `ADM__c`, `CSM__c` (User refs), `Segment__c` (Enterprise/Corporate/Partner),
`World_Region__c`, `Sub_Region__c`, `Country__c`, `State__c`, `Name`/`Name__c`.

**Named query — a target's territory** (key on the target's *actual* role; never assume AE≡ADM):
```sql
SELECT Id, Name, Name__c, Segment__c, World_Region__c, Sub_Region__c,
       Country__c, State__c, AE__r.Name, ADM__r.Name, CSM__r.Name
FROM OP_Territories__c
WHERE AE__c = :targetUserId          -- or ADM__c = :targetUserId
```

**Named query — resolve a target user by email** (when the runner isn't the target):
```sql
SELECT Id, Name, Email FROM User WHERE Email = :email AND IsActive = true
```

## Accounts (overlap-guard)
`Account.Type` ∈ {Customer, Prospect, Previous Customer, Partner, Prospective Partner,
Previous Partner, Defunct}. `OwnerId`/`Owner.Name`, `Website`, `OP_Territory__c`, `Industry`.
**AEs can own named accounts outside their territory** → match on `OwnerId`, not just territory.

**Named query — match swept candidates to existing accounts** (domain-first):
```sql
SELECT Id, Name, Website, Type, OwnerId, Owner.Name, OP_Territory__c, Industry
FROM Account
WHERE Website IN (:candidateDomains)
```
For candidates with no website match, fall back to a name search:
```
FIND {"Acme*"} IN NAME FIELDS RETURNING Account(Id, Name, Website, Type, OwnerId, OP_Territory__c)
```

## Bridges (reserved for later items — NOT used by find-accounts)
- `Account.OP_Account_ID__c` / `OP_App_ID__c` → the ObservePoint platform account.
- Gong is synced into SF (`Gong__Gong_Call__c`, `Gong__Note__c`, `Gong__Gong_Scorecard__c`, …).
- `Product_Adoption_Whitespace__c` + `Account.OP_Product_Lines__c` for expansion.
````

- [ ] **Step 7: Write the `salesforce-core` SKILL.md**

Create `observepoint-revenue/skills/salesforce-core/SKILL.md`:

```markdown
---
name: salesforce-core
description: Shared read-side Salesforce foundation for the revenue plugin — the canonical org map, the named SOQL/SOSL queries other skills run, and sf_io.py (the deterministic helper that digests Salesforce MCP results). Not a standalone task; read/imported by find-accounts (territory + overlap-guard) and, later, research-account write-back, the CSM review builder, and expansion radar. Use it to look up how this org is modeled or which query to run; it does NOT itself sell, scope, or research.
---

# Salesforce Core (shared read foundation)

The single place that knows how ObservePoint's Salesforce org is shaped and how this plugin reads it.

**Architecture rule (do not break):** the MODEL calls the Salesforce MCP (the *gather* step);
deterministic Python only parses the returned JSON (the *compute* step). No Python script calls
Salesforce; no model arithmetic; no model-held state. **Read-only today** — there are no write
helpers here yet. Writes (research-account → SF, the scope page-count field) are deferred and gated
on a rev-ops owned-custom-fields governance contract; they will arrive as payload builders in
`sf_io.py` with their own design.

## What's here
- **`references/salesforce-org.md`** — the canonical org map: objects/fields this plugin reads, the
  field-hygiene rules, and the named queries (territory, user lookup, account-match). Read it before
  writing any SOQL against this org. When the org schema changes, change that file.
- **`scripts/sf_io.py`** — `parse_records(mcp_result)` (validate + extract a SOQL/SOSL record list)
  and `normalize_domain(url_or_host)` (comparable host for account matching). Imported by SF-backed
  skills: `skills/salesforce-core/scripts` is on the test sys.path; CLI scripts add it via a
  relative-path shim.

## Using it from another skill
1. Read `references/salesforce-org.md` for the query you need.
2. Have the model run that query via the Salesforce MCP (`soqlQuery` / `find` / `getUserInfo`).
3. Pass the returned JSON to the consuming skill's script, which uses `sf_io` to digest it.
```

- [ ] **Step 8: Run the full suite, then commit**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q`
Expected: all green (291 prior + 9 new).

```bash
git add observepoint-revenue/skills/salesforce-core observepoint-revenue/tests/conftest.py observepoint-revenue/tests/test_sf_io.py
git commit -m "feat(salesforce-core): shared read foundation (org map + sf_io)"
```

---

### Task 2: `resolve_territory.py` — territory SOQL → normalized boundary

**Files:**
- Create: `observepoint-revenue/skills/find-accounts/scripts/resolve_territory.py`
- Test: `observepoint-revenue/tests/test_resolve_territory.py`

**Interfaces:**
- Consumes: `sf_io.parse_records` (Task 1).
- Produces: `resolve_territory.normalize_territory(mcp_result) -> dict` with keys
  `territory_ids, regions, sub_regions, countries, states, segments, ae_names, adm_names, csm_names`.
  CLI prints that dict as JSON.

- [ ] **Step 1: Write the failing test**

Create `observepoint-revenue/tests/test_resolve_territory.py`:

```python
import json
import pathlib
import subprocess
import sys

import resolve_territory as rt


def _terr(**kw):
    base = {"Id": "a0X1", "World_Region__c": "AMER", "Sub_Region__c": "US West",
            "Country__c": "United States", "State__c": "California", "Segment__c": "Enterprise",
            "AE__r": {"Name": "Dana AE"}, "ADM__r": {"Name": "Sam ADM"}, "CSM__r": None}
    base.update(kw)
    return base


def test_normalize_collects_unique_sorted():
    res = {"records": [_terr(), _terr(Id="a0X2", State__c="Nevada")], "done": True}
    b = rt.normalize_territory(res)
    assert b["territory_ids"] == ["a0X1", "a0X2"]
    assert b["states"] == ["California", "Nevada"]
    assert b["regions"] == ["AMER"]
    assert b["segments"] == ["Enterprise"]
    assert b["ae_names"] == ["Dana AE"]
    assert b["csm_names"] == []          # a None relationship is tolerated


def test_empty_result_is_empty_boundary():
    b = rt.normalize_territory({"records": [], "done": True})
    assert b["territory_ids"] == [] and b["regions"] == []


def test_cli_prints_boundary(tmp_path):
    f = tmp_path / "t.json"
    f.write_text(json.dumps({"records": [_terr()], "done": True}))
    script = pathlib.Path(rt.__file__).resolve().parent / "resolve_territory.py"
    res = subprocess.run([sys.executable, str(script), str(f)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["countries"] == ["United States"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_resolve_territory.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'resolve_territory'`.

- [ ] **Step 3: Write `resolve_territory.py`**

Create `observepoint-revenue/skills/find-accounts/scripts/resolve_territory.py`:

```python
"""Normalize an OP_Territories__c SOQL result into a find-accounts territory boundary.

The MODEL runs the territory query (see salesforce-core/references/salesforce-org.md) and
passes its JSON here; this script computes the boundary the sweep is constrained to.
No Salesforce calls, no model math.

CLI:  resolve_territory.py <territory-soql.json>     # prints boundary JSON to stdout
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "salesforce-core" / "scripts"))
import sf_io  # noqa: E402


def _collect(records, key):
    """Sorted unique non-empty string values of `key` across records."""
    out = []
    for r in records:
        v = (r or {}).get(key)
        if isinstance(v, str):
            v = v.strip()
        if v and v not in out:
            out.append(v)
    return sorted(out)


def _rel_name(records, rel):
    """Sorted unique .Name values from a relationship field (e.g. AE__r.Name)."""
    out = []
    for r in records:
        sub = (r or {}).get(rel)
        n = (sub.get("Name") or "").strip() if isinstance(sub, dict) else ""
        if n and n not in out:
            out.append(n)
    return sorted(out)


def normalize_territory(mcp_result):
    """OP_Territories__c records -> boundary dict. An empty result -> all-empty boundary
    (territory_ids == []), which the skill treats as 'no territory — get an explicit target'."""
    records = sf_io.parse_records(mcp_result)
    return {
        "territory_ids": [r["Id"] for r in records if (r or {}).get("Id")],
        "regions": _collect(records, "World_Region__c"),
        "sub_regions": _collect(records, "Sub_Region__c"),
        "countries": _collect(records, "Country__c"),
        "states": _collect(records, "State__c"),
        "segments": _collect(records, "Segment__c"),
        "ae_names": _rel_name(records, "AE__r"),
        "adm_names": _rel_name(records, "ADM__r"),
        "csm_names": _rel_name(records, "CSM__r"),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Normalize an OP_Territories__c SOQL result.")
    ap.add_argument("territory_json", help="JSON file of the territory SOQL result")
    a = ap.parse_args(argv)
    try:
        data = json.loads(pathlib.Path(a.territory_json).read_text())
    except (OSError, ValueError) as e:
        sys.exit(f"could not read territory JSON {a.territory_json!r}: {e}")
    try:
        boundary = normalize_territory(data)
    except sf_io.SalesforceResultError as e:
        sys.exit(f"territory result unusable: {e}")
    print(json.dumps(boundary, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_resolve_territory.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add observepoint-revenue/skills/find-accounts/scripts/resolve_territory.py observepoint-revenue/tests/test_resolve_territory.py
git commit -m "feat(find-accounts): resolve_territory normalizes OP_Territories__c -> boundary"
```

---

### Task 3: `classify_overlap.py` — "own hard, others flagged"

**Files:**
- Create: `observepoint-revenue/skills/find-accounts/scripts/classify_overlap.py`
- Test: `observepoint-revenue/tests/test_classify_overlap.py`

**Interfaces:**
- Consumes: `sf_io.normalize_domain` (Task 1); `rank_candidates.normalize_name` (existing).
- Produces: `classify_overlap.classify(candidates, accounts, territory_ids, target_user_id) -> (kept, summary)`.
  `kept` = candidates minus hard-excludes, each with `sf_status` (None for net-new, else `{"owner","type"}`).
  `summary` = `{"kept": int, "hard_excluded": {"own_or_territory": [names], "customer": [names]}, "flagged": [names]}`.
  CLI writes annotated candidates JSON (same top-level shape, `candidates` replaced by `kept`).

- [ ] **Step 1: Write the failing test**

Create `observepoint-revenue/tests/test_classify_overlap.py`:

```python
import json
import pathlib
import subprocess
import sys

import classify_overlap as co

TERR_IDS = ["a0X1"]
TARGET = "005AAA"


def _acct(name, website, type_="Prospect", owner_id="005ZZZ", owner_name="Other Rep", terr=None):
    return {"Name": name, "Website": website, "Type": type_, "OwnerId": owner_id,
            "Owner": {"Name": owner_name}, "OP_Territory__c": terr}


def _cand(name, domain=None):
    c = {"name": name, "triggerKey": "pixelWiretapSuit", "sourceUrl": "https://x.test/a"}
    if domain:
        c["domain"] = domain
    return c


def test_net_new_kept_with_null_status():
    kept, summ = co.classify([_cand("New Co", "newco.com")], [], TERR_IDS, TARGET)
    assert len(kept) == 1 and kept[0]["sf_status"] is None
    assert summ["kept"] == 1


def test_in_territory_hard_excluded():
    accts = [_acct("Acme", "acme.com", terr="a0X1")]
    kept, summ = co.classify([_cand("Acme", "acme.com")], accts, TERR_IDS, TARGET)
    assert kept == []
    assert summ["hard_excluded"]["own_or_territory"] == ["Acme"]


def test_owned_by_target_hard_excluded_outside_territory():
    accts = [_acct("Named Co", "named.com", owner_id=TARGET, terr=None)]
    kept, summ = co.classify([_cand("Named Co", "named.com")], accts, TERR_IDS, TARGET)
    assert kept == []
    assert summ["hard_excluded"]["own_or_territory"] == ["Named Co"]


def test_customer_hard_excluded_any_owner():
    accts = [_acct("BigCust", "bigcust.com", type_="Customer", terr=None)]
    kept, summ = co.classify([_cand("BigCust", "bigcust.com")], accts, TERR_IDS, TARGET)
    assert kept == []
    assert summ["hard_excluded"]["customer"] == ["BigCust"]


def test_other_rep_prospect_flagged_not_dropped():
    accts = [_acct("Rival Owned", "rival.com", type_="Prospect", owner_name="Pat Other")]
    kept, summ = co.classify([_cand("Rival Owned", "rival.com")], accts, TERR_IDS, TARGET)
    assert len(kept) == 1
    assert kept[0]["sf_status"] == {"owner": "Pat Other", "type": "Prospect"}
    assert summ["flagged"] == ["Rival Owned"]


def test_name_fallback_when_no_domain():
    accts = [_acct("Example Health System Inc", "", type_="Prospect", owner_name="Pat")]
    kept, summ = co.classify([_cand("The Example Health-System, Inc.")], accts, TERR_IDS, TARGET)
    assert kept[0]["sf_status"]["owner"] == "Pat"


def test_cli_writes_annotated_and_summary(tmp_path):
    cands = {"date": "2026-06-25", "candidates": [_cand("New Co", "newco.com"),
                                                  _cand("BigCust", "bigcust.com")]}
    matches = {"records": [_acct("BigCust", "bigcust.com", type_="Customer")], "done": True}
    boundary = {"territory_ids": TERR_IDS}
    cf = tmp_path / "c.json"; cf.write_text(json.dumps(cands))
    mf = tmp_path / "m.json"; mf.write_text(json.dumps(matches))
    bf = tmp_path / "b.json"; bf.write_text(json.dumps(boundary))
    out = tmp_path / "annotated.json"
    script = pathlib.Path(co.__file__).resolve().parent / "classify_overlap.py"
    res = subprocess.run([sys.executable, str(script), str(cf), str(mf),
                          "--territory", str(bf), "--target-user", TARGET, "--out", str(out)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    data = json.loads(out.read_text())
    assert [c["name"] for c in data["candidates"]] == ["New Co"]   # customer hard-excluded
    assert data["date"] == "2026-06-25"                            # top-level keys preserved
    assert "hard-excluded" in res.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_classify_overlap.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'classify_overlap'`.

- [ ] **Step 3: Write `classify_overlap.py`**

Create `observepoint-revenue/skills/find-accounts/scripts/classify_overlap.py`:

```python
"""find-accounts overlap-guard: 'own hard, others flagged'.

Given the swept candidates, the Salesforce account-match result, the resolved territory
boundary, and the target AE/ADM user id, classify each candidate against SF:
  - hard-exclude  : in the target's territory OR owned by the target, OR Type == 'Customer'
  - flag (keep)   : exists in SF under another rep / a non-customer prospect/previous/defunct
  - net-new (keep): no SF match
Hard-excludes are removed; survivors get an `sf_status` that rank_candidates displays.
The MODEL gathers the SF data; this script only classifies. No Salesforce calls.

CLI:  classify_overlap.py <candidates.json> <sf-matches.json> --territory <boundary.json>
                          --target-user <UserId> [--out <annotated.json>]
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "salesforce-core" / "scripts"))
import sf_io  # noqa: E402
from rank_candidates import normalize_name  # noqa: E402  (same dir; on sys.path at runtime + via conftest)

HARD_EXCLUDE_TYPES = {"Customer"}


def _index(accounts):
    """domain -> account and normalized-name -> account lookup tables (first match wins)."""
    by_domain, by_name = {}, {}
    for a in accounts:
        dom = sf_io.normalize_domain((a or {}).get("Website"))
        if dom and dom not in by_domain:
            by_domain[dom] = a
        nm = normalize_name((a or {}).get("Name"))
        if nm and nm not in by_name:
            by_name[nm] = a
    return by_domain, by_name


def _match(cand, by_domain, by_name):
    """Domain match first (most reliable), then exact normalized-name fallback."""
    dom = sf_io.normalize_domain(cand.get("domain"))
    if dom and dom in by_domain:
        return by_domain[dom]
    nm = normalize_name(cand.get("name"))
    if nm and nm in by_name:
        return by_name[nm]
    return None


def classify(candidates, accounts, territory_ids, target_user_id):
    """Return (kept, summary). See module docstring for the policy."""
    tids = set(territory_ids or [])
    by_domain, by_name = _index(accounts or [])
    kept, flagged = [], []
    excluded = {"own_or_territory": [], "customer": []}
    for c in candidates or []:
        acct = _match(c, by_domain, by_name)
        if acct is None:
            entry = dict(c); entry["sf_status"] = None
            kept.append(entry); continue
        owner_obj = acct.get("Owner")
        owner = owner_obj.get("Name") if isinstance(owner_obj, dict) else None
        atype = acct.get("Type")
        in_terr = acct.get("OP_Territory__c") in tids
        owned = bool(target_user_id) and acct.get("OwnerId") == target_user_id
        if in_terr or owned:
            excluded["own_or_territory"].append(c.get("name")); continue
        if atype in HARD_EXCLUDE_TYPES:
            excluded["customer"].append(c.get("name")); continue
        entry = dict(c); entry["sf_status"] = {"owner": owner, "type": atype}
        kept.append(entry); flagged.append(c.get("name"))
    summary = {"kept": len(kept), "hard_excluded": excluded, "flagged": flagged}
    return kept, summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="find-accounts overlap-guard (own hard, others flagged).")
    ap.add_argument("candidates")
    ap.add_argument("sf_matches")
    ap.add_argument("--territory", required=True, help="boundary JSON from resolve_territory.py")
    ap.add_argument("--target-user", default="", help="target AE/ADM Salesforce UserId")
    ap.add_argument("--out", help="write annotated candidates JSON here (default: stdout)")
    a = ap.parse_args(argv)
    try:
        data = json.loads(pathlib.Path(a.candidates).read_text())
        boundary = json.loads(pathlib.Path(a.territory).read_text())
        raw_matches = json.loads(pathlib.Path(a.sf_matches).read_text())
    except (OSError, ValueError) as e:
        sys.exit(f"overlap-guard: could not read inputs: {e}")
    try:
        accounts = sf_io.parse_records(raw_matches)
    except sf_io.SalesforceResultError as e:
        sys.exit(f"overlap-guard: SF account-match result unusable: {e}")
    kept, summary = classify(data.get("candidates", []), accounts,
                             boundary.get("territory_ids", []), a.target_user)
    out_data = dict(data); out_data["candidates"] = kept
    payload = json.dumps(out_data, indent=2)
    if a.out:
        p = pathlib.Path(a.out); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(payload)
    else:
        print(payload)
    he = summary["hard_excluded"]
    print(f"overlap-guard: kept {summary['kept']} (hard-excluded "
          f"{len(he['own_or_territory'])} own/territory, {len(he['customer'])} customer; "
          f"flagged {len(summary['flagged'])} owned by others)", file=sys.stderr)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_classify_overlap.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add observepoint-revenue/skills/find-accounts/scripts/classify_overlap.py observepoint-revenue/tests/test_classify_overlap.py
git commit -m "feat(find-accounts): overlap-guard classifier (own hard, others flagged)"
```

---

### Task 4: `rank_candidates.py` — carry + display `sf_status`

**Files:**
- Modify: `observepoint-revenue/skills/find-accounts/scripts/rank_candidates.py` (`render_chat`, `RADAR_HEADERS`, `RADAR_WIDTHS`, `build_radar`)
- Modify: `observepoint-revenue/tests/test_rank_candidates.py` (new tests + update radar-column assertions)

**Interfaces:**
- Consumes: each candidate may carry `sf_status` (None or `{"owner","type"}`) set by Task 3. `rank()` already copies it via `entry = dict(c)`, so no change to `rank()`.
- Produces: chat shows an `already in SF — owner: …, type: …` line; the radar gains an "In SF?" column (position 9), shifting Pursue?→10 and Notes→11.

- [ ] **Step 1: Write the failing tests**

Add to `observepoint-revenue/tests/test_rank_candidates.py` (new block at the end):

```python
# ── Task: SF overlap status display ──────────────────────────────────────────

def test_sf_status_flag_carried_and_shown_in_chat():
    c = _cand("Rival Co")
    c["sf_status"] = {"owner": "Pat Other", "type": "Prospect"}
    ranked, dropped, _ = rc.rank(_data([c]), CONFIG)
    assert ranked[0]["sf_status"] == {"owner": "Pat Other", "type": "Prospect"}
    chat = rc.render_chat(ranked, dropped)
    assert "already in SF" in chat and "Pat Other" in chat and "Prospect" in chat


def test_no_sf_status_means_no_sf_chat_line():
    ranked, dropped, _ = rc.rank(_data([_cand("Clean Co")]), CONFIG)
    assert "already in SF" not in rc.render_chat(ranked, dropped)


def test_xlsx_in_sf_column_present_and_filled(tmp_path):
    from openpyxl import load_workbook
    c = _cand("Rival Co")
    c["sf_status"] = {"owner": "Pat Other", "type": "Prospect"}
    out = tmp_path / "radar.xlsx"
    res = _run_cli(tmp_path, _data([c]), "--xlsx", str(out))
    assert res.returncode == 0, res.stderr
    ws = load_workbook(out)["Discovery radar"]
    hdr = [cell.value for cell in ws[1]]
    assert hdr == ["Rank", "Company", "Vertical", "Trigger", "Trigger date", "Why now",
                   "Source", "First seen", "In SF?", "Pursue?", "Notes"]
    assert "Pat Other" in (ws.cell(row=2, column=9).value or "")     # In SF? populated
```

Update the two existing radar tests for the shifted columns:

In `test_xlsx_radar_columns_hyperlink_fillable`, change the header assertion to the 11-column list above and update the fillable-cell checks:
```python
    assert hdr == ["Rank", "Company", "Vertical", "Trigger", "Trigger date", "Why now",
                   "Source", "First seen", "In SF?", "Pursue?", "Notes"]
    assert ws.cell(row=2, column=9).value in (None, "")     # In SF? blank for a no-status candidate
    assert ws.cell(row=2, column=10).value in (None, "")    # Pursue? fillable (was col 9)
    assert ws.cell(row=2, column=11).value in (None, "")    # Notes fillable (was col 10)
```
(`test_xlsx_first_seen_marks_previously_seen_rows` reads First seen at index 7 by `values_only` tuple — unchanged, since "In SF?" is inserted *after* First seen.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_rank_candidates.py -q`
Expected: FAIL — new SF tests fail (no chat line / no "In SF?" column) and the updated radar test fails on the header list.

- [ ] **Step 3: Implement `sf_status` in `render_chat`**

In `observepoint-revenue/skills/find-accounts/scripts/rank_candidates.py`, in `render_chat`, after the `lines.append(f"   {e.get('sourceUrl', '')}")` line, add:

```python
        sf = e.get("sf_status")
        if sf:
            owner = sf.get("owner") or "another rep"
            atype = sf.get("type") or "unknown type"
            lines.append(f"   ⓘ already in SF — owner: {owner}, type: {atype} "
                         "(not yours — confirm before pursuing)")
```

- [ ] **Step 4: Add the "In SF?" radar column**

Replace `RADAR_HEADERS` and `RADAR_WIDTHS`:

```python
RADAR_HEADERS = ["Rank", "Company", "Vertical", "Trigger", "Trigger date", "Why now",
                 "Source", "First seen", "In SF?", "Pursue?", "Notes"]
RADAR_WIDTHS = {"Rank": 6, "Company": 30, "Vertical": 20, "Trigger": 36, "Trigger date": 12,
                "Why now": 60, "Source": 44, "First seen": 12, "In SF?": 28, "Pursue?": 10,
                "Notes": 30}
```

In `build_radar`, replace the `ws.append([...])` row with one that inserts the In SF? cell after First seen:

```python
    for i, e in enumerate(ranked, 1):
        sf = e.get("sf_status")
        sf_cell = (f"owner: {sf.get('owner') or 'another rep'}, type: {sf.get('type') or '?'}"
                   if sf else "")
        ws.append([i, e.get("name", ""), e.get("vertical", ""), e.get("triggerLabel", ""),
                   e.get("triggerDate", ""), e.get("reason", ""), e.get("sourceUrl", ""),
                   e.get("firstSeen", ""), sf_cell, "", ""])
        src = ws.cell(row=ws.max_row, column=7)
        src.hyperlink = e.get("sourceUrl", "")
        src.font = Font(color="0563C1", underline="single")  # explicit (avoid named-style dependency)
```

(Source stays column 7, so the hyperlink line is unchanged.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_rank_candidates.py -q`
Expected: PASS (all, including the new SF tests and updated radar tests).

- [ ] **Step 6: Commit**

```bash
git add observepoint-revenue/skills/find-accounts/scripts/rank_candidates.py observepoint-revenue/tests/test_rank_candidates.py
git commit -m "feat(find-accounts): show SF overlap status in chat + radar"
```

---

### Task 5: find-accounts SKILL.md — SF-first territory + overlap-guard flow

**Files:**
- Modify: `observepoint-revenue/skills/find-accounts/SKILL.md` (tool fence; §1 Territory; §2 Exclusions; §5 Rank; "does not do")

No automated test — this task's deliverable is the rewritten workflow doc. Verify by re-reading the file end-to-end for consistency with Tasks 1–4 (script names, args, query references).

- [ ] **Step 1: Widen the tool fence**

Replace the "Tool fence" block (lines ~15-16):

```markdown
**Tool fence:** The sweep uses `WebSearch` (and `WebFetch` to read a specific result) ONLY. Do NOT
open a browser / Playwright / Claude-in-Chrome or any page-rendering/scraping tool.
```

with:

```markdown
**Tool fence:** The web sweep uses `WebSearch` (and `WebFetch` to read a specific result) ONLY — no
browser / Playwright / Claude-in-Chrome or any page-rendering/scraping tool. Territory and the
overlap-guard use the **Salesforce MCP read tools** (`getUserInfo`, `soqlQuery`, `find`) — read-only;
never `create`/`update`. Run the canonical queries from
`${CLAUDE_PLUGIN_ROOT}/skills/salesforce-core/references/salesforce-org.md`.
```

- [ ] **Step 2: Rewrite §1 Territory**

Replace the entire step 1 ("**Territory.**" through the "Shared-machine state guard." paragraph, lines ~31-51) with:

````markdown
1. **Territory (Salesforce-first).** Resolve the boundary from Salesforce, not a hand-kept file.
   Read `${CLAUDE_PLUGIN_ROOT}/skills/salesforce-core/references/salesforce-org.md` for the queries.

   a. **Identify the target AE/ADM.** Call `getUserInfo`. This is a *hint only* — the SF MCP
      authenticates as whoever connected it, who may not be the human running this. If the connected
      user is an AE/ADM and no target was named, confirm and use them. Otherwise ask whose territory
      to run, and resolve them: `SELECT Id, Name, Email FROM User WHERE Email = :email AND IsActive = true`.

   b. **Pull the territory** (key on the target's actual role — never assume AE≡ADM):
      ```sql
      SELECT Id, Name, Name__c, Segment__c, World_Region__c, Sub_Region__c,
             Country__c, State__c, AE__r.Name, ADM__r.Name, CSM__r.Name
      FROM OP_Territories__c WHERE AE__c = :targetUserId      -- or ADM__c = :targetUserId
      ```
      Save the result to `/tmp/territory-soql.json` and normalize it:
      ```bash
      python3 "$SKILL/scripts/resolve_territory.py" /tmp/territory-soql.json > /tmp/territory-boundary.json
      ```
      The boundary gives `regions / sub_regions / countries / states / segments` (the geographic +
      segment patch) and `territory_ids` (used by the overlap-guard). **Verticals are NOT in SF** —
      take them from the `targetVerticals` list in `$SCORING` (+ any per-run narrowing the rep asks
      for). A per-run override adjusts THIS run only.

   c. **No territory found** (`territory_ids` empty): the target has no AE/ADM territory. Say so and
      ask for an explicit region + segment (or a different target) — do not guess a boundary.

   **Fallback.** If the Salesforce MCP is unavailable, fall back to
   `~/Documents/ObservePoint Revenue/territory.md` (region + verticals); if that's missing too, ask
   the rep and write it (the legacy `# Territory — <rep name>` format). SF is the source of truth
   when connected; the file is only a cache/override.
````

- [ ] **Step 3: Rewrite §2 Exclusions**

Replace step 2 ("**Exclusions.**" paragraph, lines ~53-56) with:

````markdown
2. **Exclusions.** Two layers:
   - **Local** (unchanged): subfolder names under `~/Documents/ObservePoint Revenue/Account Research/`
     (already researched — `ls` it), any rep-supplied pipeline list, and the seen-log (the ranker
     enforces that one). Skip obvious duplicates/subsidiaries of excluded names.
   - **Salesforce overlap-guard** (applied after the sweep, in step 5): the model matches the swept
     candidates against SF and `classify_overlap.py` enforces the policy — **hard-exclude** anything
     in the target's territory or owned by the target (this catches named accounts in other
     territories) and any `Type = Customer`; **flag but keep** companies already in SF under another
     rep or as Prospect/Previous Customer/Defunct, annotated `already in SF — owner: X, type: Y`.
````

- [ ] **Step 4: Insert the overlap-guard into §5 (Rank)**

In step 5, before the existing `rank_candidates.py` invocation, add the match + classify step:

````markdown
   **First, the Salesforce overlap-guard.** Collect the candidate domains and match them against SF
   (domain-first; `find` by name for any without a website match), per the account-match query in
   `salesforce-org.md`. Save the result to `/tmp/sf-account-matches.json`, then:

   ```bash
   python3 "$SKILL/scripts/classify_overlap.py" /tmp/discovery-candidates.json \
     /tmp/sf-account-matches.json --territory /tmp/territory-boundary.json \
     --target-user "<targetUserId>" --out /tmp/discovery-candidates.sf.json
   ```

   It drops hard-excludes, annotates the survivors with `sf_status`, and prints a one-line summary to
   stderr. **Then rank the annotated file** (note: `discovery-candidates.sf.json`, not the raw one):
````

And change the ranker invocation to read the annotated file:

```bash
   python3 "$SKILL/scripts/rank_candidates.py" /tmp/discovery-candidates.sf.json "$SCORING" \
     --seen "$HOME/Documents/ObservePoint Revenue/Account Discovery/seen-candidates.json"
```

Add one sentence after the existing ranker description: "Flagged candidates carry an `already in SF`
note in chat and an **In SF?** column in the radar — surface them, clearly marked; they are not
silently dropped."

- [ ] **Step 5: Update "What this skill does not do (v1)"**

Replace the final paragraph's `Salesforce sync,` with `Salesforce *write-back* (read-only today),`
so it reads:

```markdown
Deep research (research-account), auto-running research on candidates, contact work, outreach copy,
Salesforce *write-back* (read-only today), scheduled sweeps, paid data sources.
```

- [ ] **Step 6: Re-read and commit**

Re-read the whole SKILL.md; confirm every script name, CLI flag, temp-file path, and query matches Tasks 1–4.

```bash
git add observepoint-revenue/skills/find-accounts/SKILL.md
git commit -m "docs(find-accounts): SF-first territory + overlap-guard workflow"
```

---

### Task 6: Wiring — version, manifests, CLAUDE.md, ROADMAP, full suite

**Files:**
- Modify: `observepoint-revenue/.claude-plugin/plugin.json` (version + description)
- Modify: `.claude-plugin/marketplace.json` (description)
- Modify: `CLAUDE.md` (skills 6→7; test count)
- Modify: `docs/ROADMAP.md` (mark Active-sequence item 1 shipped)

- [ ] **Step 1: Bump the plugin version + description**

In `observepoint-revenue/.claude-plugin/plugin.json`: bump `"version"` from `0.17.0` to `0.18.0`, and append to the description, before the closing `"`: `, salesforce-core (shared read-side Salesforce foundation: org map + sf_io)`.

- [ ] **Step 2: Update the marketplace description**

In `.claude-plugin/marketplace.json`, append the same `salesforce-core (...)` clause to the plugin `description` so the two stay in sync.

- [ ] **Step 3: Update CLAUDE.md**

- Change the heading `## Skills (6)` to `## Skills (7)`.
- Add a bullet under it:
  ```markdown
  - **salesforce-core** — the shared read-side Salesforce foundation: the canonical org map
    (`references/salesforce-org.md`) + `sf_io.py` (digests SF MCP result JSON). Read-only; the
    model runs the MCP queries, scripts compute on the returned JSON. find-accounts uses it for
    territory + the overlap-guard; future SF skills (research write-back, CSM review, expansion)
    reuse it.
  ```
- In the Dev section, update the test count note (`291 passing`) to the new total printed by the full run in Step 5.

- [ ] **Step 4: Mark the roadmap item shipped**

In `docs/ROADMAP.md`, in the Active sequence, change item 1's status from `*in design now.*` to `*shipped in v0.18.0.*` and check it. In the Platform/integrations section, update the `Salesforce sync **[in design]**` line to note the read foundation + territory shipped, write-back still pending.

- [ ] **Step 5: Run the full suite**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q`
Expected: all green. Record the new total (291 + 9 sf_io + 3 resolve_territory + 7 classify_overlap + 3 rank-additions ≈ 313) and put it in CLAUDE.md (Step 3).

- [ ] **Step 6: Commit**

```bash
git add observepoint-revenue/.claude-plugin/plugin.json .claude-plugin/marketplace.json CLAUDE.md docs/ROADMAP.md
git commit -m "chore: wire salesforce-core into plugin (v0.18.0), docs + roadmap"
```

---

## Self-Review

**1. Spec coverage**
- Spec A (salesforce-core: `salesforce-org.md` + `sf_io.py`) → Task 1. ✓
- Spec B (territory resolution; getUserInfo-as-hint; role-keyed query; verticals from ICP; territory.md fallback) → Task 2 (`resolve_territory.py`) + Task 5 §1. ✓
- Spec C (overlap-guard two-phase, own-hard/others-flagged, feeds rank) → Task 3 (`classify_overlap.py`) + Task 4 (display) + Task 5 §2/§5. ✓
- Spec D (SKILL.md flow + output "In SF?" annotation) → Task 4 (radar/chat) + Task 5. ✓
- Spec E (fixture-based tests, no live SF; the named fixture cases) → Tasks 1–4 tests. ✓
- Spec decisions (hosting=salesforce-core; read-only; SF-source-of-truth+fallback; role-keyed) → reflected across tasks + Global Constraints. ✓

**2. Placeholder scan:** No "TBD/TODO/handle edge cases" — every code and test step is complete. `<targetUserId>` / `:email` / `:candidateDomains` are deliberate bind-variable placeholders the model fills at runtime, not plan gaps.

**3. Type consistency:** `sf_io.parse_records`/`normalize_domain`, `SalesforceResultError`, `normalize_territory` boundary keys (`territory_ids` used identically in Task 2 output, Task 3 input, Task 5 CLI), `classify(...) -> (kept, summary)` with `sf_status` shape `{"owner","type"}` consistent across Tasks 3–4, and `normalize_name` reused (not redefined). Radar column shift (In SF? at 9; Pursue? 10; Notes 11) applied consistently in Task 4 impl + test edits. ✓

## Out of scope (roadmap, not this plan)
Any SF write (research-account → SF, scope page-count field) + the rev-ops governance contract; the CSM review builder; expansion radar; reporting. The SF↔platform bridge and Gong-in-SF are documented in `salesforce-org.md` for those later items but unused here.
