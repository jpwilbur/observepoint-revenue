# find-accounts (Territory Discovery) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port NERD's Stage-0 Discovery as a `find-accounts` skill — find in-territory, ICP-fit,
*triggered* accounts not already in pipeline, ranked by the same trigger weights + recency decay
research-account uses.

**Architecture:** Claude judges (territory boundary, web sweep, trigger classification, evidence);
one deterministic script `rank_candidates.py` does the mechanics: validation (hard errors on unknown
trigger keys / missing sources), seen-log dedup + append, points × recency-decay ranking (parity
with `score_account.py`, constants read from research-account's `scoring-config.json` passed by
path), chat-ready stdout, and an optional `.xlsx` radar only on `--xlsx`. Chat-first deliverable.

**Tech Stack:** Python 3 stdlib (`argparse`, `json`, `math`, `datetime`); `openpyxl` imported
lazily only on the `--xlsx` path; pytest.

**Spec:** `docs/superpowers/specs/2026-06-09-find-accounts-design.md` — read it first.

---

## Critical environment notes (read before Task 0)

- Repo root: `/Users/jarrodwilbur/Documents/OP Revenue Plugin` (path has spaces — **quote it**).
  Plugin code lives under `observepoint-revenue/`. Branch: `feat/find-accounts` (already created).
- **Interpreter trap:** `/usr/bin/python3` is CLT 3.9 with no pytest. Always run tests with
  `/opt/homebrew/bin/python3 -m pytest` (3.14, pytest 9, openpyxl installed). Never pipe pytest
  through `| tail` inside `&&` chains (masks failures).
- Run pytest from `observepoint-revenue/` so `tests/conftest.py` is picked up.
- All test data is fictional ("Example Health System" etc.) — never commit real prospect data.

## File structure

| File | Responsibility |
|---|---|
| `observepoint-revenue/skills/find-accounts/scripts/rank_candidates.py` (create) | Validate, dedup vs seen-log, rank, print, optional xlsx. No LLM, no network. |
| `observepoint-revenue/skills/find-accounts/references/discovery-sources.md` (create) | Sweep playbook ported from NERD `prompts/discovery.md`. |
| `observepoint-revenue/skills/find-accounts/SKILL.md` (create) | Orchestration: territory profile → exclusions → sweep → script → summarize/offer export. |
| `observepoint-revenue/tests/test_rank_candidates.py` (create) | Offline tests incl. decay-parity vs score_account. |
| `observepoint-revenue/tests/conftest.py` (modify) | Add the new scripts dir to `sys.path`. |
| `observepoint-revenue/.claude-plugin/plugin.json` (modify) | v0.9.0 + description mentions find-accounts. |
| `docs/ROADMAP.md` (modify) | Move find-accounts to Recently shipped; fix stale v0.8.0/domains.txt header. |
| `observepoint-revenue/skills/owned-properties/scripts/build_inventory.py` (modify, hygiene) | Docstring still describes the dropped `domains.txt` 3-arg CLI. |

---

### Task 0: Scaffold + test path

**Files:**
- Create: `observepoint-revenue/skills/find-accounts/scripts/` and `references/` dirs
- Modify: `observepoint-revenue/tests/conftest.py`

- [ ] **Step 1: Add the scripts dir to conftest**

In `observepoint-revenue/tests/conftest.py`, add one line to the `for rel in (...)` tuple:

```python
    "skills/find-accounts/scripts",
```

(after the `"skills/owned-properties/scripts",` line).

- [ ] **Step 2: Create the skill directories with a placeholder-free keep**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin/observepoint-revenue"
mkdir -p skills/find-accounts/scripts skills/find-accounts/references
```

(Directories land in git with the files added in later tasks; nothing to commit for them yet.)

- [ ] **Step 3: Verify the suite still passes**

Run: `cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin/observepoint-revenue" && /opt/homebrew/bin/python3 -m pytest tests/ -q`
Expected: all existing tests pass (85 at last count), 0 failures.

- [ ] **Step 4: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin" && git add observepoint-revenue/tests/conftest.py && git commit -m "chore: find-accounts scaffold — test path for rank_candidates"
```

---

### Task 1: `rank_candidates.py` core — parse, decay parity, validation, ranking

**Files:**
- Create: `observepoint-revenue/skills/find-accounts/scripts/rank_candidates.py`
- Create: `observepoint-revenue/tests/test_rank_candidates.py`

- [ ] **Step 1: Write the failing tests**

Create `observepoint-revenue/tests/test_rank_candidates.py`:

```python
import json
import pathlib
import subprocess
import sys

import rank_candidates as rc
import score_account as sa

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "find-accounts" / "scripts" / "rank_candidates.py"
CONFIG_PATH = ROOT / "skills" / "research-account" / "references" / "scoring-config.json"
CONFIG = json.loads(CONFIG_PATH.read_text())

AS_OF = "2026-06-09"


def _data(candidates, date=AS_OF):
    return {"territory": {"region": "US West", "verticals": ["healthcare"]},
            "prepared_by": "Test", "date": date, "requested": 5, "candidates": candidates}


