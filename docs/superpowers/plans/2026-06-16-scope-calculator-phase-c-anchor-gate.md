# Scope Calculator — Phase C: Stage-1 Anchor Confirmation Gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop a silently-wrong page-count anchor (e.g. the Gallagher ~15× recursion trap) from ever reaching pricing. Surface the rollup-dominance signal during Stage 1 (not just in the Stage-3 internal file), and add an explicit **anchor confirmation gate** between Stage 1 and Stage 2: every deal pauses to show the anchor + confidence + any recursion/dominance flags; a tripped flag or MEDIUM/LOW confidence is a **hard stop** the rep must acknowledge (and, for a dominant/recursion host, sample + exclude) before pricing.

**Architecture:** Honors the repo principle — the deterministic plausibility signal (dominance + confidence → confirmation directive) lives in a small Python module (`anchor_guard.py`), not in LLM judgment. `dominant_host` (currently in `build_internal_evidence.py`) moves there so Stage 1 and the internal-evidence file share ONE definition + threshold. The gate orchestration (present, require confirmation, hard-stop) is SKILL.md prose that runs the script and ties in the step-5 recursion verdict.

**Tech Stack:** Python 3 (`/opt/homebrew/bin/python3`), `pytest`. No new deps. SKILL.md is the orchestration.

**Spec:** `docs/superpowers/specs/2026-06-15-scope-calculator-advisor-flow-design.md` §9 (anchor guard), §9.2 (rollup-dominance flag). Builds on `main` (Phases A+B merged at `034a0af`).

**Decision (locked):** gate strictness = **always checkpoint; HARD STOP when a recursion/dominance flag trips OR confidence is MEDIUM/LOW; HIGH-confidence + no flags = a quick one-line confirm.**

**Run all tests:** `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q` (currently 212 passing).

---

## File structure (Phase C)

```
skills/scope-calculator/
├── scripts/
│   ├── anchor_guard.py              [NEW]    dominant_host (moved here) + gate_report + CLI
│   └── build_internal_evidence.py   [MODIFY] import dominant_host/DOMINANCE_THRESHOLD from anchor_guard (drop local copy)
├── references/
│   └── site-census-methodology.md   [MODIFY] brief: the anchor gate / anchor_guard
└── SKILL.md                         [MODIFY] Stage-1 step 7 (anchor confirmation gate); script list; red-flag row
tests/
└── test_anchor_guard.py             [NEW]
```

**Sequencing:** Task 1 (the shared `anchor_guard.py` + move `dominant_host`) must land before Task 2 wires it into the flow.

---

## Task 1: `anchor_guard.py` — shared dominance signal + gate report

Move `dominant_host` + `DOMINANCE_THRESHOLD` out of `build_internal_evidence.py` into a new `anchor_guard.py` (single source of the threshold), add a `gate_report(data)` that combines dominance + confidence into a deterministic confirmation directive, and a CLI the Stage-1 flow runs. `build_internal_evidence.py` imports from `anchor_guard` so its existing behavior + tests are unchanged.

