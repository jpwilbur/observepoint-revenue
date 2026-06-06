# ObservePoint Revenue — Scope Calculator Engine (Plan 1 of 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the deterministic Python engine and plugin scaffold that turns scope inputs into an annual page-scan usage number and a live, authoritative ObservePoint price, plus a customer evidence appendix workbook.

**Architecture:** Three self-contained Python scripts inside an `observepoint-revenue` Claude Code plugin. `compute_scope.py` owns all usage/price math (and the baked fallback tier table — the single source of truth). `fetch_pricing.py` pulls ObservePoint's live graduated tiers from the public pricing-app JS bundle, validates them, and falls back to baked. `build_evidence_appendix.py` renders the per-domain Site Census evidence into a 4-sheet `.xlsx`. All math is pure-function + CLI so it is reproducible and unit-tested with pytest; no LLM arithmetic. Plan 2 (separate) adds the three SKILL.md orchestration layers that call these scripts.

**Tech Stack:** Python 3 (stdlib `urllib`, `re`, `json`), `openpyxl` for `.xlsx`, `pytest` for tests.

**Reference spec:** `docs/superpowers/specs/2026-06-06-op-revenue-scope-calculator-design.md`

---

## File Structure

```
observepoint-revenue/
├── .claude-plugin/plugin.json                         # plugin manifest
├── requirements.txt                                   # openpyxl, pytest
├── skills/
│   ├── derive-page-count/scripts/build_evidence_appendix.py   # per-domain JSON → evidence .xlsx
│   └── size-and-price/scripts/
│       ├── compute_scope.py                           # math + BAKED_TIERS + CLI
│       └── fetch_pricing.py                            # live tier fetch/parse/validate + fallback + CLI
└── tests/
    ├── conftest.py                                     # puts scripts dirs on sys.path
    ├── test_compute_scope.py
    ├── test_fetch_pricing.py
    └── test_build_evidence_appendix.py
```