def _cand(name, key="pixelWiretapSuit", date="2026-06-01", url="https://example.org/x", **kw):
    c = {"name": name, "vertical": "healthcare", "reason": f"{name} reason",
         "triggerKey": key, "triggerDate": date, "sourceUrl": url}
    c.update(kw)
    return c


def test_recency_decay_parity_with_score_account():
    now_ms = sa._parse_ms(AS_OF)
    for d in ["2026-05-20", "2026-03-09", "2025-06-09", "2025-03-16", "2024-01-15",
              "2023-12-01", None, "2026", "2025-08"]:
        assert rc.recency_factor(d, CONFIG["recency"], now_ms) == \
            sa.recency_factor(d, CONFIG["recency"], now_ms), f"decay mismatch for {d!r}"


def test_round_half_up_matches_js_not_bankers():
    assert rc._round_half_up(2.5) == 3        # Python round(2.5) == 2 — we need JS Math.round
    assert rc._round_half_up(12.5) == 13
    assert rc._round_half_up(12.4) == 12


def test_half_up_rounding_applied_to_points():
    # enforcementAction = 25 pts; 2025-03-16 is exactly 450 days = 15.0 months before 2026-06-09
    # → factor 1 - (15-6)/18 = 0.5 → 12.5 → half-up 13 (banker's would give 12).
    ranked, dropped, new = rc.rank(_data([_cand("A", key="enforcementAction",
                                                date="2025-03-16")]), CONFIG)
    assert ranked[0]["effectivePoints"] == 13


def test_ranks_by_effective_points_decay_can_flip_order():
    # settlement 15 pts recent (→15) beats pixelWiretapSuit 30 pts from 2023 (>24mo → ×0.1 → 3).
    ranked, dropped, new = rc.rank(_data([
        _cand("OldSuit Co", key="pixelWiretapSuit", date="2023-01-01"),
        _cand("FreshSettle Co", key="settlement", date="2026-06-01"),
    ]), CONFIG)
    assert [e["name"] for e in ranked] == ["FreshSettle Co", "OldSuit Co"]
    assert ranked[0]["effectivePoints"] == 15 and ranked[1]["effectivePoints"] == 3


def test_tiebreak_newer_first_undated_last():
    # All pixelWiretapSuit (30): A 2026-06-01 (30), B 2026-05-01 (30); C 2025-05-09 is 13.2mo
    # → ×0.6 → 18, D undated → ×0.6 → 18. Expect A, B (newer dated first), then C before D.
    ranked, dropped, new = rc.rank(_data([
        _cand("D", date=None), _cand("C", date="2025-05-09"),
        _cand("B", date="2026-05-01"), _cand("A", date="2026-06-01"),
    ]), CONFIG)
    assert [e["name"] for e in ranked] == ["A", "B", "C", "D"]


def test_unknown_trigger_key_is_hard_error():
    import pytest
    with pytest.raises(ValueError, match="bipaOnly"):
        rc.rank(_data([_cand("X", key="bipaOnly")]), CONFIG)


def test_missing_source_url_is_hard_error():
    import pytest
    with pytest.raises(ValueError, match="sourceUrl"):
        rc.rank(_data([_cand("X", url="  ")]), CONFIG)


def test_trigger_label_attached_from_config():
    ranked, _, _ = rc.rank(_data([_cand("A")]), CONFIG)
    assert ranked[0]["triggerLabel"] == CONFIG["whyNow"]["pixelWiretapSuit"]["label"]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin/observepoint-revenue" && /opt/homebrew/bin/python3 -m pytest tests/test_rank_candidates.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'rank_candidates'`.

- [ ] **Step 3: Implement the core module**

Create `observepoint-revenue/skills/find-accounts/scripts/rank_candidates.py`:

