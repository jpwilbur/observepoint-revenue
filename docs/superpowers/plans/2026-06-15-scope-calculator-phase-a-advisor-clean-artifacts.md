# Scope Calculator — Phase A: Advisor Flow & Clean Artifacts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make scope-calculator deliverables clean-by-construction for customers (no internal jargon, no leaked derivation), add per-cadence "why" rationale to the proposal, split rep-only context into a separate internal-evidence file, and rework `SKILL.md` into a guided advisor flow with a rationale-driven frequency ladder.

**Architecture:** Preserve the repo principle — *Claude gathers/judges; deterministic scripts compute/render.* A new shared `customer_clean.py` guard enforces clean customer language across both generators. `build_proposal.py` and the customer workbook are scrubbed; everything internal moves to a new `build_internal_evidence.py`. Cadence gains a customer-facing rationale per layer, seeded by a new `frequency-advisor.md`. No math changes — `compute_scope.py` is untouched.

**Tech Stack:** Python 3 (`/opt/homebrew/bin/python3`), `python-docx`, `openpyxl`, `pytest`. Tests live in `observepoint-revenue/tests/`; `conftest.py` puts each skill's `scripts/` on `sys.path` so modules import by name.

**Spec:** `docs/superpowers/specs/2026-06-15-scope-calculator-advisor-flow-design.md` (§5, §6, §8, §9.3, §10, §11 Phase A). Built on branch `harden/scope-calculator-recursion-port` (after commit `66f74b5`).

**Run all tests:** `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q` (currently 166 passing).

---

## File structure (Phase A)

```
skills/scope-calculator/
├── scripts/
│   ├── customer_clean.py            [NEW]    shared forbidden-term guard (1 responsibility: language safety)
│   ├── build_proposal.py            [MODIFY] use shared guard over all agent text; +cadence "why"; remove [INTERNAL]
│   ├── build_evidence_appendix.py   [MODIFY] CLEAN customer workbook: drop Spiral?/raw/reduced/census/Methodology; +why
│   └── build_internal_evidence.py   [NEW]    rep-only workbook: derivation, spiral, assumptions, price-by-band, dominance
├── references/
│   ├── customer-vocabulary.md       [NEW]    internal→customer term map (human doc; mirrors customer_clean.FORBIDDEN)
│   ├── frequency-advisor.md         [NEW]    5-layer ladder, rationales, anchor-high defaults, pull-back guidance
│   ├── usage-methodology.md         [MODIFY] point cadence section at frequency-advisor.md (keep multipliers/ask-map)
│   └── deliverables-mapping.md      [MODIFY] document the 3-file output (proposal / customer workbook / internal)
└── SKILL.md                         [MODIFY] phase-based advisor flow (audience Q, recommend-first inputs, ladder walk, 3 files)
tests/
├── test_customer_clean.py           [NEW]
├── test_build_internal_evidence.py  [NEW]
├── test_build_proposal.py           [MODIFY] flip internal-section asserts; add cadence-why + clean asserts
└── test_build_evidence_appendix.py  [MODIFY] flip Spiral?/Methodology asserts; add clean asserts
```

**Sequencing rationale:** Task 1 (the guard) is the shared dependency for Tasks 2/3/5. Task 4 (internal file) must land before Task 5 strips internal content from the customer workbook, so no rep data is lost. Tasks 6–7 (content) come last and are verified by the full suite staying green plus subagent pressure tests.

---

## Task 1: Shared customer-language guard (`customer_clean.py` + vocabulary doc)

**Files:**
- Create: `skills/scope-calculator/scripts/customer_clean.py`
- Create: `skills/scope-calculator/references/customer-vocabulary.md`
- Test: `tests/test_customer_clean.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_customer_clean.py
import pathlib
import pytest
import customer_clean as cc

REFS = pathlib.Path(__file__).resolve().parent.parent / "skills" / "scope-calculator" / "references"
VOCAB = REFS / "customer-vocabulary.md"


def test_flags_internal_terms():
    leaked = cc.find_forbidden(["Annual full-site sweep", "we discounted the spiral URLs"])
    assert "spiral" in leaked and "discount" in leaked


def test_clean_text_passes():
    assert cc.find_forbidden(["Annual full-site monitoring", "weekly release checks"]) == []
    cc.assert_clean(["Annual full-site monitoring"])  # must not raise


def test_assert_clean_raises_with_context():
    with pytest.raises(ValueError, match="internal-only term"):
        cc.assert_clean(["raw URL total"], where="proposal")


def test_identity_values_are_not_passed_here():
    # The guard only sees strings the CALLER chooses to pass; callers must exclude identity fields.
    # A customer literally named "Discount Tire" only false-trips if a caller wrongly passes it —
    # this asserts the guard itself has no special-casing, documenting the caller contract.
    assert cc.find_forbidden(["Discount Tire Co"]) == ["discount"]


def test_every_forbidden_term_is_documented_in_vocab():
    doc = VOCAB.read_text().lower()
    missing = [t for t in cc.FORBIDDEN if t not in doc]
    assert missing == [], f"terms in FORBIDDEN but not in customer-vocabulary.md: {missing}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_customer_clean.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'customer_clean'`.

- [ ] **Step 3: Write `customer_clean.py`**

```python
# skills/scope-calculator/scripts/customer_clean.py
"""Shared customer-facing-language guard for scope-calculator deliverables.

Internal Site Census / pricing jargon must never reach a customer .docx or .xlsx. This module is
the single source of the forbidden-term list (kept in sync with references/customer-vocabulary.md)
and the guard both generators call.

CALLER CONTRACT: pass only AGENT-COMPOSED, customer-facing strings (narrative, cadence names,
"why" lines, properties notes). NEVER pass identity/factual fields (customer name, domains,
prepared_by) — a customer named "Discount Tire" or a domain "spiral-galaxy.com" would false-trip.
The guard intentionally has no identity special-casing; scoping is the caller's job.
"""

# Internal-only terms that must not appear in customer-facing prose or labels.
# MIRRORS references/customer-vocabulary.md (test_every_forbidden_term_is_documented_in_vocab).
FORBIDDEN = (
    "site census", "census", "spiral", "raw url", "defensible", "indefensible",
    "reduced", "discount", "query-param", "query-string", "crawl", "recursion",
    "collapsed", "anchor", "fallback",
)


def find_forbidden(strings):
    """Return the forbidden terms present (substring, case-insensitive) across the given strings."""
    blob = " ".join(s for s in strings if s).lower()
    return [t for t in FORBIDDEN if t in blob]


def assert_clean(strings, where="customer deliverable"):
    leaked = find_forbidden(strings)
    if leaked:
        raise ValueError(f"{where} contains internal-only term(s): {sorted(set(leaked))}")
```