Responsibilities: `compute_scope.py` = all numeric truth; `fetch_pricing.py` = network + parse only (delegates math to compute_scope's table); `build_evidence_appendix.py` = presentation of Part-1 data, with the sum-to-anchor invariant. SKILL.md files are intentionally NOT in this plan.

All commands below assume the working directory `/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill`. Run tests from there with `python3 -m pytest`.

---

### Task 0: Plugin scaffold + dev setup

**Files:**
- Create: `observepoint-revenue/.claude-plugin/plugin.json`
- Create: `observepoint-revenue/requirements.txt`
- Create: `observepoint-revenue/tests/conftest.py`
- Create: `observepoint-revenue/skills/size-and-price/scripts/.gitkeep`
- Create: `observepoint-revenue/skills/derive-page-count/scripts/.gitkeep`

- [ ] **Step 1: Create the directory tree**

Run:
```bash
cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill"
mkdir -p observepoint-revenue/.claude-plugin \
         observepoint-revenue/skills/size-and-price/scripts \
         observepoint-revenue/skills/derive-page-count/scripts \
         observepoint-revenue/tests
touch observepoint-revenue/skills/size-and-price/scripts/.gitkeep \
      observepoint-revenue/skills/derive-page-count/scripts/.gitkeep
```

- [ ] **Step 2: Write the plugin manifest**

Create `observepoint-revenue/.claude-plugin/plugin.json`:
```json
{
  "name": "observepoint-revenue",
  "version": "0.1.0",
  "description": "ObservePoint revenue-team tooling. First capability: a contract scope calculator that derives a defensible page count, sizes annual usage, prices it against ObservePoint's live pricing, and produces a customer proposal plus an evidence appendix."
}
```

- [ ] **Step 3: Write requirements.txt**

Create `observepoint-revenue/requirements.txt`:
```
openpyxl>=3.1
pytest>=8.0
```

- [ ] **Step 4: Install pytest (openpyxl already present)**

Run: `python3 -m pip install -r observepoint-revenue/requirements.txt`
Expected: pytest installs successfully (openpyxl already satisfied).

- [ ] **Step 5: Write the test path shim**

Create `observepoint-revenue/tests/conftest.py`:
```python
"""Put the hyphenated skill script dirs on sys.path so tests can `import` the
script modules directly (compute_scope, fetch_pricing, build_evidence_appendix)."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent  # observepoint-revenue/
for rel in (
    "skills/size-and-price/scripts",
    "skills/derive-page-count/scripts",
):
    sys.path.insert(0, str(ROOT / rel))
```

- [ ] **Step 6: Verify pytest collects (no tests yet is fine)**

Run: `cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill" && python3 -m pytest observepoint-revenue/tests -q`
Expected: "no tests ran" (exit code 5) — confirms pytest + conftest load without error.

- [ ] **Step 7: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill"
git add observepoint-revenue/.claude-plugin observepoint-revenue/requirements.txt observepoint-revenue/tests/conftest.py observepoint-revenue/skills
git commit -m "chore: scaffold observepoint-revenue plugin + test harness"
```

---

### Task 1: Graduated pricing math + baked tier table (`compute_scope.py`)

**Files:**
- Create: `observepoint-revenue/skills/size-and-price/scripts/compute_scope.py`
- Test: `observepoint-revenue/tests/test_compute_scope.py`

- [ ] **Step 1: Write the failing tests**

Create `observepoint-revenue/tests/test_compute_scope.py`:
```python
import compute_scope as cs


def test_baked_tiers_shape():
    assert cs.BAKED_TIERS[0] == {"limit": 1_000, "pricePerPage": 0.0}
    assert cs.BAKED_TIERS[1]["pricePerPage"] == 0.17
    assert len(cs.BAKED_TIERS) == 6


def test_graduated_price_calibration():
    # Spec §10 fixture: 1,664,256 annual scans through the baked tiers.
    p = cs.graduated_price(1_664_256, cs.BAKED_TIERS)
    assert p["total"] == 133_030.24
    assert p["avg_per_page"] == 0.0799
    # bands hit: free, 0.17, 0.12, 0.06, 0.04 (tail) = 5 priced bands
    assert len(p["breakdown"]) == 5
    assert p["breakdown"][1]["cost"] == 8_500.0   # 50,000 @ 0.17


def test_graduated_price_free_tier():
    p = cs.graduated_price(500, cs.BAKED_TIERS)
    assert p["total"] == 0.0


def test_graduated_price_first_paid_band():
    # 1,000 free + 9,000 @ 0.17
    p = cs.graduated_price(10_000, cs.BAKED_TIERS)
    assert p["total"] == round(9_000 * 0.17, 2)  # 1530.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill" && python3 -m pytest observepoint-revenue/tests/test_compute_scope.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'compute_scope'`.

- [ ] **Step 3: Create compute_scope.py with the tier table + graduated math**

Create `observepoint-revenue/skills/size-and-price/scripts/compute_scope.py`:
```python
"""Deterministic scope / usage / price engine for the ObservePoint scope-calculator.

No network and no LLM arithmetic. Pure functions plus a CLI that reads an inputs
JSON (file arg or stdin) and writes a full breakdown JSON to stdout.
"""
import json
import sys

# Spec §4.4 — last-known-good graduated audit page-scan tiers (band width, rate/page).
# Single source of truth for the baked fallback; fetch_pricing imports this.
BAKED_TIERS = [
    {"limit": 1_000,      "pricePerPage": 0.0},
    {"limit": 50_000,     "pricePerPage": 0.17},
    {"limit": 500_000,    "pricePerPage": 0.12},
    {"limit": 1_000_000,  "pricePerPage": 0.06},
    {"limit": 5_000_000,  "pricePerPage": 0.04},
    {"limit": 50_000_000, "pricePerPage": 0.03},
]
BAKED_AS_OF = "2026-06-06"


def graduated_price(scans, tiers):
    """Graduated/marginal price: each band's width priced at its rate, summed.
    Mirrors the website's calculateTierBreakdown exactly. Returns
    {total, breakdown:[{band_limit, rate, pages, cost}], avg_per_page}."""
    remaining = int(scans)
    breakdown = []
    total = 0.0
    for band in tiers:
        pages = min(band["limit"], remaining)
        if pages <= 0:
            continue
        cost = pages * band["pricePerPage"]
        total += cost
        remaining -= pages
        breakdown.append({
            "band_limit": band["limit"],
            "rate": band["pricePerPage"],
            "pages": pages,
            "cost": round(cost, 2),
        })
        if remaining <= 0:
            break
    if remaining > 0:  # beyond defined bands: price the tail at the last band's rate
        rate = tiers[-1]["pricePerPage"]
        cost = remaining * rate
        total += cost
        breakdown.append({"band_limit": None, "rate": rate, "pages": remaining, "cost": round(cost, 2)})
    avg = round(total / scans, 4) if scans else 0.0
    return {"total": round(total, 2), "breakdown": breakdown, "avg_per_page": avg}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill" && python3 -m pytest observepoint-revenue/tests/test_compute_scope.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill"
git add observepoint-revenue/skills/size-and-price/scripts/compute_scope.py observepoint-revenue/tests/test_compute_scope.py
git commit -m "feat: graduated pricing math + baked tier table"
```

---

### Task 2: Tier classifier (`classify_tier`)

**Files:**
- Modify: `observepoint-revenue/skills/size-and-price/scripts/compute_scope.py`
- Test: `observepoint-revenue/tests/test_compute_scope.py`

- [ ] **Step 1: Add failing tests**

Append to `observepoint-revenue/tests/test_compute_scope.py`:
```python
def test_classify_tier_boundaries():
    assert cs.classify_tier(599_999) == "starter"
    assert cs.classify_tier(600_000) == "professional"   # n < 600k is starter; 600k is not
    assert cs.classify_tier(6_000_000) == "professional"  # <= 6M
    assert cs.classify_tier(6_000_001) == "enterprise"
    assert cs.classify_tier(1_664_256) == "professional"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill" && python3 -m pytest observepoint-revenue/tests/test_compute_scope.py::test_classify_tier_boundaries -q`
Expected: FAIL — `AttributeError: module 'compute_scope' has no attribute 'classify_tier'`.

- [ ] **Step 3: Implement classify_tier**

Append to `compute_scope.py` (after `graduated_price`):
```python
def classify_tier(scans):
    """Website $F classifier: starter < 600k <= professional <= 6M < enterprise."""
    if scans < 600_000:
        return "starter"
    if scans <= 6_000_000:
        return "professional"
    return "enterprise"
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill" && python3 -m pytest observepoint-revenue/tests/test_compute_scope.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill"
git add -A && git commit -m "feat: tier classifier (starter/professional/enterprise)"
```

---

### Task 3: Multipliers, layered cadence, buffer (`use_case_pages`, `annual_scans`, `apply_buffer`)

**Files:**
- Modify: `observepoint-revenue/skills/size-and-price/scripts/compute_scope.py`
- Test: `observepoint-revenue/tests/test_compute_scope.py`

- [ ] **Step 1: Add failing tests**

Append to `observepoint-revenue/tests/test_compute_scope.py`:
```python
CALIBRATION_LAYERS = [
    {"name": "annual baseline", "pct": 1.0,   "runs_per_year": 1},
    {"name": "quarterly",       "pct": 0.05,  "runs_per_year": 4},
    {"name": "weekly",          "pct": 0.004, "runs_per_year": 52},
    {"name": "daily",           "pct": 0.0,   "runs_per_year": 365},
]


def test_use_case_pages():
    assert cs.use_case_pages(197_000, geographies=2, scenarios=3, environments=1) == 1_182_000


def test_annual_scans_layered_calibration():
    # Spec §10: 1,182,000 use-case pages through the calibration cadence = 1,664,256.
    out = cs.annual_scans(1_182_000, CALIBRATION_LAYERS)
    assert out["total"] == 1_664_256
    by = {l["name"]: l["runs"] for l in out["by_layer"]}
    assert by["annual baseline"] == 1_182_000
    assert by["quarterly"] == 236_400
    assert by["weekly"] == 245_856
    assert by["daily"] == 0


def test_apply_buffer():
    assert cs.apply_buffer(100_000, 0.10) == 110_000
    assert cs.apply_buffer(1_664_256, 0.0) == 1_664_256          # no-op
    assert cs.apply_buffer(1_664_256, 0.10) == 1_830_682          # round(…*1.1)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill" && python3 -m pytest observepoint-revenue/tests/test_compute_scope.py -k "use_case_pages or annual_scans or apply_buffer" -q`
Expected: FAIL — `AttributeError: module 'compute_scope' has no attribute 'use_case_pages'`.

- [ ] **Step 3: Implement the three functions**

Append to `compute_scope.py` (after `classify_tier`):
```python
def use_case_pages(base_pages, geographies=1, scenarios=1, environments=1.0):
    """base × geos × scenarios × environments (geos×scenarios = the website's
    geoPersonaMultiplier; environments is 1 or 1.5)."""
    return base_pages * geographies * scenarios * environments


def annual_scans(ucp, cadence_layers):
    """Additive layered cadence model. cadence_layers: list of
    {name, pct, runs_per_year}. A page may appear in multiple layers (layers are
    additive). Returns {total, by_layer:[{name, pct, runs_per_year, pages, runs}]}."""
    by_layer = []
    total = 0.0
    for layer in cadence_layers:
        pages = ucp * layer["pct"]
        runs = pages * layer["runs_per_year"]
        total += runs
        by_layer.append({
            "name": layer["name"],
            "pct": layer["pct"],
            "runs_per_year": layer["runs_per_year"],
            "pages": round(pages, 2),
            "runs": round(runs, 2),
        })
    return {"total": round(total), "by_layer": by_layer}


def apply_buffer(scans, buffer_pct=0.0):
    """purchased = round(predicted × (1 + buffer))."""
    return round(scans * (1 + buffer_pct))
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill" && python3 -m pytest observepoint-revenue/tests/test_compute_scope.py -q`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill"
git add -A && git commit -m "feat: multipliers, layered cadence, buffer"
```

---

### Task 4: End-to-end `compute()` + range propagation + reconciliation + CLI

**Files:**
- Modify: `observepoint-revenue/skills/size-and-price/scripts/compute_scope.py`
- Test: `observepoint-revenue/tests/test_compute_scope.py`

- [ ] **Step 1: Add failing tests**

Append to `observepoint-revenue/tests/test_compute_scope.py`:
```python
import json
import subprocess
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMPUTE = ROOT / "skills" / "size-and-price" / "scripts" / "compute_scope.py"

BASE_INPUTS = {
    "customer": "Acme",
    "use_case": "privacy",
    "page_count": {"low": 180_000, "anchor": 197_000, "high": 210_000, "confidence": "MEDIUM"},
    "multipliers": {"geographies": 2, "scenarios": 3, "environments": 1},
    "cadence_layers": CALIBRATION_LAYERS,
    "buffer_pct": 0.0,
}


def test_compute_anchor_calibration():
    out = cs.compute(BASE_INPUTS)
    a = out["anchor"]
    assert a["use_case_pages"] == 1_182_000
    assert a["predicted_scans"] == 1_664_256
    assert a["purchased_scans"] == 1_664_256
    assert a["tier"] == "professional"
    assert a["price"]["total"] == 133_030.24
    assert a["implied_blended_frequency"] == round(1_664_256 / 1_182_000, 3)
    assert out["recommended_quote"]["price_total"] == 133_030.24
    assert out["pricing_source"].startswith("baked")  # no tiers passed → baked


def test_compute_range_is_monotonic():
    out = cs.compute(BASE_INPUTS)
    lo, hi = out["range"]["low"], out["range"]["high"]
    assert lo["purchased_scans"] < out["anchor"]["purchased_scans"] < hi["purchased_scans"]
    assert lo["price_total"] < out["anchor"]["price"]["total"] < hi["price_total"]


def test_compute_buffer_changes_purchased():
    inp = dict(BASE_INPUTS, buffer_pct=0.10)
    out = cs.compute(inp)
    assert out["anchor"]["predicted_scans"] == 1_664_256
    assert out["anchor"]["purchased_scans"] == 1_830_682
    assert out["anchor"]["price"]["total"] > 133_030.24


def test_compute_uses_passed_tiers_and_source():
    inp = dict(BASE_INPUTS, tiers=cs.BAKED_TIERS, pricing_source="live @ test")
    out = cs.compute(inp)
    assert out["pricing_source"] == "live @ test"


def test_cli_reads_json_writes_json(tmp_path):
    f = tmp_path / "in.json"
    f.write_text(json.dumps(BASE_INPUTS))
    res = subprocess.run([sys.executable, str(COMPUTE), str(f)],
                         capture_output=True, text=True)
    assert res.returncode == 0
    out = json.loads(res.stdout)
    assert out["anchor"]["price"]["total"] == 133_030.24
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill" && python3 -m pytest observepoint-revenue/tests/test_compute_scope.py -k compute_anchor -q`
Expected: FAIL — `AttributeError: module 'compute_scope' has no attribute 'compute'`.

- [ ] **Step 3: Implement compute() + helper + CLI main()**

Append to `compute_scope.py` (after `apply_buffer`):
```python
def _compute_one(base, m, layers, buffer_pct, tiers):
    ucp = use_case_pages(base, m.get("geographies", 1), m.get("scenarios", 1),
                         m.get("environments", 1))
    sc = annual_scans(ucp, layers)
    predicted = sc["total"]
    purchased = apply_buffer(predicted, buffer_pct)
    return {
        "base_pages": base,
        "use_case_pages": round(ucp),
        "predicted_scans": predicted,
        "purchased_scans": purchased,
        "buffer_pct": buffer_pct,
        "cadence_by_layer": sc["by_layer"],
        "implied_blended_frequency": round(predicted / ucp, 3) if ucp else 0,
        "tier": classify_tier(purchased),
        "price": graduated_price(purchased, tiers),
    }


def compute(inputs):
    """Full scope breakdown over the page-count range (low/anchor/high)."""
    pc = inputs["page_count"]
    m = inputs.get("multipliers", {})
    layers = inputs["cadence_layers"]
    buffer_pct = inputs.get("buffer_pct", 0.0)
    tiers = inputs.get("tiers") or BAKED_TIERS

    anchor = _compute_one(pc["anchor"], m, layers, buffer_pct, tiers)
    low = _compute_one(pc["low"], m, layers, buffer_pct, tiers)
    high = _compute_one(pc["high"], m, layers, buffer_pct, tiers)

    return {
        "customer": inputs.get("customer"),
        "use_case": inputs.get("use_case"),
        "pricing_source": inputs.get("pricing_source", f"baked ({BAKED_AS_OF})"),
        "confidence": pc.get("confidence"),
        "multipliers": {
            "geographies": m.get("geographies", 1),
            "scenarios": m.get("scenarios", 1),
            "environments": m.get("environments", 1),
            "combined_geo_persona": m.get("geographies", 1) * m.get("scenarios", 1),
        },
        "anchor": anchor,
        "range": {
            "low": {"predicted_scans": low["predicted_scans"],
                    "purchased_scans": low["purchased_scans"],
                    "price_total": low["price"]["total"]},
            "high": {"predicted_scans": high["predicted_scans"],
                     "purchased_scans": high["purchased_scans"],
                     "price_total": high["price"]["total"]},
        },
        "recommended_quote": {
            "purchased_scans": anchor["purchased_scans"],
            "price_total": anchor["price"]["total"],
            "tier": anchor["tier"],
        },
    }


def main(argv):
    raw = open(argv[1]).read() if len(argv) > 1 else sys.stdin.read()
    print(json.dumps(compute(json.loads(raw)), indent=2))


if __name__ == "__main__":
    main(sys.argv)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill" && python3 -m pytest observepoint-revenue/tests/test_compute_scope.py -q`
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill"
git add -A && git commit -m "feat: end-to-end compute() with range, reconciliation, CLI"
```

---

### Task 5: Live pricing fetch / parse / validate / fallback (`fetch_pricing.py`)

**Files:**
- Create: `observepoint-revenue/skills/size-and-price/scripts/fetch_pricing.py`
- Test: `observepoint-revenue/tests/test_fetch_pricing.py`

- [ ] **Step 1: Write the failing tests**

Create `observepoint-revenue/tests/test_fetch_pricing.py`:
```python
import json
import subprocess
import sys
import pathlib

import fetch_pricing as fp
import compute_scope as cs

ROOT = pathlib.Path(__file__).resolve().parent.parent
FETCH = ROOT / "skills" / "size-and-price" / "scripts" / "fetch_pricing.py"

# Representative snippet copied from the live bundle (app.observepoint.com/www-pricing/main.js).
SAMPLE_JS = (
    'var Gt=[{limit:1e3,pricePerPage:0},{limit:5e4,pricePerPage:.17},'
    '{limit:5e5,pricePerPage:.12},{limit:1e6,pricePerPage:.06},'
    '{limit:5e6,pricePerPage:.04},{limit:5e7,pricePerPage:.03}],Nn=1e3,Jr=5e7'
)


def test_parse_tiers_from_sample():
    tiers = fp.parse_tiers(SAMPLE_JS)
    assert tiers == [
        {"limit": 1_000, "pricePerPage": 0.0},
        {"limit": 50_000, "pricePerPage": 0.17},
        {"limit": 500_000, "pricePerPage": 0.12},
        {"limit": 1_000_000, "pricePerPage": 0.06},
        {"limit": 5_000_000, "pricePerPage": 0.04},
        {"limit": 50_000_000, "pricePerPage": 0.03},
    ]


def test_parse_tiers_missing_returns_none():
    assert fp.parse_tiers("no pricing here") is None


def test_validate_tiers():
    assert fp.validate_tiers(cs.BAKED_TIERS) is True
    assert fp.validate_tiers(None) is False
    assert fp.validate_tiers(cs.BAKED_TIERS[:3]) is False                  # < 5 bands
    bad = [dict(b) for b in cs.BAKED_TIERS]; bad[2]["limit"] = 10          # non-monotonic
    assert fp.validate_tiers(bad) is False


def test_fetch_pricing_live():
    out = fp.fetch_pricing(fetcher=lambda url: SAMPLE_JS)
    assert out["source"].startswith("live")
    assert out["tiers"][1]["pricePerPage"] == 0.17


def test_fetch_pricing_fallback_on_error():
    def boom(url):
        raise RuntimeError("network down")
    out = fp.fetch_pricing(fetcher=boom)
    assert out["source"].startswith("fallback")
    assert out["tiers"] == cs.BAKED_TIERS


def test_fetch_pricing_fallback_on_garbage():
    out = fp.fetch_pricing(fetcher=lambda url: "garbage")
    assert out["source"].startswith("fallback")
    assert out["tiers"] == cs.BAKED_TIERS


def test_cli_emits_json():
    res = subprocess.run([sys.executable, str(FETCH), "--offline"],
                         capture_output=True, text=True)
    assert res.returncode == 0
    out = json.loads(res.stdout)
    assert "tiers" in out and "source" in out
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill" && python3 -m pytest observepoint-revenue/tests/test_fetch_pricing.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'fetch_pricing'`.

- [ ] **Step 3: Implement fetch_pricing.py**

Create `observepoint-revenue/skills/size-and-price/scripts/fetch_pricing.py`:
```python
"""Fetch ObservePoint's live graduated pricing tiers from the public pricing-app
JS bundle, validate them, and fall back to the baked table on any failure.

The math and the baked table live in compute_scope (single source of truth);
this module only does network + parsing.
"""
import json
import re
import sys
import urllib.request

from compute_scope import BAKED_TIERS, BAKED_AS_OF

BUNDLE_URL = "https://app.observepoint.com/www-pricing/main.js"
_GT_RE = re.compile(r"Gt=\[(\{limit:.*?\})\]")
_BAND_RE = re.compile(r"\{limit:([\deE.+-]+),pricePerPage:([\d.]+)\}")


def parse_tiers(js_text):
    """Extract the Gt=[...] tier array from bundle text → list of
    {limit, pricePerPage}, or None if not found."""
    m = _GT_RE.search(js_text)
    if not m:
        return None
    bands = [
        {"limit": int(float(limit_s)), "pricePerPage": float(rate_s)}
        for limit_s, rate_s in _BAND_RE.findall(m.group(1))
    ]
    return bands or None


def validate_tiers(tiers):
    """Sanity gate: >= 5 bands, strictly increasing limits, non-negative rates."""
    if not tiers or len(tiers) < 5:
        return False
    if any(b["pricePerPage"] < 0 for b in tiers):
        return False
    limits = [b["limit"] for b in tiers]
    return all(a < b for a, b in zip(limits, limits[1:]))


def _default_fetcher(url):
    with urllib.request.urlopen(url, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def fetch_pricing(fetcher=_default_fetcher, url=BUNDLE_URL):
    """Return {tiers, source}. Live tiers on success+valid; baked fallback otherwise."""
    try:
        tiers = parse_tiers(fetcher(url))
        if validate_tiers(tiers):
            return {"tiers": tiers, "source": f"live @ {url}"}
    except Exception:
        pass
    return {"tiers": BAKED_TIERS, "source": f"fallback (baked {BAKED_AS_OF})"}


def main(argv):
    if "--offline" in argv:  # test/dev hook: skip the network, force fallback path
        out = fetch_pricing(fetcher=lambda url: "")
    else:
        out = fetch_pricing()
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main(sys.argv)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill" && python3 -m pytest observepoint-revenue/tests/test_fetch_pricing.py -q`
Expected: 7 passed.

- [ ] **Step 5: (Optional) live smoke check**

Run: `python3 "observepoint-revenue/skills/size-and-price/scripts/fetch_pricing.py"`
Expected: JSON with `"source": "live @ https://app.observepoint.com/www-pricing/main.js"` and 6 tiers. If you see `fallback`, the bundle shape changed — note it but do not block (the fallback is correct behavior).

- [ ] **Step 6: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill"
git add observepoint-revenue/skills/size-and-price/scripts/fetch_pricing.py observepoint-revenue/tests/test_fetch_pricing.py
git commit -m "feat: live pricing fetch with validation and baked fallback"
```

---

### Task 6: Evidence appendix workbook (`build_evidence_appendix.py`)

**Files:**
- Create: `observepoint-revenue/skills/derive-page-count/scripts/build_evidence_appendix.py`
- Test: `observepoint-revenue/tests/test_build_evidence_appendix.py`

- [ ] **Step 1: Write the failing tests**

Create `observepoint-revenue/tests/test_build_evidence_appendix.py`:
```python
import json
import subprocess
import sys
import pathlib

import pytest
from openpyxl import load_workbook

import build_evidence_appendix as bea

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "derive-page-count" / "scripts" / "build_evidence_appendix.py"

DATA = {
    "customer": "Acme",
    "rollup": {
        "url_total": 268_042, "path_floor": 1_900, "spiral_adjusted_anchor": 2_661,
        "low": 2_500, "high": 3_000, "confidence": "MEDIUM",
        "census_ids": [711], "crawl_status": "paused",
    },
    "per_domain": [
        {"hostname": "www.1stagency.com", "raw_urls": 266_042, "paths": 761,
         "patterns": 120, "spiral_flag": True, "spiral_ratio": 349.0,
         "defensible_pages": 761, "discounted": 265_281,
         "why": "349x query-param spiral",
         "url_samples": ["https://www.1stagency.com/", "https://www.1stagency.com/about"]},
        {"hostname": "shop.acme.com", "raw_urls": 2_000, "paths": 1_900,
         "patterns": 90, "spiral_flag": False, "spiral_ratio": 1.05,
         "defensible_pages": 1_900, "discounted": 100, "why": "",
         "url_samples": ["https://shop.acme.com/p/1"]},
    ],
}


def test_invariant_raises_on_mismatch():
    bad = json.loads(json.dumps(DATA))
    bad["rollup"]["spiral_adjusted_anchor"] = 9_999  # != 761 + 1900
    with pytest.raises(ValueError):
        bea.build_workbook(bad)


def test_workbook_structure(tmp_path):
    wb = bea.build_workbook(DATA)
    assert wb.sheetnames == ["Scope Summary", "Pages by Domain", "Raw Evidence", "URL Samples"]

    pbd = wb["Pages by Domain"]
    assert [c.value for c in pbd[1]] == [
        "Domain", "Defensible pages", "Spiral?", "Include in scope?", "Priority", "Notes"]
    assert pbd[2][0].value == "www.1stagency.com"
    assert pbd[2][1].value == 761
    assert pbd[2][2].value == "Yes"
    # customer-fillable columns present and empty
    assert pbd[2][3].value is None and pbd[2][4].value is None and pbd[2][5].value is None

    raw = wb["Raw Evidence"]
    assert raw[2][1].value == 266_042            # raw distinct URLs
    assert raw[2][5].value == "349x query-param spiral"

    samples = wb["URL Samples"]
    assert samples.max_row == 1 + 2 + 1          # header + 2 + 1 sample rows


def test_cli_writes_file(tmp_path):
    f = tmp_path / "in.json"; f.write_text(json.dumps(DATA))
    out = tmp_path / "evidence.xlsx"
    res = subprocess.run([sys.executable, str(SCRIPT), str(f), str(out)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    wb = load_workbook(out)
    assert "Scope Summary" in wb.sheetnames
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill" && python3 -m pytest observepoint-revenue/tests/test_build_evidence_appendix.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'build_evidence_appendix'`.

- [ ] **Step 3: Implement build_evidence_appendix.py**

Create `observepoint-revenue/skills/derive-page-count/scripts/build_evidence_appendix.py`:
```python
"""Render the customer-facing evidence appendix .xlsx from Site Census per-domain
data. Enforces the spec §4.6 invariant: per-domain defensible_pages must sum to
the rolled-up anchor."""
import json
import sys

from openpyxl import Workbook
from openpyxl.styles import Font

FILL_COLS = ["Include in scope?", "Priority", "Notes"]  # customer-fillable, left empty


def _check_invariant(data):
    total = sum(d["defensible_pages"] for d in data["per_domain"])
    anchor = data["rollup"]["spiral_adjusted_anchor"]
    if total != anchor:
        raise ValueError(
            f"per-domain defensible_pages sum {total} != rollup anchor {anchor}")


def _bold_header(ws):
    for c in ws[1]:
        c.font = Font(bold=True)


def build_workbook(data):
    _check_invariant(data)
    domains = data["per_domain"]
    r = data["rollup"]
    raw_total = sum(d["raw_urls"] for d in domains)
    def_total = sum(d["defensible_pages"] for d in domains)

    wb = Workbook()

    ss = wb.active
    ss.title = "Scope Summary"
    for row in [
        ["ObservePoint — Page-Count Evidence", ""],
        ["Customer", data.get("customer", "")],
        ["Census ID(s)", ", ".join(str(c) for c in r.get("census_ids", []))],
        ["Crawl status", r.get("crawl_status", "")],
        ["Confidence", r.get("confidence", "")],
        ["", ""],
        ["Defensible pages — low", r.get("low", "")],
        ["Defensible pages — anchor (recommended)", r.get("spiral_adjusted_anchor", "")],
        ["Defensible pages — high", r.get("high", "")],
        ["", ""],
        ["Total raw URLs crawled", raw_total],
        ["Total defensible pages", def_total],
        ["Discounted (raw - defensible)", raw_total - def_total],
        ["", ""],
        ["How to use", "Review the 'Pages by Domain' tab and confirm these are the "
                       "right properties. Fill Include/Priority to validate scope. "
                       "'Raw Evidence' shows why query-param spirals were discounted."],
    ]:
        ss.append(row)
    ss["A1"].font = Font(bold=True, size=14)

    pbd = wb.create_sheet("Pages by Domain")
    pbd.append(["Domain", "Defensible pages", "Spiral?"] + FILL_COLS)
    _bold_header(pbd)
    for d in domains:
        pbd.append([d["hostname"], d["defensible_pages"],
                    "Yes" if d.get("spiral_flag") else "No", None, None, None])

    raw = wb.create_sheet("Raw Evidence")
    raw.append(["Domain", "Raw distinct URLs", "Distinct paths", "Spiral ratio",
                "Discounted", "Why"])
    _bold_header(raw)
    for d in domains:
        raw.append([d["hostname"], d["raw_urls"], d.get("paths", ""),
                    d.get("spiral_ratio", ""), d.get("discounted", ""), d.get("why", "")])

    samples = wb.create_sheet("URL Samples")
    samples.append(["Domain", "Sample URL"])
    _bold_header(samples)
    for d in domains:
        for url in d.get("url_samples", []):
            samples.append([d["hostname"], url])

    return wb


def main(argv):
    raw = open(argv[1]).read() if len(argv) > 1 else sys.stdin.read()
    out = argv[2] if len(argv) > 2 else "evidence-appendix.xlsx"
    build_workbook(json.loads(raw)).save(out)
    print(out)


if __name__ == "__main__":
    main(sys.argv)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill" && python3 -m pytest observepoint-revenue/tests/test_build_evidence_appendix.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill"
git add observepoint-revenue/skills/derive-page-count/scripts/build_evidence_appendix.py observepoint-revenue/tests/test_build_evidence_appendix.py
git commit -m "feat: evidence appendix workbook with sum-to-anchor invariant"
```

---

### Task 7: Full suite green + engine smoke run

**Files:** none (verification task)

- [ ] **Step 1: Run the entire test suite**

Run: `cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill" && python3 -m pytest observepoint-revenue/tests -q`
Expected: 23 passed (13 compute + 7 fetch + 3 appendix).

- [ ] **Step 2: End-to-end smoke (live pricing → compute → JSON)**

Run:
```bash
cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill/observepoint-revenue/skills/size-and-price/scripts"
python3 - <<'PY'
import json, fetch_pricing, compute_scope
pr = fetch_pricing.fetch_pricing()
inp = {
  "customer": "Acme", "use_case": "privacy",
  "page_count": {"low":180000,"anchor":197000,"high":210000,"confidence":"MEDIUM"},
  "multipliers": {"geographies":2,"scenarios":3,"environments":1},
  "cadence_layers": [
    {"name":"annual baseline","pct":1.0,"runs_per_year":1},
    {"name":"quarterly","pct":0.05,"runs_per_year":4},
    {"name":"weekly","pct":0.004,"runs_per_year":52},
    {"name":"daily","pct":0.0,"runs_per_year":365}],
  "buffer_pct": 0.10,
  "tiers": pr["tiers"], "pricing_source": pr["source"],
}
out = compute_scope.compute(inp)
print("source:", out["pricing_source"])
print("predicted:", out["anchor"]["predicted_scans"], "purchased:", out["anchor"]["purchased_scans"])
print("tier:", out["anchor"]["tier"], "price:", out["anchor"]["price"]["total"])
PY
```
Expected: prints a live (or fallback) source, predicted 1,664,256, purchased 1,830,682, tier professional, and a price total > $133K. Confirms the three modules compose.

- [ ] **Step 3: Commit any final touch-ups**

```bash
cd "/Users/jarrodwilbur/Documents/OP Scoping Calculator Skill"
git add -A && git commit -m "test: full engine suite green + smoke run" --allow-empty
```

---

## Self-Review

**1. Spec coverage:**
- §4.4 graduated tiers + §4.4 formula → Task 1 (`graduated_price`, `BAKED_TIERS`). ✓
- §4.4 tier classifier `$F` → Task 2. ✓
- §4.2 multipliers, §4.3 layered cadence → Task 3. ✓
- §4.7 buffer → Task 3 (`apply_buffer`) + Task 4 (compute uses purchased). ✓
- §7 range propagation + reconciliation (implied blended frequency) → Task 4. ✓
- §4.5 live fetch + validate + fallback + stamp → Task 5. ✓
- §4.6 per-domain contract + §8 evidence appendix (4 sheets, fillable cols) + sum-to-anchor invariant → Task 6. ✓
- §3 plugin scaffold → Task 0. ✓
- §10 fixtures (1,664,256 scans; $133,030.24; 100k→110k buffer; invariant) → Tasks 1/3/4/6. ✓
- NOT in this plan (by design, Plan 2): the three SKILL.md orchestration layers, references, `.docx` proposal generation, Site Census MCP calls, subagent pressure tests. The engine exposes JSON-in/JSON-out CLIs that Plan 2 will drive.

**2. Placeholder scan:** No TBD/TODO; every code and test step shows complete, runnable code; every run step states the exact command and expected result. ✓

**3. Type consistency:** `compute_scope` exposes `BAKED_TIERS`, `BAKED_AS_OF`, `graduated_price`, `classify_tier`, `use_case_pages`, `annual_scans`, `apply_buffer`, `compute`, `main`. `fetch_pricing` imports `BAKED_TIERS`/`BAKED_AS_OF` and exposes `parse_tiers`, `validate_tiers`, `fetch_pricing`, `main`. `build_evidence_appendix` exposes `build_workbook`, `main`. The `compute()` input keys (`page_count{low,anchor,high,confidence}`, `multipliers{geographies,scenarios,environments}`, `cadence_layers[{name,pct,runs_per_year}]`, `buffer_pct`, `tiers`, `pricing_source`) match between Task 4's implementation and tests, and match the evidence `rollup{spiral_adjusted_anchor,...}` / `per_domain[{hostname,raw_urls,paths,spiral_flag,spiral_ratio,defensible_pages,discounted,why,url_samples}]` shape used in Task 6 — which is the spec §4.6 contract Plan 2's Part-1 step must emit. ✓