```python
"""Rank territory-discovery candidates and maintain the seen-candidates log (deterministic).

The model FINDS and CLASSIFIES candidates (territory judgment, trigger classification, evidence);
this script does the mechanics: validation, seen-log dedup, ranking by trigger points x the SAME
recency decay research-account uses (scoring-config.json is passed in by path — single source of
truth, never copied), chat-ready stdout, and an optional .xlsx radar.

The decay math is reimplemented (not imported across skills) and pinned by a parity test against
score_account.recency_factor. `date` in the candidates JSON is the as_of clock (not the system
clock) so a given file always ranks the same.

CLI:  rank_candidates.py <candidates.json> <scoring-config.json>
                         [--seen <seen.json>] [--include-seen] [--xlsx <out.xlsx>]
"""
import argparse
import json
import math
import pathlib
import sys
from datetime import datetime, timezone

MONTH_MS = 30 * 86_400_000  # 30-day month (parity with score_account.py / NERD scoring.ts)


def _round_half_up(x):
    """Match JS Math.round (half rounds up), not Python's banker's rounding."""
    return int(math.floor(x + 0.5))


def _parse_ms(s):
    """Parse YYYY, YYYY-MM, YYYY-MM-DD, or full ISO to epoch ms (UTC). None if unparseable.
    Date-only formats anchored to UTC so recency is machine-independent (see score_account.py)."""
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            dt = datetime.strptime(s[:10] if fmt == "%Y-%m-%d" else s, fmt)
            return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


def recency_factor(date_str, recency, now_ms):
    """Full strength within fullStrengthMonths, linear decay to a 0.1 floor by zeroStrengthMonths.
    Undated/unparseable triggers get 0.6 (matched, but we can't time them)."""
    t = _parse_ms(date_str)
    if t is None:
        return 0.6
    months = (now_ms - t) / MONTH_MS
    if months <= recency["fullStrengthMonths"]:
        return 1.0
    if months >= recency["zeroStrengthMonths"]:
        return 0.1
    span = max(1, recency["zeroStrengthMonths"] - recency["fullStrengthMonths"])
    return max(0.1, 1 - (months - recency["fullStrengthMonths"]) / span)


def normalize_name(name):
    """'The Example Health-System, Inc.' == 'example health system inc' for dedup purposes."""
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def rank(data, config, seen=None, include_seen=False):
    """Validate + rank candidates. Returns (ranked, dropped_count, new_log_entries).

    Previously-seen names are dropped (or kept and annotated with firstSeen when include_seen);
    every NEW name yields a seen-log entry. Validation runs on every candidate, dropped or not.
    """
    why, recency = config["whyNow"], config["recency"]
    now_ms = _parse_ms(data.get("date"))
    if now_ms is None:
        raise ValueError("candidates JSON needs a 'date' (YYYY-MM-DD) to rank against")
    seen_by_name = {normalize_name(c.get("name")): c
                    for c in (seen or {}).get("candidates", [])}

    ranked, new_entries, dropped = [], [], 0
    for c in data.get("candidates", []) or []:
        key = c.get("triggerKey")
        if key not in why:
            raise ValueError(f"unknown triggerKey {key!r} for {c.get('name')!r} — "
                             "must be one of the scoring-config whyNow keys")
        if not (c.get("sourceUrl") or "").strip():
            raise ValueError(f"missing sourceUrl for {c.get('name')!r} — "
                             "every candidate needs a real source")
        prior = seen_by_name.get(normalize_name(c.get("name")))
        if prior and not include_seen:
            dropped += 1
            continue
        entry = dict(c)
        entry["triggerLabel"] = why[key]["label"]
        entry["effectivePoints"] = _round_half_up(
            why[key]["points"] * recency_factor(c.get("triggerDate"), recency, now_ms))
        if prior:
            entry["firstSeen"] = prior.get("firstSeen")
        else:
            new_entries.append({"name": c.get("name"), "firstSeen": data.get("date"),
                                "triggerKey": key, "sourceUrl": c.get("sourceUrl")})
        ranked.append(entry)
    # points desc, then newer trigger first; undated (None→0) lands last among point-ties.
    ranked.sort(key=lambda e: (-e["effectivePoints"], -(_parse_ms(e.get("triggerDate")) or 0)))
    return ranked, dropped, new_entries
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin/observepoint-revenue" && /opt/homebrew/bin/python3 -m pytest tests/test_rank_candidates.py -q`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin" && git add observepoint-revenue/skills/find-accounts/scripts/rank_candidates.py observepoint-revenue/tests/test_rank_candidates.py && git commit -m "feat: rank_candidates core — decay parity, validation, ranking (TDD)"
```

---

### Task 2: Seen-log — load, dedup, include-seen, append

**Files:**
- Modify: `observepoint-revenue/skills/find-accounts/scripts/rank_candidates.py` (add `load_seen`)
- Modify: `observepoint-revenue/tests/test_rank_candidates.py` (append tests)

- [ ] **Step 1: Write the failing tests** (append to `tests/test_rank_candidates.py`)

```python
SEEN = {"candidates": [{"name": "The Example Health-System, Inc.", "firstSeen": "2026-05-01",
                        "triggerKey": "pixelWiretapSuit", "sourceUrl": "https://example.org/old"}]}


def test_seen_dedup_normalized_name_match():
    ranked, dropped, new = rc.rank(_data([_cand("Example Health System Inc"),
                                          _cand("Brand New Co")]), CONFIG, seen=SEEN)
    assert [e["name"] for e in ranked] == ["Brand New Co"]
    assert dropped == 1
    assert [n["name"] for n in new] == ["Brand New Co"]   # only NEW names get log entries


def test_include_seen_keeps_and_annotates_without_relogging():
    ranked, dropped, new = rc.rank(_data([_cand("Example Health System Inc")]), CONFIG,
                                   seen=SEEN, include_seen=True)
    assert dropped == 0
    assert ranked[0]["firstSeen"] == "2026-05-01"
    assert new == []                                       # seen entry NOT re-appended


def test_new_entry_shape_uses_data_date():
    _, _, new = rc.rank(_data([_cand("Brand New Co")]), CONFIG, seen=SEEN)
    assert new == [{"name": "Brand New Co", "firstSeen": AS_OF,
                    "triggerKey": "pixelWiretapSuit", "sourceUrl": "https://example.org/x"}]


def test_load_seen_missing_and_corrupt_treated_empty(tmp_path):
    assert rc.load_seen(tmp_path / "nope.json") == {"candidates": []}
    bad = tmp_path / "bad.json"; bad.write_text("{not json")
    assert rc.load_seen(bad) == {"candidates": []}
    wrong = tmp_path / "wrong.json"; wrong.write_text(json.dumps({"candidates": "oops"}))
    assert rc.load_seen(wrong) == {"candidates": []}
    assert rc.load_seen(None) == {"candidates": []}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin/observepoint-revenue" && /opt/homebrew/bin/python3 -m pytest tests/test_rank_candidates.py -q`