**Files:**
- Create: `skills/scope-calculator/scripts/anchor_guard.py`
- Modify: `skills/scope-calculator/scripts/build_internal_evidence.py`
- Test: `tests/test_anchor_guard.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_anchor_guard.py
import json, subprocess, sys, pathlib
import anchor_guard as ag

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "scope-calculator" / "scripts" / "anchor_guard.py"

def _data(per_domain, anchor, confidence="HIGH"):
    return {"rollup": {"spiral_adjusted_anchor": anchor, "confidence": confidence},
            "per_domain": per_domain}

DOMINANT = _data([{"hostname": "trap.com", "defensible_pages": 90_000},
                  {"hostname": "real.com", "defensible_pages": 5_000}], 95_000)      # trap = 94.7%
BALANCED = _data([{"hostname": "a.com", "defensible_pages": 35_000},
                  {"hostname": "b.com", "defensible_pages": 30_000},
                  {"hostname": "c.com", "defensible_pages": 30_000}], 95_000)        # max 36.8%


def test_dominant_host_flags_outsized_host():
    assert ag.dominant_host(DOMINANT)["hostname"] == "trap.com"

def test_dominant_host_none_when_balanced():
    assert ag.dominant_host(BALANCED) is None

def test_dominant_host_safe_on_empty_or_zero_anchor():
    assert ag.dominant_host(_data([], 95_000)) is None
    assert ag.dominant_host(_data([{"hostname": "x", "defensible_pages": 1}], 0)) is None

def test_gate_requires_confirmation_on_dominance():
    r = ag.gate_report(DOMINANT)
    assert r["requires_confirmation"] is True
    assert r["dominant"]["hostname"] == "trap.com" and r["dominant"]["pct"] == 94.7
    assert any("recursion trap" in reason for reason in r["reasons"])

def test_gate_requires_confirmation_on_medium_low_confidence():
    assert ag.gate_report(_data(BALANCED["per_domain"], 95_000, "MEDIUM"))["requires_confirmation"] is True
    assert ag.gate_report(_data(BALANCED["per_domain"], 95_000, "LOW"))["requires_confirmation"] is True

def test_gate_clean_on_high_confidence_no_dominance():
    r = ag.gate_report(BALANCED)   # HIGH + balanced
    assert r["requires_confirmation"] is False and r["dominant"] is None and r["reasons"] == []

def test_cli_prints_confirm_required(tmp_path):
    f = tmp_path / "rollup.json"; f.write_text(json.dumps(DOMINANT))
    res = subprocess.run([sys.executable, str(SCRIPT), str(f)], capture_output=True, text=True)
    assert res.returncode == 0
    assert "CONFIRM REQUIRED" in res.stdout and "trap.com" in res.stdout

def test_cli_prints_clean(tmp_path):
    f = tmp_path / "rollup.json"; f.write_text(json.dumps(BALANCED))
    res = subprocess.run([sys.executable, str(SCRIPT), str(f)], capture_output=True, text=True)
    assert res.returncode == 0 and "clean" in res.stdout.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_anchor_guard.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'anchor_guard'`.

- [ ] **Step 3: Write `anchor_guard.py`**

```python
"""Stage-1 anchor plausibility guard (deterministic, no network, no LLM math).

Before a derived page-count anchor propagates into pricing, the rep must confirm it. This module
provides the deterministic signals the Stage-1 confirmation gate uses:
  - the ROLLUP-DOMINANCE flag: one host an outsized share of the anchor (the Gallagher
    recursion-trap signal — stevenson-insurance.com was 93% of the total), and
  - a CONFIDENCE-aware confirmation directive.
The recursion/%22 verdict itself comes from check_artifacts.py (run on URL samples, Stage-1 step 5);
this module covers the rollup-level + confidence signals and is the single home of the threshold.

Input: the same {rollup, per_domain} object Stage 1 emits. rollup has spiral_adjusted_anchor +
confidence; per_domain has hostname + defensible_pages.
"""
import json
import sys

DOMINANCE_THRESHOLD = 0.40        # one host > this share of the anchor → confirm it's not a trap
_CONFIRM_CONFIDENCE = {"LOW", "MEDIUM"}   # confidence levels that force a hard-stop confirmation


def dominant_host(data):
    """The per-domain row whose defensible_pages exceed DOMINANCE_THRESHOLD of the anchor, else None."""
    pd = data.get("per_domain") or []
    if not pd:
        return None
    anchor = (data.get("rollup") or {}).get("spiral_adjusted_anchor") or 0
    if anchor <= 0:
        return None
    top = max(pd, key=lambda d: d["defensible_pages"])
    return top if top["defensible_pages"] / anchor > DOMINANCE_THRESHOLD else None


def gate_report(data):
    """Deterministic anchor-gate signals. Returns
    {anchor, confidence, dominant:{hostname,pct}|None, requires_confirmation:bool, reasons:[...]}.
    requires_confirmation is True when a dominant host trips OR confidence is LOW/MEDIUM — the cases
    the rep MUST acknowledge before pricing. (Recursion is handled in SKILL.md step 5; the gate ties
    that verdict in too.)"""
    rollup = data.get("rollup") or {}
    anchor = rollup.get("spiral_adjusted_anchor")
    confidence = str(rollup.get("confidence", "")).upper()
    dom = dominant_host(data)
    dom_pct = round(100.0 * dom["defensible_pages"] / anchor, 1) if dom else None
    reasons = []
    if dom:
        reasons.append(f"one host ({dom['hostname']}) is {dom_pct}% of the anchor — verify it is not "
                       f"a recursion trap (sample it via check_artifacts) before pricing")
    if confidence in _CONFIRM_CONFIDENCE:
        reasons.append(f"confidence is {confidence} — confirm the range before pricing")
    return {"anchor": anchor, "confidence": confidence,
            "dominant": {"hostname": dom["hostname"], "pct": dom_pct} if dom else None,
            "requires_confirmation": bool(reasons), "reasons": reasons}


def main(argv):
    raw = open(argv[1]).read() if len(argv) > 1 else sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f"scope-calculator: anchor-guard inputs are not valid JSON ({e}); "
                 f"see references/site-census-methodology.md")
    r = gate_report(data)
    anchor_s = f"{r['anchor']:,}" if isinstance(r["anchor"], (int, float)) else "—"
    print(f"ANCHOR GATE — anchor {anchor_s}, confidence {r['confidence'] or '—'}")
    if r["dominant"]:
        print(f"  ! dominant host: {r['dominant']['hostname']} = {r['dominant']['pct']}% of anchor")
    if r["requires_confirmation"]:
        print("  CONFIRM REQUIRED before pricing:")
        for reason in r["reasons"]:
            print(f"   - {reason}")
    else:
        print("  clean (HIGH confidence, no dominant host) — confirm the anchor to proceed.")


if __name__ == "__main__":
    main(sys.argv)
```