- [ ] **Step 4: Write `customer-vocabulary.md`** (the human-facing term map; must mention every `FORBIDDEN` term so the consistency test passes)

```markdown
# Customer-facing vocabulary (scrub map)

Internal Site Census and pricing jargon must never appear in a customer-facing `.docx` or `.xlsx`.
`scripts/customer_clean.py` enforces the forbidden list below; this doc is the human-readable map.
Anything internal lives in the separate internal-evidence workbook, never forwarded.

| Internal term | Why it's internal | Customer-facing wording |
|---|---|---|
| site census / census | internal crawler + its IDs | (omit) "your website footprint" |
| spiral / spiral-adjusted | query-param de-duplication mechanic | (omit) — just report "pages" |
| raw url / raw URLs | pre-reduction crawl count | "pages" (the clean number) |
| defensible / indefensible | internal defensibility framing | "pages" |
| reduced / discount / discounted | the delta we removed | (omit) — show only the clean count |
| query-param / query-string | the duplication source | (omit) |
| crawl / recursion / collapsed | crawler internals + recursion-trap handling | (omit) — internal file only |
| anchor | internal point-estimate label | "estimated footprint" |
| fallback | pricing-source staleness flag | (omit) — internal file only |

**Caller contract:** the guard checks only agent-composed customer-facing strings (narrative,
cadence-layer names, "why" lines, property notes). Identity/factual fields (customer name, domains,
prepared_by, regulations) are never passed to it.
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_customer_clean.py -q`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" add observepoint-revenue/skills/scope-calculator/scripts/customer_clean.py observepoint-revenue/skills/scope-calculator/references/customer-vocabulary.md observepoint-revenue/tests/test_customer_clean.py
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" commit -m "feat(scope-calculator): shared customer-language guard + vocabulary map"
```

---

## Task 2: Wire the expanded guard into `build_proposal.py`

Replace the proposal's local, narrative-only guard with the shared module, and widen what it checks to every agent-composed customer-facing string (cadence-layer names, the new "why" lines, properties note) — never identity fields.

**Files:**
- Modify: `skills/scope-calculator/scripts/build_proposal.py:50-51` (remove local `_FORBIDDEN`), `:226-232` (`_assert_clean`)
- Test: `tests/test_build_proposal.py` (add cases)

- [ ] **Step 1: Write the failing tests** (append to `tests/test_build_proposal.py`)

```python
def test_clean_guard_rejects_internal_term_in_cadence_name():
    d = json.loads(json.dumps(DATA))
    d["cadence_layers"][1]["name"] = "Quarterly spiral re-check"   # internal term in a customer label
    with pytest.raises(ValueError):
        bp.build_proposal(d)


def test_clean_guard_rejects_internal_term_in_why():
    d = json.loads(json.dumps(DATA))
    d["cadence_layers"][0]["why"] = "Full crawl to find every defensible page."
    with pytest.raises(ValueError):
        bp.build_proposal(d)


def test_clean_guard_allows_identity_collision_in_name_and_domain():
    d = json.loads(json.dumps(DATA))
    d["customer"] = "Discount Tire Co"
    d["domains"] = ["spiral-galaxy.com"]
    d["monitoring_summary"] = "Full-site privacy monitoring annually."
    bp.build_proposal(d)  # identity fields are not scrubbed → must not raise
```

- [ ] **Step 2: Run to verify failure**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_build_proposal.py -q -k "cadence_name or term_in_why or identity_collision"`
Expected: FAIL — `test_clean_guard_rejects_internal_term_in_cadence_name` and `..._in_why` do NOT raise yet (guard only checks `monitoring_summary`).

- [ ] **Step 3: Edit `build_proposal.py`**

Delete the local list at line 51:
```python
_FORBIDDEN = ("spiral", "discount", "query-param", "raw url", "indefensible", "fallback")
```

Add the import near the top imports (after line 31, with the other local-module-free imports — `customer_clean` is a sibling module on the test/skill `sys.path`):
```python
import customer_clean
```

Replace `_assert_clean` (lines 226–232) with a version that collects every agent-composed customer-facing string — but NOT identity fields:
```python
def _assert_clean(data):
    """Guard all agent-composed customer-facing text against internal-only language. Identity/
    factual fields (customer, domains, prepared_by, regulations) are NOT scrubbed — see
    customer_clean caller contract."""
    strings = [data.get("monitoring_summary", ""), data.get("properties_note", "")]
    for L in data.get("cadence_layers", []):
        strings.append(L.get("name", ""))
        strings.append(L.get("why", ""))
    customer_clean.assert_clean(strings, where="proposal")
```