Expected: `test_load_seen_missing_and_corrupt_treated_empty` FAILS (`AttributeError: load_seen`);
the other three PASS (Task 1's `rank` already handles `seen`). That's expected — `load_seen` is
the only missing piece.

- [ ] **Step 3: Implement `load_seen`** (add to `rank_candidates.py`, after `normalize_name`)

```python
def load_seen(path):
    """Read the seen-log; a missing, corrupt, or wrong-shaped file is just an empty log
    (it gets recreated on the next save). State must never block a discovery run."""
    if not path:
        return {"candidates": []}
    try:
        data = json.loads(pathlib.Path(path).read_text())
        if isinstance(data, dict) and isinstance(data.get("candidates"), list):
            return data
    except Exception:
        pass
    return {"candidates": []}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin/observepoint-revenue" && /opt/homebrew/bin/python3 -m pytest tests/test_rank_candidates.py -q`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin" && git add observepoint-revenue/skills/find-accounts/scripts/rank_candidates.py observepoint-revenue/tests/test_rank_candidates.py && git commit -m "feat: rank_candidates seen-log — normalized dedup, include-seen, resilient load (TDD)"
```

---

### Task 3: Chat output + CLI (`main`)

**Files:**
- Modify: `observepoint-revenue/skills/find-accounts/scripts/rank_candidates.py` (add `render_chat`, `main`)
- Modify: `observepoint-revenue/tests/test_rank_candidates.py` (append tests)

- [ ] **Step 1: Write the failing tests** (append to `tests/test_rank_candidates.py`)

```python
def _run_cli(tmp_path, data, *extra):
    f = tmp_path / "cands.json"; f.write_text(json.dumps(data))
    return subprocess.run([sys.executable, str(SCRIPT), str(f), str(CONFIG_PATH), *extra],
                          capture_output=True, text=True)


def test_cli_prints_ranked_order_and_sources(tmp_path):
    res = _run_cli(tmp_path, _data([_cand("Beta Co", key="settlement"),
                                    _cand("Alpha Co", key="pixelWiretapSuit")]))
    assert res.returncode == 0, res.stderr
    out = res.stdout
    assert out.index("1. Alpha Co") < out.index("2. Beta Co")   # 30 pts before 15 pts
    assert "https://example.org/x" in out
    assert CONFIG["whyNow"]["pixelWiretapSuit"]["label"] in out


def test_cli_seen_log_appends_and_excludes(tmp_path):
    seen = tmp_path / "seen.json"
    res1 = _run_cli(tmp_path, _data([_cand("Alpha Co")]), "--seen", str(seen))
    assert res1.returncode == 0, res1.stderr
    logged = json.loads(seen.read_text())["candidates"]
    assert [(c["name"], c["firstSeen"]) for c in logged] == [("Alpha Co", AS_OF)]
    # second run: Alpha excluded with a note; Beta appended.
    res2 = _run_cli(tmp_path, _data([_cand("Alpha Co"), _cand("Beta Co")]), "--seen", str(seen))
    assert "Beta Co" in res2.stdout and "1 previously-seen" in res2.stdout
    assert "1. Alpha Co" not in res2.stdout
    names = [c["name"] for c in json.loads(seen.read_text())["candidates"]]
    assert names == ["Alpha Co", "Beta Co"]


def test_cli_include_seen_shows_annotation(tmp_path):
    seen = tmp_path / "seen.json"
    _run_cli(tmp_path, _data([_cand("Alpha Co")]), "--seen", str(seen))
    res = _run_cli(tmp_path, _data([_cand("Alpha Co")]), "--seen", str(seen), "--include-seen")
    assert "Alpha Co" in res.stdout and f"[seen {AS_OF}]" in res.stdout


def test_cli_validation_error_exits_nonzero(tmp_path):
    res = _run_cli(tmp_path, _data([_cand("X", key="notAKey")]))
    assert res.returncode != 0
    assert "notAKey" in res.stderr


def test_cli_empty_candidates_is_valid(tmp_path):
    res = _run_cli(tmp_path, _data([]))
    assert res.returncode == 0, res.stderr
    assert "Ranked candidates (0)" in res.stdout


def test_cli_writes_no_files_without_xlsx_flag(tmp_path):
    _run_cli(tmp_path, _data([_cand("Alpha Co")]))
    assert list(tmp_path.glob("*.xlsx")) == [] and list(tmp_path.glob("*.txt")) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin/observepoint-revenue" && /opt/homebrew/bin/python3 -m pytest tests/test_rank_candidates.py -q`
Expected: most new CLI tests FAIL — the module has no `main()`/`__main__` block yet, so the
subprocess exits 0 with empty stdout (stdout assertions and the expects-nonzero test fail;
`test_cli_writes_no_files_without_xlsx_flag` may vacuously pass — that's fine).

- [ ] **Step 3: Implement `render_chat` + `main`** (add to `rank_candidates.py`, at the end)

```python
def render_chat(ranked, dropped):
    lines = [f"Ranked candidates ({len(ranked)}):"]
    for i, e in enumerate(ranked, 1):
        seen_note = f"  [seen {e['firstSeen']}]" if e.get("firstSeen") else ""
        lines.append(f"{i}. {e.get('name', '')} — {e['triggerLabel']} "
                     f"({e['effectivePoints']} pts, {e.get('triggerDate') or 'undated'})"
                     f"{seen_note}")
        lines.append(f"   {e.get('reason', '')}")
        lines.append(f"   {e.get('sourceUrl', '')}")
    if dropped:
        lines.append("")
        lines.append(f"Excluded {dropped} previously-seen candidate(s) — "
                     "rerun with --include-seen to show them.")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Rank discovery candidates; maintain the seen-candidates log.")
    ap.add_argument("candidates", help="candidates JSON assembled by the skill")
    ap.add_argument("config", help="path to research-account's scoring-config.json")
    ap.add_argument("--seen", help="seen-candidates log (created/extended as needed)")
    ap.add_argument("--include-seen", action="store_true",
                    help="keep previously-seen names in the output (refresh mode)")
    ap.add_argument("--xlsx", help="also write the discovery-radar workbook here")
    a = ap.parse_args(argv)

    data = json.loads(pathlib.Path(a.candidates).read_text())
    config = json.loads(pathlib.Path(a.config).read_text())
    seen = load_seen(a.seen)
    try:
        ranked, dropped, new_entries = rank(data, config, seen, a.include_seen)
    except ValueError as e:
        sys.exit(str(e))
    if a.seen and new_entries:
        p = pathlib.Path(a.seen)
        p.parent.mkdir(parents=True, exist_ok=True)
        seen["candidates"].extend(new_entries)
        p.write_text(json.dumps(seen, indent=2))
    if a.xlsx:
        out = pathlib.Path(a.xlsx)
        out.parent.mkdir(parents=True, exist_ok=True)
        build_radar(ranked).save(out)
        print(f"{out}\n")
    print(render_chat(ranked, dropped))


if __name__ == "__main__":
    main()
```

Note: `build_radar` does not exist until Task 4 — that's fine; it is only referenced on the
`--xlsx` path, which no Task-3 test exercises.

- [ ] **Step 4: Run to verify pass**

Run: `cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin/observepoint-revenue" && /opt/homebrew/bin/python3 -m pytest tests/test_rank_candidates.py -q`
Expected: 18 passed.

- [ ] **Step 5: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin" && git add observepoint-revenue/skills/find-accounts/scripts/rank_candidates.py observepoint-revenue/tests/test_rank_candidates.py && git commit -m "feat: rank_candidates CLI — chat output, seen-log persistence, hard-error exits (TDD)"
```

---

### Task 4: `--xlsx` discovery radar

**Files:**
- Modify: `observepoint-revenue/skills/find-accounts/scripts/rank_candidates.py` (add `build_radar`)
- Modify: `observepoint-revenue/tests/test_rank_candidates.py` (append tests)

- [ ] **Step 1: Write the failing tests** (append to `tests/test_rank_candidates.py`)

```python
def test_xlsx_radar_columns_hyperlink_fillable(tmp_path):
    from openpyxl import load_workbook
    out = tmp_path / "radar.xlsx"
    res = _run_cli(tmp_path, _data([_cand("Alpha Co")]), "--xlsx", str(out))
    assert res.returncode == 0, res.stderr
    assert out.exists() and str(out) in res.stdout
    wb = load_workbook(out)
    ws = wb["Discovery radar"]
    hdr = [c.value for c in ws[1]]
    assert hdr == ["Rank", "Company", "Vertical", "Trigger", "Trigger date", "Why now",
                   "Source", "Pursue?", "Notes"]
    assert ws.cell(row=2, column=1).value == 1
    assert ws.cell(row=2, column=2).value == "Alpha Co"
    src = ws.cell(row=2, column=7)
    assert src.hyperlink is not None and src.hyperlink.target == "https://example.org/x"
    assert ws.cell(row=2, column=8).value in (None, "")    # Pursue? fillable
    assert ws.cell(row=2, column=9).value in (None, "")    # Notes fillable


def test_xlsx_rows_follow_rank_order(tmp_path):
    from openpyxl import load_workbook
    out = tmp_path / "radar.xlsx"
    _run_cli(tmp_path, _data([_cand("Beta Co", key="settlement"),
                              _cand("Alpha Co", key="pixelWiretapSuit")]), "--xlsx", str(out))
    ws = load_workbook(out)["Discovery radar"]
    assert [(r[0], r[1]) for r in ws.iter_rows(min_row=2, values_only=True)] == \
        [(1, "Alpha Co"), (2, "Beta Co")]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin/observepoint-revenue" && /opt/homebrew/bin/python3 -m pytest tests/test_rank_candidates.py -q`
Expected: the 2 new tests FAIL (`NameError: build_radar` surfaces as nonzero returncode/stderr).

- [ ] **Step 3: Implement `build_radar`** (add to `rank_candidates.py`, before `render_chat`)

```python
RADAR_HEADERS = ["Rank", "Company", "Vertical", "Trigger", "Trigger date", "Why now",
                 "Source", "Pursue?", "Notes"]
RADAR_WIDTHS = {"Rank": 6, "Company": 30, "Vertical": 20, "Trigger": 36, "Trigger date": 12,
                "Why now": 60, "Source": 44, "Pursue?": 10, "Notes": 30}
DARK = "1E1E1E"


def build_radar(ranked):
    """One-sheet working list: ranked candidates + fillable Pursue?/Notes for the rep."""
    from openpyxl import Workbook  # lazy: the default chat-first path must not need openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    ws = wb.active
    ws.title = "Discovery radar"
    for i, h in enumerate(RADAR_HEADERS, 1):
        c = ws.cell(row=1, column=i, value=h)
        c.font = Font(bold=True, color="FFFFFF", size=11)
        c.fill = PatternFill("solid", fgColor=DARK)
        c.alignment = Alignment(horizontal="left", vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = RADAR_WIDTHS[h]
    for i, e in enumerate(ranked, 1):
        ws.append([i, e.get("name", ""), e.get("vertical", ""), e.get("triggerLabel", ""),
                   e.get("triggerDate", ""), e.get("reason", ""), e.get("sourceUrl", ""), "", ""])
        src = ws.cell(row=ws.max_row, column=7)
        src.hyperlink = e.get("sourceUrl", "")
        src.font = Font(color="0563C1", underline="single")  # explicit (avoid named-style dependency)
    return wb
```

- [ ] **Step 4: Run to verify pass**

Run: `cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin/observepoint-revenue" && /opt/homebrew/bin/python3 -m pytest tests/test_rank_candidates.py -q`
Expected: 20 passed.

- [ ] **Step 5: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin" && git add observepoint-revenue/skills/find-accounts/scripts/rank_candidates.py observepoint-revenue/tests/test_rank_candidates.py && git commit -m "feat: rank_candidates --xlsx discovery radar — ranked, hyperlinked, fillable (TDD)"
```

---

### Task 5: `references/discovery-sources.md`

**Files:**
- Create: `observepoint-revenue/skills/find-accounts/references/discovery-sources.md`

- [ ] **Step 1: Write the reference** (ported from NERD `control-plane/config/prompts/discovery.md`;
trigger taxonomy and verticals deferred to the shared scoring config rather than duplicated)

```markdown
# Discovery sweep — sources & rules

You are scouting NEW accounts for the rep's territory. You do not deep-research them here; you
surface qualified candidates that then go through research-account. Every judgment below is yours;
the script only ranks and de-duplicates what you give it.

## Territory is a hard boundary

Only surface companies inside the rep's stated territory (region and, if specified, verticals). A
great ICP fit outside the territory belongs to a different AE — leave it out. **When in doubt
whether a company is in-territory, leave it out.**

## What makes a strong candidate

ObservePoint's ideal customer is a large, regulated enterprise with a complex web presence and
active privacy/compliance pressure. The highest-signal candidates have a recent, specific trigger,
in roughly this order:

1. Named in a recent CIPA / state-wiretap class action, demand letter, or settlement (highest).
2. Recent FTC / HHS OCR / CPPA / state-AG privacy enforcement action or consent order.
3. A publicly reported privacy incident or client-side breach (Magecart, rogue tag).
4. New privacy/compliance leadership or a wave of privacy/analytics-governance hiring.

Tag each candidate with the single best `triggerKey` from
`../../research-account/references/scoring-config.json` (`whyNow` keys — the shared taxonomy; an
unknown key is a script error). Triggers need a genuine **web-tracking nexus** — no BIPA-only,
generic breach, antitrust, or product-safety stretches (same discipline as research-account).
Quick ICP sanity per candidate: enterprise scale, complex web estate, in a `targetVerticals`
vertical (same file).

## Sources to scan (public only)

- Litigation: ClassAction.org, Top Class Actions, Law360, Bloomberg Law, LawStreetMedia; the Duane
  Morris class-action review; DLA Piper / Davis Polk / Gibson Dunn / Baker McKenzie
  privacy-litigation reports; PACER coverage of CIPA (Cal. Penal Code 631), VPPA, state wiretap.
- Enforcement: FTC press releases, HHS OCR enforcement, CPPA actions, state-AG announcements.
- Incidents: breach/security press with a client-side or third-party-script angle.
- People signals: privacy/compliance leadership changes, privacy & analytics-governance job posts.

## Hard rules

- Aim for ~2x the requested count of raw leads, then keep only strong ones. **Never pad with weak
  fits** — fewer than requested, stated plainly, is the correct result when the territory is quiet.
- Every candidate needs a **real source URL** for its trigger. No fabricated companies, triggers,
  or sources. No companies already in the pipeline/exclusion set, and no obvious duplicates or
  subsidiaries of them.
- Candidate `reason` is one line: what happened, when, and why it makes them reachable now.
```

- [ ] **Step 2: Sanity-check the relative pointer**

Run: `ls "/Users/jarrodwilbur/Documents/OP Revenue Plugin/observepoint-revenue/skills/research-account/references/scoring-config.json"`
Expected: the file exists (the `../../research-account/...` pointer in the doc is for the reader;
the SKILL passes the absolute `${CLAUDE_PLUGIN_ROOT}` path to the script).

- [ ] **Step 3: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin" && git add observepoint-revenue/skills/find-accounts/references/discovery-sources.md && git commit -m "feat: find-accounts discovery-sources reference (ported from NERD discovery prompt)"
```

---

### Task 6: `SKILL.md` (writing-skills discipline)

**Files:**
- Create: `observepoint-revenue/skills/find-accounts/SKILL.md`

The implementer should invoke `superpowers:writing-skills` and follow its checklist; the content
below is the approved draft to validate against it (trigger-only description, imperative workflow,
red-flags table — consistent with the sibling skills).

- [ ] **Step 1: Write SKILL.md**

```markdown
---
name: find-accounts
description: Use when a revenue or sales rep wants NEW prospects surfaced for their territory — "find me accounts", "who should I be prospecting", "what's new in my territory", "discovery run", "find triggered accounts". Produces a ranked, sourced candidate list (chat-first, optional .xlsx radar) that feeds research-account. For researching a single named company use research-account; this finds the names in the first place.
---

# Find Accounts (Territory Discovery)

Proactively find in-territory, ICP-fit companies with a strong, current reason to be contacted —
not already in the rep's pipeline. Candidates feed research-account; this stage does NOT
deep-research them.

You judge (territory, triggers, evidence); `rank_candidates.py` does the mechanics (validation,
seen-log dedup, ranking with research-account's trigger weights + recency decay).

Set `SKILL=${CLAUDE_PLUGIN_ROOT}/skills/find-accounts` and
`SCORING=${CLAUDE_PLUGIN_ROOT}/skills/research-account/references/scoring-config.json`.
Read first: `$SKILL/references/discovery-sources.md` (sources, hard rules) and the `whyNow` keys +
`targetVerticals` in `$SCORING`.

## Inputs

- **Count** (default 5). **Territory override** (optional, this run only).
- **Pipeline list** (optional — pasted names or a file path; all excluded).
- **"Include previously seen" / "refresh"** (optional — re-show seen-log names).

## Workflow

1. **Territory.** Read `~/Documents/ObservePoint Revenue/territory.md`. If missing, ask the rep for
   region(s) + verticals (default verticals: the `targetVerticals` list in `$SCORING`) and write
   the file:

   ```markdown
   # Territory — <rep name>
   - **Region(s):** <e.g. US West>
   - **Verticals:** <comma-separated, or "all target verticals">
   - **Notes:** <segment limits, named exclusions, anything else>
   ```

   A per-run override ("just healthcare this time") adjusts THIS run only — never rewrite the file
   for an override. Territory is a hard boundary: when in doubt, leave the company out.

2. **Exclusions.** Union of: (a) subfolder names under
   `~/Documents/ObservePoint Revenue/Account Research/` (already researched — `ls` it),
   (b) any rep-supplied pipeline list, (c) the seen-log (the script enforces that one). Also skip
   obvious duplicates/subsidiaries of excluded names.

3. **Sweep** (`WebSearch`/`WebFetch`) per `$SKILL/references/discovery-sources.md`. Build each
   candidate: `name`, `domain` (when obvious), `vertical`, one-line `reason`, `triggerKey` (must be
   a `whyNow` key in `$SCORING`), `triggerDate` (YYYY-MM-DD if known), real `sourceUrl`. Fewer than
   requested is a valid result — say so; never pad.

4. **Assemble** `/tmp/discovery-candidates.json`: `territory{region,verticals,override}`,
   `prepared_by`, `date` (today), `requested`, `candidates[]`.

5. **Rank:**

   ```bash
   python3 "$SKILL/scripts/rank_candidates.py" /tmp/discovery-candidates.json "$SCORING" \
     --seen "$HOME/Documents/ObservePoint Revenue/Account Discovery/seen-candidates.json"
   ```

   Add `--include-seen` only when the rep asked to refresh/re-include. The script drops
   previously-seen names, appends new ones to the log, and prints the ranked list.

6. **Summarize in chat:** the ranked list (name, trigger, points, date, reason, source link), which
   territory/verticals were used, and how many were excluded as previously seen. Then **offer**:
   (a) the spreadsheet export, (b) a research-account run on the top pick.

7. **Only if the rep wants the export**, rerun step 5 with
   `--xlsx "$HOME/Documents/ObservePoint Revenue/Account Discovery/<YYYY-MM-DD> - discovery radar.xlsx"`
   AND `--include-seen` (step 5 already logged these names — without it the rerun would drop them
   all and write an empty radar). Rep folder override honored; `mkdir -p` first.

## Red flags — stop and fix

| Rationalization | Reality |
|---|---|
| "Great fit, just outside the territory." | Out of territory = out. It belongs to a different AE. When in doubt, leave it out. |
| "Only found 3 strong ones, I'll add 2 weaker." | Never pad. Fewer, stated plainly, is the honest result. |
| "I'm sure there's a lawsuit, I'll cite a likely URL." | Never fabricate a company, trigger, or source URL. Real sources only. |
| "Their subsidiary isn't technically in the pipeline." | Subsidiaries/duplicates of excluded accounts are excluded. |
| "This breach is close enough to web tracking." | Triggers need a web-tracking nexus (no BIPA-only, antitrust, product-safety stretches). |
| "I'll invent a trigger category for this." | `triggerKey` must exist in scoring-config; the script hard-errors otherwise. |

## What this skill does not do (v1)

Deep research (research-account), auto-running research on candidates, contact work, outreach copy,
Salesforce sync, scheduled sweeps, paid data sources.
```

- [ ] **Step 2: Validate frontmatter + structure against writing-skills**

Check: description is trigger-only (when to use, not how it works); name matches the folder; the
workflow is imperative; red-flags table present; no em-dash-free constraint needed (internal doc).

- [ ] **Step 3: Dry-run the step-5 command shape against the real script**

Run (from repo root, builds a tiny fixture inline):

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin/observepoint-revenue"
printf '{"territory":{"region":"US"},"date":"2026-06-09","requested":1,"candidates":[{"name":"Smoke Test Co","vertical":"healthcare","reason":"smoke","triggerKey":"settlement","triggerDate":"2026-06-01","sourceUrl":"https://example.org/s"}]}' > /tmp/fa-smoke.json
/opt/homebrew/bin/python3 skills/find-accounts/scripts/rank_candidates.py /tmp/fa-smoke.json skills/research-account/references/scoring-config.json --seen /tmp/fa-smoke-seen.json
rm -f /tmp/fa-smoke.json /tmp/fa-smoke-seen.json
```

Expected: exit 0; stdout shows `Ranked candidates (1):` with `1. Smoke Test Co` and the settlement
label at 15 pts.

- [ ] **Step 4: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin" && git add observepoint-revenue/skills/find-accounts/SKILL.md && git commit -m "feat: find-accounts SKILL.md — territory discovery orchestration"
```

---

### Task 7: Version bump, ROADMAP, hygiene, full suite

**Files:**
- Modify: `observepoint-revenue/.claude-plugin/plugin.json`
- Modify: `docs/ROADMAP.md`
- Modify: `observepoint-revenue/skills/owned-properties/scripts/build_inventory.py` (docstring only)

- [ ] **Step 1: plugin.json → 0.9.0 + description**

Set `"version": "0.9.0"` and replace the description with:

```
ObservePoint revenue-team tooling suite. Capabilities: find-accounts (surface in-territory, ICP-fit, triggered prospects ranked by why-now strength), owned-properties (discover all the web properties an org owns into a confirmable inventory + a domain list for scoping), scope-calculator (derive a defensible page count, size annual usage, price against ObservePoint's live pricing, and produce a customer proposal + evidence workbook), and research-account (research and qualify a named prospect into a scored, evidence-backed ICP dossier). More revenue tools to come.
```

- [ ] **Step 2: ROADMAP — ship it + fix the stale header**

In `docs/ROADMAP.md`:
1. Move the `find-accounts (Discovery)` bullet from "Top-of-funnel / discovery" (delete the now-empty
   section) into "✅ Recently shipped" as:

```markdown
- [x] **find-accounts (territory discovery)** **[deferred→shipped]** — NERD Stage-0 ported:
  in-territory, ICP-fit, *triggered* accounts not already in pipeline; ranked with the shared
  trigger weights + recency decay; seen-log so re-runs only surface new names; chat-first with an
  optional `.xlsx` discovery radar. Shipped in v0.9.0.
```

2. In the "**Shipped so far:**" header paragraph: add find-accounts, change "confirmable `.xlsx` +
   confirmed `domains.txt`" to "confirmable `.xlsx` + confirmed domains printed for scoping", and
   "Plugin at v0.8.0." → "Plugin at v0.9.0."

- [ ] **Step 3: build_inventory.py docstring hygiene** (stale since v0.8.1)

Replace the entire module docstring (it still describes the dropped `domains.txt` + 3-arg CLI) with:

```python
"""Render an owned-properties inventory workbook (.xlsx) + a confirmed-domains feed (deterministic).

Input: a candidates JSON (org + properties[] each with registrable/type/confidence/evidence/source/
host_count/sample_hosts/[all_hosts_file] + an excluded[] list). Output: an editable .xlsx with four
sheets (Confirmed Properties / For Review (unconfirmed) / All hostnames / Methodology & sources);
the CONFIRMED registrable domains are printed to stdout for scope-calculator (we do not scope on
guesses — and no separate domains.txt cluttering the deliverable folder).

CLI:  build_inventory.py <candidates.json> <out.xlsx>
"""
```

- [ ] **Step 4: Full suite**

Run: `cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin/observepoint-revenue" && /opt/homebrew/bin/python3 -m pytest tests/ -q`
Expected: 105 passed (85 existing + 20 new), 0 failures.

- [ ] **Step 5: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin" && git add observepoint-revenue/.claude-plugin/plugin.json docs/ROADMAP.md observepoint-revenue/skills/owned-properties/scripts/build_inventory.py && git commit -m "chore: v0.9.0 — find-accounts shipped; roadmap + stale build_inventory docstring"
```

---

### Task 8: Final review gate

- [ ] Run the full suite once more (same command as Task 7 Step 4) — green.
- [ ] Dispatch the final whole-branch code review (subagent-driven-development's closing review)
  over `git diff main...feat/find-accounts`.
- [ ] Address findings, then hand off to superpowers:finishing-a-development-branch.