- [ ] **Step 4: Update `build_internal_evidence.py` to import from `anchor_guard`**

Remove the local `DOMINANCE_THRESHOLD` constant (line ~28) and the local `dominant_host` function (lines ~48-57). Add an import so both names are in the module namespace (existing tests reference `bie.dominant_host`):
```python
from anchor_guard import DOMINANCE_THRESHOLD, dominant_host  # noqa: F401  (re-exported; used by _derivation)
```
`_derivation` already calls `dominant_host(data)` — unchanged. Verify `tests/test_build_internal_evidence.py`'s dominance tests still pass (they call `bie.dominant_host`).

- [ ] **Step 5: Run to verify pass**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_anchor_guard.py tests/test_build_internal_evidence.py -q`
Expected: PASS (new anchor_guard tests + the unchanged internal-evidence tests, incl. its dominance cases via the import).

- [ ] **Step 6: Commit**

```bash
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" add observepoint-revenue/skills/scope-calculator/scripts/anchor_guard.py observepoint-revenue/skills/scope-calculator/scripts/build_internal_evidence.py observepoint-revenue/tests/test_anchor_guard.py
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" commit -m "feat(scope-calculator): anchor_guard.py — shared dominance signal + gate report"
```

---

## Task 2: Wire the anchor confirmation gate into SKILL.md

**Files:**
- Modify: `skills/scope-calculator/SKILL.md`
- Modify: `skills/scope-calculator/references/site-census-methodology.md`

This is prose/behavior — verified by the full suite staying green plus a subagent pressure test (controller-run).

- [ ] **Step 1: Add `anchor_guard.py` to the script list** (SKILL.md line ~10): append `anchor_guard.py` to the `Scripts:` inventory.

- [ ] **Step 2: Add Stage-1 step 7 — the anchor confirmation gate.** After step 6 ("Emit `{rollup, per_domain[]}`") in Stage 1, add:

```markdown
7. **Anchor confirmation gate — REQUIRED before Stage 2.** The derived anchor does NOT proceed to
   pricing until the rep confirms it. Run `python3 "$SCRIPTS/anchor_guard.py" <rollup_perdomain.json>`
   (the `{rollup, per_domain}` object from step 6) and present the rep with: the **anchor + range +
   confidence**, plus any flags — the step-5 recursion/artifact verdict AND the gate's
   **dominant-host** signal. Then:
   - **HARD STOP** if ANY of: the gate reports `requires_confirmation` (a dominant host > 40% of the
     anchor, OR confidence MEDIUM/LOW), OR step 5 found a recursion/`%22` host. The rep must
     explicitly acknowledge, and for a dominant/recursion host you MUST run the step-5
     `check_artifacts.py` sample on that host and EXCLUDE it if it's a trap, then re-derive — before
     pricing. Never price past a hard stop on the rep's silence.
   - **Quick confirm** if the gate is clean (HIGH confidence, no dominant host, step-5 clean): show
     the anchor and get a one-line "confirmed" before Stage 2.
   This gate is why a silent ~15× over-count (Gallagher) cannot reach a quote: the anchor is always
   seen and OK'd, and an outsized single host is always investigated. (Applies on the full-scope
   path; "known page count" entry skips Stage 1, so the rep-supplied number is the confirmation.)