- [ ] **Step 4: Run to verify pass**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_build_proposal.py -q`
Expected: PASS. (Note: existing `test_clean_guard_rejects_internal_terms_in_narrative` and `..._allows_internal_section_terms`/`..._allows_collision_identity` still pass — the new guard still catches narrative terms, still ignores `page_count.spiral_note`, still ignores identity.)

- [ ] **Step 5: Commit**

```bash
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" add observepoint-revenue/skills/scope-calculator/scripts/build_proposal.py observepoint-revenue/tests/test_build_proposal.py
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" commit -m "feat(scope-calculator): proposal guard covers all agent-composed customer text"
```

---

## Task 3: Proposal — add cadence "why", remove the [INTERNAL] section, drop the confidence chip

The cadence table gains a customer-facing **Why** column (spec §5). The strippable `[INTERNAL]` section is removed entirely (its content moves to Task 4's file). The confidence chip and footprint internal details move internal too (spec §8.1: confidence → internal file).

**Files:**
- Modify: `skills/scope-calculator/scripts/build_proposal.py` — cadence table (lines 305–311), confidence chip (283–286), `[INTERNAL]` block (338–389)
- Test: `tests/test_build_proposal.py`

- [ ] **Step 1: Update tests — flip the internal-section asserts to RED, add the Why column**

In `tests/test_build_proposal.py`, add a `why` to each cadence layer in the `DATA` fixture (lines 30–33) so the new column has content:
```python
    "cadence_layers": [
        {"name": "Baseline inventory", "runs_per_year": 1, "pages": 287_163, "runs": 287_163,
         "why": "A full sweep so nothing on the site is invisible."},
        {"name": "Inventory refresh", "runs_per_year": 4, "pages": 14_358, "runs": 57_432,
         "why": "Sites drift — quarterly keeps the full picture current."},
        {"name": "Critical watch", "runs_per_year": 12, "pages": 7_179, "runs": 86_149,
         "why": "Crown-jewel pages checked far more often."}],
```

Replace `test_internal_section_marked_and_present` with its inverse, and update `test_customer_sections_and_derivation`:
```python
def test_no_internal_section_or_confidence_in_customer_doc():
    t = _text(bp.build_proposal(DATA))
    assert "[INTERNAL" not in t                 # the strippable section is gone
    assert "485,096" not in t                   # raw URL total never in the customer doc
    assert "711" not in t                       # census id never in the customer doc
    assert "CONFIDENCE" not in t.upper()        # confidence moved to the internal file
    for term in ("census", "spiral", "raw url", "defensible", "anchor"):
        assert term not in t.lower(), f"leaked internal term: {term}"


def test_cadence_table_shows_the_why():
    t = _text(bp.build_proposal(DATA))
    assert "Why" in t                                            # the new column header
    assert "nothing on the site is invisible" in t              # a rationale line, customer-facing
```

Note: also remove the now-obsolete `test_internal_section_marked_and_present` (lines 80–85). In `test_customer_sections_and_derivation`, the existing `assert "96,000" in t` stays (anchor still rendered as the footprint number, just not labeled "anchor").

- [ ] **Step 2: Run to verify failure**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_build_proposal.py -q -k "no_internal_section or cadence_table_shows"`
Expected: FAIL — `[INTERNAL` still present; no "Why" column.

- [ ] **Step 3: Edit `build_proposal.py` — cadence table with Why column** (replace lines 305–311)

```python
    cadence_rows = []
    for L in data.get("cadence_layers", []):
        freq = _FREQ.get(L.get("runs_per_year"), f"{L.get('runs_per_year')}×/yr")
        cadence_rows.append([L["name"], L.get("why", ""), freq, _int(L.get("pages", 0)),
                             str(L.get("runs_per_year", "")), _int(L.get("runs", 0))])
    cadence_rows.append(["**Total annual page scans**", "", "", "", "", "**" + _int(us["annual_scans"]) + "**"])
    _table(doc, ["What's monitored", "Why", "How often", "Pages each run", "Runs/yr", "Page scans/yr"],
           cadence_rows)
```

- [ ] **Step 4: Edit `build_proposal.py` — drop the confidence chip** (replace lines 276–286, the badge block, keeping only the page-count badge)

```python
    # Footprint badge (page count only — confidence is rep-only, in the internal file)
    badge_t = doc.add_table(rows=1, cols=1)
    _no_borders(badge_t)
    _chip(badge_t.rows[0].cells[0], _int(_round_sig(pc["anchor"])) + " pages", YELLOW_HEX, DARK, size=14)
```

Also, in §1 footprint prose (lines 264–268), remove the `confidence {pc.get('confidence', 'MEDIUM')}` clause so confidence is not stated to the customer:
```python
    _para(doc, f"We scanned your web properties to establish how many real pages ObservePoint "
               f"would monitor. Your estimated footprint is approximately "
               f"{_int(_round_sig(pc['anchor']))} pages "
               f"(range {_int(_round_sig(pc['low']))}–{_int(_round_sig(pc['high']))}).")
```