```

- [ ] **Step 3: Add a Red-Flags row** (SKILL.md Red Flags table):

```markdown
| "The anchor looks fine — I'll go straight to pricing." | Run the **anchor gate** (`anchor_guard.py`) and get explicit rep confirmation first. An unconfirmed anchor is exactly how a silent ~15× over-count reaches the quote. Hard-stop on a dominant host (>40%), a recursion/`%22` host, or MEDIUM/LOW confidence. |
```

- [ ] **Step 4: Update `site-census-methodology.md`** — add a brief note (near the artifact-check / output-contract section) that after emitting `{rollup, per_domain}`, the Stage-1 flow runs `anchor_guard.py` for the confirmation gate (dominant-host + confidence signals), and that a dominant host must be sampled (check_artifacts) and excluded if it's a recursion trap before pricing.

- [ ] **Step 5: Run the FULL suite** — `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q`. Expected: green (these are doc edits; the count is whatever Task 1 left it at).

- [ ] **Step 6: Subagent pressure test (controller-run, not implementer):** give a fresh agent the reworked Stage 1 + a {rollup, per_domain} where one host is 93% of the anchor at MEDIUM confidence; verify it (a) runs/honors the anchor gate, (b) hard-stops and investigates the dominant host rather than proceeding to price, (c) does not price on silence. Record gaps as a red-flag refinement if found.

- [ ] **Step 7: Commit**

```bash
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" add observepoint-revenue/skills/scope-calculator/SKILL.md observepoint-revenue/skills/scope-calculator/references/site-census-methodology.md
git -C "/Users/jarrodwilbur/Documents/OP Revenue Plugin" commit -m "feat(scope-calculator): Stage-1 anchor confirmation gate (always confirm; hard-stop when flagged)"
```

---

## Self-review (against spec §9)

- **§9.1 wire the guard into Phase 1 + require rep confirmation** → Task 2 step 2 (Stage-1 step 7 gate; always confirm; hard-stop when flagged or MEDIUM/LOW). ✓
- **§9.2 rollup-dominance flag (max host / anchor > threshold)** → Task 1 (`dominant_host`/`gate_report`, now runnable at Stage 1, not just Stage 3). ✓
- **§9.3 recursion exclusion carried in the internal file / invariant preserved** → unchanged from Phase A (the internal file still records dominance via the shared `dominant_host`). ✓
- **Architecture principle (deterministic script, no LLM math)** → the dominance + confidence signal is computed in `anchor_guard.py`; SKILL.md only orchestrates. ✓
- **DRY** → `dominant_host` + threshold now defined once in `anchor_guard.py`, imported by `build_internal_evidence.py`. ✓

**Placeholder scan:** none — module, tests, and SKILL.md additions are complete.

**Type/reference consistency:** `dominant_host(data)`, `gate_report(data)` (returns `{anchor, confidence, dominant, requires_confirmation, reasons}`), `DOMINANCE_THRESHOLD`, and the `{rollup:{spiral_adjusted_anchor,confidence}, per_domain:[{hostname,defensible_pages}]}` input shape are consistent across `anchor_guard.py`, `build_internal_evidence.py`, the tests, and the SKILL.md gate. The 0.40 threshold matches Phase A's value (no behavior change for the internal file).

**Risk note:** moving `dominant_host` could break `test_build_internal_evidence.py` if it referenced a now-removed local symbol — the import re-exports both `dominant_host` and `DOMINANCE_THRESHOLD` into `bie`'s namespace so existing `bie.dominant_host` references resolve unchanged (Task 1 Step 4 + Step 5 verify this).