- [ ] **Step 5: Edit `build_proposal.py` — remove the [INTERNAL] section** (delete lines 338–389, from `# [INTERNAL] — rep-only, delete before sending` through the end of the `thresholds_swept` block, i.e. everything between the `# §5 To finalize` block's end and the final `return doc`). After deletion the builder ends:

```python
        p = doc.add_paragraph(style="List Bullet")
        _run(p, item)

    return doc
```

Remove the now-unused `internal = data.get("internal", {})` (line 242) and the docstring's mention of the `[INTERNAL]` section (lines 3–6, 11) — update the module docstring to: *"Customer-facing scope & investment proposal (.docx). Clean by construction — internal derivation lives in the separate internal-evidence workbook."* The `internal` and `page_count` internal-only keys (`url_total`, `census_id`, etc.) become ignored-if-present (harmless); note this in the docstring schema.

- [ ] **Step 6: Run to verify pass**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_build_proposal.py -q`
Expected: PASS (including the updated clean-doc + Why-column tests).

- [ ] **Step 7: Commit**

```bash
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" add observepoint-revenue/skills/scope-calculator/scripts/build_proposal.py observepoint-revenue/tests/test_build_proposal.py
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" commit -m "feat(scope-calculator): clean customer proposal — cadence 'why', drop [INTERNAL] + confidence"
```

---

## Task 4: New rep-only `build_internal_evidence.py`

Everything internal that the proposal/appendix used to carry now lives in one rep-only workbook: page-count derivation (census id, crawl status, raw/defensible/reduced), per-domain spiral/discount + Methodology, assumptions-to-verify, modeled-vs-contracted, price-by-band, and the new rollup-dominance flag (spec §9.2; full detail is Phase C, but the file is its home). Reuses the sum-to-anchor invariant.

**Files:**
- Create: `skills/scope-calculator/scripts/build_internal_evidence.py`
- Test: `tests/test_build_internal_evidence.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_build_internal_evidence.py
import json
import pathlib
import subprocess
import sys

import pytest
from openpyxl import load_workbook

import build_internal_evidence as bie

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "scope-calculator" / "scripts" / "build_internal_evidence.py"

DATA = {
    "customer": "Acme Corp", "date": "2026-06-15",
    "rollup": {"url_total": 410_000, "spiral_adjusted_anchor": 95_000, "low": 88_000, "high": 105_000,
               "confidence": "MEDIUM", "census_ids": [812], "crawl_status": "done"},
    "per_domain": [
        {"hostname": "acme.com", "raw_urls": 90_000, "defensible_pages": 90_000, "discounted": 0, "why": ""},
        {"hostname": "shop.acme.com", "raw_urls": 320_000, "defensible_pages": 5_000, "discounted": 315_000,
         "spiral_flag": True, "why": "64x query-param spiral"}],
    "pricing": {"price_by_band": [{"band_limit": 1000, "rate": 0.0, "pages": 1000, "cost": 0.0},
                                  {"band_limit": 50000, "rate": 0.17, "pages": 50000, "cost": 8500.0}],
                "modeled_scans": 430_744, "modeled_price": 54_069.28,
                "recommended_scans": 430_167, "recommended_price": 54_000,
                "pricing_source": "live @ https://app.observepoint.com/www-pricing/main.js"},
    "internal": {"assumptions": ["Geographies defaulted to 1 — confirm regions.",
                                 "Consent states assumed CCPA (3) — confirm regulations."],
                 "implied_frequency": 1.5},
}


def _alltext(wb):
    out = []
    for ws in wb.worksheets:
        out.append(ws.title)
        for row in ws.iter_rows(values_only=True):
            out += [str(v) for v in row if v is not None]
    return "\n".join(out)


def test_invariant_raises_on_mismatch():
    bad = json.loads(json.dumps(DATA))
    bad["rollup"]["spiral_adjusted_anchor"] = 9_999
    with pytest.raises(ValueError, match=r"sum \d+ != rollup anchor"):
        bie.build_workbook(bad)


def test_internal_content_present():
    t = _alltext(bie.build_workbook(DATA))
    assert "812" in t                              # census id (internal)
    assert "410,000" in t or "410000" in t         # raw URL total (internal)
    assert "64x query-param spiral" in t           # per-domain derivation note
    assert "confirm regulations" in t.lower()      # assumption-to-verify
    assert "430,744" in t or "430744" in t         # modeled scans


def test_dominance_flag_when_one_domain_dominates():
    # spec §9.2: flag when the single largest host exceeds ~40% of the anchor.
    d = json.loads(json.dumps(DATA))
    d["per_domain"] = [{"hostname": "trap.com", "raw_urls": 1_710_000, "defensible_pages": 90_000,
                        "discounted": 0, "why": ""},
                       {"hostname": "acme.com", "raw_urls": 5_000, "defensible_pages": 5_000,
                        "discounted": 0, "why": ""}]
    d["rollup"]["spiral_adjusted_anchor"] = 95_000   # trap.com = 94.7% of anchor
    t = _alltext(bie.build_workbook(d))
    assert "trap.com" in t and "%" in t
    assert bie.dominant_host(d) is not None and bie.dominant_host(d)["hostname"] == "trap.com"


def test_no_dominance_flag_when_balanced():
    assert bie.dominant_host(DATA) is None          # 90k/95k? -> acme.com IS 94.7%...
```

> **Plan note for the implementer:** the `DATA` fixture above has `acme.com` at 90k of a 95k anchor (94.7%), which WOULD trip dominance — so `test_no_dominance_flag_when_balanced` as written is wrong. Fix the fixture for that test to a balanced split (e.g. two domains at ~47k each summing to 95k) inside the test, OR assert `dominant_host` returns `acme.com`. Use a balanced local fixture:

```python
def test_no_dominance_flag_when_balanced():
    d = json.loads(json.dumps(DATA))
    d["per_domain"] = [{"hostname": "a.com", "raw_urls": 48_000, "defensible_pages": 48_000, "discounted": 0, "why": ""},
                       {"hostname": "b.com", "raw_urls": 47_000, "defensible_pages": 47_000, "discounted": 0, "why": ""}]
    d["rollup"]["spiral_adjusted_anchor"] = 95_000
    assert bie.dominant_host(d) is None             # 48k/95k = 50.5%... still >40%
```

> Both 94.7% and 50.5% exceed a 40% threshold, so a 2-domain split always trips it. Use a 3+ domain balanced fixture (e.g. 35k/30k/30k = 95k; max share 36.8% < 40%) for the negative case. The implementer MUST construct the negative fixture so the largest host is < 40% of the anchor.

- [ ] **Step 2: Run to verify failure**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_build_internal_evidence.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'build_internal_evidence'`.

- [ ] **Step 3: Write `build_internal_evidence.py`**

Reuse the styling helpers pattern from `build_evidence_appendix.py` (`_f`, `_fill`, `_title`, `_headers`, `_row`, `_widths`, `_check_invariant`). Provide a `dominant_host(data)` helper and four sheets: Derivation, Per-Domain, Assumptions, Pricing.

```python
"""Rep-only internal evidence workbook (.xlsx) — NEVER sent to a customer.

Holds everything the customer-facing deliverables intentionally omit: page-count derivation
(census id, crawl status, raw vs defensible vs reduced), per-domain spiral/recursion notes,
assumptions-to-verify, modeled-vs-contracted, price-by-band, and the rollup-dominance flag
(spec §9.2). Enforces the sum-to-anchor invariant (spec §4.6).

Input: {customer, date?, rollup{...}, per_domain[{...}], pricing?{...}, internal?{...}}.
"""
import json
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

FONT = "Montserrat"
DARK, YELLOW, LIGHT, GRAY, WHITE, RED = "1E1E1E", "F2CD14", "F2F2F2", "5C5C5C", "FFFFFF", "F34146"
_THIN = Side(style="thin", color="D9D9D9")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
DOMINANCE_THRESHOLD = 0.40  # spec §9.2: flag when one host exceeds this share of the anchor


def _f(bold=False, color=DARK, size=10):
    return Font(name=FONT, bold=bold, color=color, size=size)


def _fill(hexc):
    return PatternFill("solid", fgColor=hexc)


def _check_invariant(data):
    total = sum(d["defensible_pages"] for d in data["per_domain"])
    anchor = data["rollup"]["spiral_adjusted_anchor"]
    if total != anchor:
        breakdown = ", ".join(f"{d['hostname']}={d['defensible_pages']}" for d in data["per_domain"])
        raise ValueError(f"per-domain defensible_pages sum {total} != rollup anchor {anchor} "
                         f"(per domain: {breakdown})")


def dominant_host(data):
    """Return the per-domain row whose defensible_pages exceed DOMINANCE_THRESHOLD of the anchor,
    else None. The Gallagher recursion-trap signal (one host was 93% of the total)."""
    anchor = data["rollup"].get("spiral_adjusted_anchor") or 0
    if anchor <= 0:
        return None
    top = max(data["per_domain"], key=lambda d: d["defensible_pages"])
    return top if top["defensible_pages"] / anchor > DOMINANCE_THRESHOLD else None


def _widths(ws, widths):
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w


def _title(ws, text, span, row, color=DARK):
    c = ws.cell(row, 1, text)
    c.font = _f(bold=True, size=14, color=color)
    return row + 2


def _headers(ws, headers, row):
    for i, h in enumerate(headers):
        c = ws.cell(row, i + 1, h)
        c.font = _f(bold=True, color=WHITE)
        c.fill = _fill(DARK)
        c.border = _BORDER
    return row + 1


def _row(ws, row, values, *, alt=False, fill=None, bold=()):
    for i, v in enumerate(values):
        c = ws.cell(row, i + 1, v)
        c.font = _f(bold=(i in bold))
        c.border = _BORDER
        if fill:
            c.fill = _fill(fill)
        elif alt:
            c.fill = _fill(LIGHT)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            c.number_format = "#,##0"
    return row + 1


def _derivation(wb, data):
    ws = wb.active
    ws.title = "Derivation (INTERNAL)"
    _widths(ws, [44, 26])
    r = _title(ws, "Page-count derivation — REP ONLY, do not send", 2, 1, color=RED)
    rollup = data["rollup"]
    raw_total = sum(d["raw_urls"] for d in data["per_domain"])
    def_total = sum(d["defensible_pages"] for d in data["per_domain"])
    dom = dominant_host(data)
    pairs = [
        ("Customer", data.get("customer", "")),
        ("Date", data.get("date", "")),
        ("Census ID(s)", ", ".join(str(c) for c in rollup.get("census_ids", []))),
        ("Crawl status", rollup.get("crawl_status", "")),
        ("Confidence", rollup.get("confidence", "")),
        ("", ""),
        ("Validated pages — low / anchor / high",
         f"{rollup.get('low','')} / {rollup.get('spiral_adjusted_anchor','')} / {rollup.get('high','')}"),
        ("Total raw URLs crawled", raw_total),
        ("Total defensible pages", def_total),
        ("Reduced (query-string duplicates)", raw_total - def_total),
    ]
    if dom:
        share = round(100.0 * dom["defensible_pages"] / rollup["spiral_adjusted_anchor"], 1)
        pairs += [("", ""),
                  ("⚠ DOMINANCE FLAG", f"{dom['hostname']} = {share}% of anchor — verify it is not a "
                                       f"recursion trap before quoting (spec §9.2)")]
    for label, val in pairs:
        c1 = ws.cell(r, 1, label); c1.font = _f(bold=True)
        c2 = ws.cell(r, 2, val); c2.font = _f()
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            c2.number_format = "#,##0"
        if "DOMINANCE" in str(label):
            c1.fill = c2.fill = _fill(YELLOW)
        r += 1


def _per_domain(wb, data):
    ws = wb.create_sheet("Per-Domain (INTERNAL)")
    _widths(ws, [40, 14, 14, 14, 36])
    r = _title(ws, "Per-domain derivation", 5, 1)
    r = _headers(ws, ["Property (domain)", "Raw URLs", "Defensible pages", "Reduced", "Note"], r)
    for i, d in enumerate(sorted(data["per_domain"], key=lambda x: -x.get("discounted", 0))):
        note = d.get("why", "") or ("query-string duplicates removed" if d.get("spiral_flag") else "")
        r = _row(ws, r, [d["hostname"], d["raw_urls"], d["defensible_pages"],
                         d.get("discounted", 0), note], alt=(i % 2 == 1))


def _assumptions(wb, data):
    internal = data.get("internal", {})
    if not internal.get("assumptions"):
        return
    ws = wb.create_sheet("Assumptions (INTERNAL)")
    _widths(ws, [80])
    r = _title(ws, "Assumptions to verify with the customer", 1, 1)
    for a in internal["assumptions"]:
        r = _row(ws, r, [a])
    if internal.get("implied_frequency") is not None:
        r += 1
        _row(ws, r, [f"Implied blended frequency: {internal['implied_frequency']}× "
                     f"(vs the public single-frequency calculator)."])


def _pricing(wb, data):
    pr = data.get("pricing", {})
    if not pr:
        return
    ws = wb.create_sheet("Pricing (INTERNAL)")
    _widths(ws, [22, 20, 16, 16])
    r = _title(ws, "Pricing — modeled vs contracted", 4, 1)
    r = _headers(ws, ["", "Modeled (precise)", "Contracted (clean)", ""], r)
    r = _row(ws, r, ["Annual page scans", pr.get("modeled_scans", ""), pr.get("recommended_scans", ""), ""])
    r = _row(ws, r, ["Annual price (USD)", pr.get("modeled_price", ""), pr.get("recommended_price", ""), ""], alt=True)
    r += 1
    if pr.get("price_by_band"):
        r = _headers(ws, ["Band width", "Rate/scan", "Scans", "Cost"], r)
        for i, b in enumerate(pr["price_by_band"]):
            band = "tail" if b.get("band_limit") is None else b["band_limit"]
            r = _row(ws, r, [band, b["rate"], b["pages"], b["cost"]], alt=(i % 2 == 1))
    if pr.get("pricing_source"):
        r += 1
        _row(ws, r, [f"Pricing source: {pr['pricing_source']}"])


def build_workbook(data):
    _check_invariant(data)
    wb = Workbook()
    _derivation(wb, data)
    _per_domain(wb, data)
    _assumptions(wb, data)
    _pricing(wb, data)
    return wb


_DOC_REF = "see references/deliverables-mapping.md"
_REQUIRED = {"rollup": "{spiral_adjusted_anchor, …}", "per_domain": "[{hostname, raw_urls, defensible_pages}, …]"}


def _validate(data):
    if not isinstance(data, dict):
        sys.exit(f"scope-calculator: malformed internal-evidence inputs — expected a JSON object; {_DOC_REF}")
    for key, shape in _REQUIRED.items():
        if key not in data or data[key] in (None, {}, []):
            sys.exit(f"scope-calculator: missing/malformed '{key}' — expected {shape}; {_DOC_REF}")


def main(argv):
    raw = open(argv[1]).read() if len(argv) > 1 else sys.stdin.read()
    out = argv[2] if len(argv) > 2 else "internal-evidence.xlsx"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f"scope-calculator: internal-evidence inputs are not valid JSON ({e}); {_DOC_REF}")
    _validate(data)
    build_workbook(data).save(out)
    print(out)


if __name__ == "__main__":
    main(sys.argv)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_build_internal_evidence.py -q`
Expected: PASS (after fixing the negative-dominance fixture per the Step-1 plan note).

- [ ] **Step 5: Commit**

```bash
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" add observepoint-revenue/skills/scope-calculator/scripts/build_internal_evidence.py observepoint-revenue/tests/test_build_internal_evidence.py
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" commit -m "feat(scope-calculator): rep-only internal-evidence workbook + dominance flag"
```

---

## Task 5: Clean the customer workbook (`build_evidence_appendix.py`)

Strip everything internal from the customer workbook now that Task 4 preserves it: drop the **Methodology** sheet, the **Spiral?** column, the raw/reduced rows and census/crawl/confidence from **Scope Summary**; rename "Real (defensible) pages"/"Real pages" → **"Pages"**; add the per-row **Why** to the usage breakdown; run the customer-language guard over agent-composed strings.

**Files:**
- Modify: `skills/scope-calculator/scripts/build_evidence_appendix.py`
- Test: `tests/test_build_evidence_appendix.py`

- [ ] **Step 1: Update tests — flip Spiral?/Methodology asserts to RED**

Replace `test_sheets_present_with_usage`, `test_pages_by_domain_headers_and_fillable`, and `test_methodology_shows_reduction`:
```python
def test_customer_sheets_no_methodology_or_internal():
    wb = bea.build_workbook(DATA)
    assert "Methodology" not in wb.sheetnames            # methodology is internal now
    assert wb.sheetnames == ["Scope Summary", "Pages by Domain", "Sample Pages", "Annual Usage Breakdown"]
    t = _alltext(wb)
    for term in ("Spiral", "raw url", "Census", "Confidence", "Reduced", "defensible"):
        assert term.lower() not in t.lower(), f"leaked internal term: {term}"


def test_pages_by_domain_clean_headers():
    ws = bea.build_workbook(DATA)["Pages by Domain"]
    assert [c.value for c in ws[3]] == ["Property (domain)", "Pages", "% of total"] + bea.FILL_COLS
    assert ws.cell(4, 1).value == "acme.com"
    assert ws.cell(4, 2).value == 90_000
    assert ws.cell(4, 4).value is None    # first fillable column (Include in scope?) empty


def test_usage_breakdown_shows_why():
    # add a why to the fixture layers in this test
    d = json.loads(json.dumps(DATA))
    for L, w in zip(d["usage"]["cadence_layers"], ["full sweep", "priority refresh", "consent watch"]):
        L["why"] = w
    t = _alltext(bea.build_workbook(d))
    assert "Why" in t and "priority refresh" in t
```

Keep `test_invariant_raises_on_mismatch`, `test_usage_sheet_omitted_when_no_usage` (update expected count to 3), `test_sample_pages_present`, `test_usage_breakdown_content` (drop the consent/percent asserts that reference removed columns if needed), and the CLI tests.

- [ ] **Step 2: Run to verify failure**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_build_evidence_appendix.py -q`
Expected: FAIL — Methodology sheet still present, `Spiral?` header still there.

- [ ] **Step 3: Edit `build_evidence_appendix.py`**

(a) Add the guard import (after line 24): `import customer_clean`.

(b) `_scope_summary` (lines 112–126): remove the internal `pairs` entries — drop `Census ID(s)`, `Crawl status`, `Confidence`, `Total raw URLs crawled`, `Total real (defensible) pages`, `Reduced (...)`. Keep customer-safe rows:
```python
    pairs = [
        ("Customer", data.get("customer", "")),
        ("Date", data.get("date", "")),
        ("", ""),
        ("Pages — low", rollup.get("low", "")),
        ("Pages — estimated footprint", rollup.get("spiral_adjusted_anchor", "")),
        ("Pages — high", rollup.get("high", "")),
    ]
```
Remove the now-unused `raw_total`/`def_total` locals (lines 110–111). Update the title (line 107) from `"Page-Count Evidence"` to `"Scope Summary"`. Update the "How to use" note (lines 143–147) to drop the Methodology sentence.

(c) `_pages_by_domain` (lines 159–165): drop the `Spiral?` column and rename `Real pages` → `Pages`:
```python
    r = _headers(ws, ["Property (domain)", "Pages", "% of total"] + FILL_COLS, r)
    ws.freeze_panes = ws.cell(r, 1)
    for i, d in enumerate(sorted(data["per_domain"], key=lambda x: -x["defensible_pages"])):
        pct = round(100.0 * d["defensible_pages"] / anchor, 1)
        r = _row(ws, r, [d["hostname"], d["defensible_pages"], f"{pct}%", None, None, None], alt=(i % 2 == 1))
```
Adjust `_widths` (line 156) to 6 columns: `_widths(ws, [40, 16, 12, 16, 12, 26])`.

(d) `_usage_breakdown` (lines 208–213): add the Why column:
```python
    r = _headers(ws, ["What's monitored", "Why", "How often", "% of pages", "Pages each run", "Runs/yr", "Page scans/yr"], r)
    for i, L in enumerate(usage.get("cadence_layers", [])):
        freq = _FREQ.get(L.get("runs_per_year"), f"{L.get('runs_per_year')}x/yr")
        pct = f"{round(L.get('pct', 0) * 100, 2)}%"
        r = _row(ws, r, [L["name"], L.get("why", ""), freq, pct, round(L.get("pages", 0)),
                         L.get("runs_per_year", ""), round(L.get("runs", 0))], alt=(i % 2 == 1))
```
Update the two TOTAL/header rows in `_usage_breakdown` that assume 6 columns to 7 (the `["From pages to one full sweep", "", "", "", "", "Pages"]` header and the TOTAL row gain one `""`), and widen `_widths` (line 199) to 7 columns: `_widths(ws, [34, 30, 14, 12, 16, 12, 16])`.

(e) Delete `_methodology` (lines 224–242) and its call in `build_workbook` (line 253). Remove `_FREQ`-adjacent unused imports only if now unused (keep all — still used).

(f) In `build_workbook` (lines 245–254), add the guard over agent-composed strings before building:
```python
def build_workbook(data):
    _check_invariant(data)
    strings = []
    for d in data["per_domain"]:
        strings.append(d.get("why", ""))
    for L in data.get("usage", {}).get("cadence_layers", []):
        strings.append(L.get("name", ""))
        strings.append(L.get("why", ""))
    customer_clean.assert_clean(strings, where="evidence appendix")
    wb = Workbook()
    _scope_summary(wb, data)
    _pages_by_domain(wb, data)
    _sample_pages(wb, data)
    if data.get("usage"):
        _usage_breakdown(wb, data)
    return wb
```

> **Note:** `per_domain[].why` for spiral domains (e.g. "64x query-param spiral") is INTERNAL and must NOT be passed to the customer workbook's guard or rendered. In the customer workbook, do not render `why` on the Pages-by-Domain sheet at all (it isn't, after (c)); only the *usage cadence* `why` (customer rationale) is rendered. Update the guard in (f) to NOT include `d.get("why")` from per_domain — only the usage cadence name/why:
```python
    strings = []
    for L in data.get("usage", {}).get("cadence_layers", []):
        strings += [L.get("name", ""), L.get("why", "")]
    customer_clean.assert_clean(strings, where="evidence appendix")
```

- [ ] **Step 4: Run to verify pass**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_build_evidence_appendix.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" add observepoint-revenue/skills/scope-calculator/scripts/build_evidence_appendix.py observepoint-revenue/tests/test_build_evidence_appendix.py
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" commit -m "feat(scope-calculator): clean customer workbook — drop Spiral?/raw/Methodology, +cadence why"
```

---

## Task 6: `frequency-advisor.md` reference

**Files:**
- Create: `skills/scope-calculator/references/frequency-advisor.md`
- Test: `tests/test_build_proposal.py` — add a doc-presence guard (cheap regression that the ladder reference exists and is wired)

- [ ] **Step 1: Write the failing test** (append to `tests/test_build_proposal.py`)

```python
def test_frequency_advisor_reference_exists_and_has_ladder():
    refs = pathlib.Path(__file__).resolve().parent.parent / "skills" / "scope-calculator" / "references"
    doc = (refs / "frequency-advisor.md").read_text().lower()
    for layer in ("baseline inventory", "inventory refresh", "compliance", "release catch", "critical watch"):
        assert layer in doc
    for pct in ("100%", "50%", "15%", "5%", "1%"):
        assert pct in doc
```

- [ ] **Step 2: Run to verify failure**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_build_proposal.py -q -k frequency_advisor`
Expected: FAIL — file not found.

- [ ] **Step 3: Write `frequency-advisor.md`** (the ladder, rationales, anchor-high defaults, pull-back guidance — content from spec §5)

```markdown
# Frequency advisor (the cadence ladder)

Cadence is proposed like an advisor, not "plopped." Open with all five layers at the anchor-high
default; walk the rep through each (keep / adjust % / drop). Every retained layer carries its
customer-facing **"why"** into the proposal and the model. The customer negotiates DOWN from the
anchor — in the live model they can do it themselves.

| Layer (`name`) | Cadence (`runs_per_year`) | The "why" (customer-facing) | Anchor-high default `pct` | Targets |
|---|---|---|---|---|
| Baseline inventory | Annual · 1 | A full sweep so nothing on the site is invisible — your lay of the land. | 100% | Entire footprint |
| Inventory refresh | Quarterly · 4 | Sites drift — new sections, campaigns, redirects. Quarterly keeps the full picture current. | 50% | Broad cross-section |
| Compliance / quality audit | Monthly · 12 | Monthly audit of the meaningful body of the site for tag health & consent compliance. | 15% | Key templates & high-value sections |
| Release catch | Weekly · 52 | Aligned to release cadence — catches tags/consent breaking shortly after a deploy. | 5% | Actively-changing / recently-released |
| Critical watch | Daily · 365 | Crown-jewel pages — highest traffic, revenue, visibility. A failure here is most expensive, so check daily. | 1% | Top revenue / traffic / consent-critical |

**Blend:** Σ(pct × runs_per_year) ≈ **11 scans/footprint-page/year** at the default (× geo × scenario
× environment multipliers). A deliberately strong anchor.

**Layers are additive** — a daily page is also in the annual baseline; `compute_scope.py` sums them.
Cadence layers feed `compute_scope.py` as `[{name, pct, runs_per_year, why}]` (the `why` rides along
to the deliverables; it is not used in math).

**Pulling back (when the customer can't fund the anchor):** trim in this order — (1) drop *Critical
watch* to fewer pages or remove it; (2) reduce *Release catch* %; (3) reduce *Inventory refresh* to
quarterly-of-a-smaller-slice; keep *Baseline inventory* (the floor — always recommend ≥1 full sweep/yr).

**"I don't know" →** keep the default for that layer and add an assumption-to-verify.
```

- [ ] **Step 4: Run to verify pass**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_build_proposal.py -q -k frequency_advisor`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" add observepoint-revenue/skills/scope-calculator/references/frequency-advisor.md observepoint-revenue/tests/test_build_proposal.py
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" commit -m "docs(scope-calculator): frequency-advisor ladder reference"
```

---

## Task 7: `SKILL.md` advisor flow + reference pointers

Rework `SKILL.md` into the phase-based advisor flow (spec §4): audience question up front, automated page count + the anchor/dominance guard (already present from `c6ac67c` — keep), recommend-first soft-input elicitation, the frequency-ladder walk, model + price, and the **three** deliverables. This is prose/behavior; verified by the full suite staying green and subagent pressure tests.

**Files:**
- Modify: `skills/scope-calculator/SKILL.md`
- Modify: `skills/scope-calculator/references/usage-methodology.md` (cadence section → "see frequency-advisor.md")
- Modify: `skills/scope-calculator/references/deliverables-mapping.md` (three-file mapping incl. `build_internal_evidence.py`, `build_model.py` placeholder noted for Phase B)

- [ ] **Step 1: Edit `SKILL.md` — Stage 2 + Stage 3.**
  - Stage 2 step 1–3: replace the silent use-case-profile cadence with the advisor walk — "Set cadence via the frequency ladder (`$REFS/frequency-advisor.md`): open at the anchor-high default, walk each layer (keep/adjust %/drop), capture each layer's `why`." Soft inputs (use case, geos, scenarios, environments) become recommend-first with an explicit "I don't know → labeled default + assumption" instruction.
  - Add a **Phase 0 audience** line at the top of the flow: "Ask up front whether these files will reach the customer (default: yes). Customer files are clean by construction; all internal context goes to the internal-evidence file."
  - Stage 3: replace "Produce BOTH files" with **three** files — proposal `.docx` (clean), customer workbook `.xlsx` (clean), and `build_internal_evidence.py` → `<Customer> - internal evidence.xlsx` (rep-only, never sent). Update the script list (line 10) to include `customer_clean.py` and `build_internal_evidence.py`.
  - Red Flags: add "I'll show the customer the confidence/derivation" → that's the internal file; customer files are clean by construction.

- [ ] **Step 2: Edit `usage-methodology.md`** — replace the cadence-layer/use-case-profile subsection with a pointer: "Cadence is now driven by the frequency advisor — see `frequency-advisor.md`. Multipliers and the ask-the-customer map below are unchanged." Keep §multipliers and the ask map.

- [ ] **Step 3: Edit `deliverables-mapping.md`** — document three outputs and which JSON feeds each: proposal (`build_proposal.py`), customer workbook (`build_evidence_appendix.py`), internal evidence (`build_internal_evidence.py`). Note cadence layers now carry a `why` field. Note `build_model.py` (live model) supersedes the customer workbook in Phase B.

- [ ] **Step 4: Run the FULL suite — nothing regressed**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q`
Expected: PASS (≥ 166 + the new tests from Tasks 1–6).

- [ ] **Step 5: Subagent pressure test (RED-first behavior check).** Dispatch a subagent with the reworked skill and a scoping scenario; verify it (a) asks the audience question, (b) elicits soft inputs recommend-first and accepts "I don't know" with a logged assumption, (c) opens cadence at the anchor-high ladder and lets layers be dropped, (d) produces three files with the internal one separate, (e) leaks no internal term into a customer file. Record gaps in a rationalization table in the skill if found.

- [ ] **Step 6: Commit**

```bash
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" add observepoint-revenue/skills/scope-calculator/SKILL.md observepoint-revenue/skills/scope-calculator/references/usage-methodology.md observepoint-revenue/skills/scope-calculator/references/deliverables-mapping.md
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" commit -m "feat(scope-calculator): advisor-flow SKILL.md + reference pointers"
```

---

## Self-review (against spec)

- **§5 frequency advisor** → Tasks 3 (proposal why-column), 5 (workbook why), 6 (ladder reference), 7 (SKILL walk). ✓
- **§6 soft-input elicitation** → Task 7 (recommend-first + "I don't know"). ✓
- **§8 artifacts + split** → Tasks 3 (clean doc), 4 (internal file), 5 (clean workbook). ✓
- **§8.1 vocabulary scrub** → Tasks 1 (guard+map), 2/3/5 (wired). ✓
- **§9.2 dominance flag** → Task 4 (`dominant_host` + surfaced in internal file). ✓ (full Phase-1 wiring is Phase C)
- **§9.3 invariant + recursion exclusion in internal file** → Task 4 (`_check_invariant`). ✓
- **Architecture principle (no LLM math)** → no change to `compute_scope.py`; new scripts only render. ✓

**Gaps deferred (by design):** the live formula model (`build_model.py`) is Phase B; Phase-1 anchor-guard *flow wiring* + confirmation gate is Phase C. Noted in spec §11.

**Placeholder scan:** none — all code blocks are complete; the one fixture caveat (negative-dominance must use a 3-domain balanced split) is called out explicitly in Task 4 Step 1.

**Type consistency:** `dominant_host(data)`, `build_workbook(data)`, `find_forbidden/assert_clean(strings, where=)`, cadence `why` field — consistent across Tasks 1, 4, 5.
