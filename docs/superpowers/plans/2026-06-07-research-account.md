# research-account Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `research-account` skill to the `observepoint-revenue` plugin that, given a named prospect, runs a light ObservePoint scan + public web research, scores the account deterministically, and renders a themed `.docx` dossier.

**Architecture:** Mirror `scope-calculator`'s three-part pattern — Claude (the SKILL body) gathers evidence and writes a classification JSON; `score_account.py` computes the score/qualify decision deterministically from ported NERD weights; `build_dossier.py` renders the themed `.docx`. The NERD prompts and `scoring.ts` math port over; the NERD Agent-SDK runtime is dropped (Claude's native web tools replace it).

**Tech Stack:** Python 3 (stdlib + `python-docx`), `pytest`. ObservePoint MCP `detect_cmp`; `WebSearch`/`WebFetch`. Brand theming mirrored from `build_proposal.py` (Montserrat / `#1E1E1E` / `#F2CD14`).

**Spec:** `docs/superpowers/specs/2026-06-07-research-account-design.md`

**NERD source (read-only reference):** `~/Documents/NERD/nerd`

---

## File Structure

```
observepoint-revenue/
  skills/research-account/
    SKILL.md                        # orchestration (Task 5)
    scripts/
      score_account.py              # deterministic scoring (Task 2)
      build_dossier.py              # themed .docx builder (Task 3)
    references/
      scoring-config.json           # ported NERD weights/gates/recency/lists (Task 1)
      trigger-and-fit.md            # ported NERD Stage-1 prompt (Task 4)
      research-and-contacts.md      # ported NERD Stage-2/3 prompt (Task 4)
      icp-and-tone.md               # condensed OP/buying-centers/tone reference (Task 4)
    assets/
      op-logo.png                   # copied from scope-calculator (Task 0)
  tests/
    conftest.py                     # MODIFY: add research-account/scripts to sys.path (Task 0)
    test_score_account.py           # (Task 2)
    test_build_dossier.py           # (Task 3)
  .claude-plugin/plugin.json        # MODIFY: 0.4.2 -> 0.5.0 (Task 6)
```

Each script is a pure function of its JSON input (no network, no LLM) and is independently testable.

---

## Task 0: Scaffold the skill and wire the test path

**Files:**
- Create dirs: `skills/research-account/{scripts,references,assets}`
- Copy: `skills/scope-calculator/assets/op-logo.png` → `skills/research-account/assets/op-logo.png`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Create the directory tree and copy the logo**

Run (from `observepoint-revenue/`):
```bash
mkdir -p skills/research-account/scripts skills/research-account/references skills/research-account/assets
cp skills/scope-calculator/assets/op-logo.png skills/research-account/assets/op-logo.png
ls skills/research-account/assets/op-logo.png
```
Expected: the path prints (file exists).

- [ ] **Step 2: Add the new scripts dir to the test sys.path**

In `tests/conftest.py`, the `for rel in (...)` tuple currently lists three script dirs. Add the new one. Replace:
```python
for rel in (
    "skills/size-and-price/scripts",
    "skills/derive-page-count/scripts",
    "skills/scope-calculator/scripts",
):
```
with:
```python
for rel in (
    "skills/size-and-price/scripts",
    "skills/derive-page-count/scripts",
    "skills/scope-calculator/scripts",
    "skills/research-account/scripts",
):
```

- [ ] **Step 3: Verify the existing suite still collects and passes**

Run (from `observepoint-revenue/`):
```bash
python -m pytest -q
```
Expected: all existing tests pass (no collection errors from the conftest edit).

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py skills/research-account/assets/op-logo.png
git commit -m "chore: scaffold research-account skill dir + test path + logo"
```

---

## Task 1: Port the scoring config

**Files:**
- Create: `skills/research-account/references/scoring-config.json`

This is a verbatim port of the `scoring` block from `~/Documents/NERD/nerd/control-plane/config/config.json` plus the `targetVerticals`, `personaPriorityTitles`, and `triggerSources` lists. It is the single source of truth for weights.

- [ ] **Step 1: Create `scoring-config.json` with this exact content**

```json
{
  "_note": "Ported from NERD control-plane/config/config.json. Single source of truth for ICP scoring. The model CLASSIFIES (which fit criteria are met, which triggers matched with dates); score_account.py computes the numbers. FIT is privacy-weighted; analytics-accuracy is intentionally lighter.",
  "fitGate": 55,
  "triggerOverride": 30,
  "recency": { "fullStrengthMonths": 6, "zeroStrengthMonths": 24 },
  "fit": {
    "privacyConsentSurface": { "label": "Privacy & consent surface (CMP deployed, consent-mode, GPC/opt-out duty)", "points": 25 },
    "regulatoryExposure": { "label": "Regulatory exposure (HIPAA / CCPA-CPRA + state / GDPR / FERPA / GLBA / COPPA)", "points": 20 },
    "tagPixelDensity": { "label": "Tag/pixel & MarTech density (GTM/Tealium/Adobe/Segment + heavy 3rd-party pixels)", "points": 20 },
    "webScale": { "label": "Web estate scale & complexity (many pages, multi-domain/brand, SPA, login-gated)", "points": 15 },
    "targetVertical": { "label": "In a target vertical", "points": 10 },
    "analyticsAccuracy": { "label": "Analytics-accuracy pressure (GA4 reliance, frequent releases/redesigns, data-quality owner)", "points": 10 }
  },
  "whyNow": {
    "pixelWiretapSuit": { "label": "Active pixel/wiretap suit (CIPA or state wiretap)", "points": 30 },
    "vppaSuit": { "label": "VPPA / video-tracking (Meta Pixel) suit", "points": 28 },
    "ocrHealthcare": { "label": "HHS OCR tracking-tech exposure (patient-portal pixels)", "points": 26 },
    "enforcementAction": { "label": "FTC / CPPA / state-AG action on tracking, consent, or data sharing", "points": 25 },
    "sessionReplaySuit": { "label": "Session-replay / chat-intercept suit", "points": 18 },
    "breachIncident": { "label": "Client-side / third-party-script compromise (Magecart, web-skimming, rogue tag)", "points": 16 },
    "settlement": { "label": "Privacy/tracking settlement finalized (24mo)", "points": 15 },
    "demandLetter": { "label": "Demand letter / pre-litigation notice", "points": 12 },
    "complianceDeadline": { "label": "Dated deadline exposure (TCF 2.3, Consent Mode v2, EU AI Act, EAA accessibility)", "points": 12 },
    "leadershipChange": { "label": "New CPO / GC / VP MarTech / VP Analytics (last 6 months)", "points": 10 },
    "governanceHiring": { "label": "Hiring privacy / analytics-governance roles", "points": 8 },
    "siteOrMerger": { "label": "Major site relaunch, M&A, or new tracking-heavy surface", "points": 8 }
  },
  "targetVerticals": [
    "healthcare", "financial services", "insurance", "pharma", "media & streaming",
    "retail & e-commerce", "higher education & government", "telecom", "travel & hospitality"
  ],
  "personaPriorityTitles": [
    "Chief Privacy Officer / VP Privacy",
    "VP Marketing Technology / Director MarTech",
    "VP Digital Analytics / Head of Analytics",
    "VP / Director Compliance or Legal (data-focused)",
    "Director Marketing Operations"
  ],
  "triggerSources": [
    "PACER docket search (CIPA, California Penal Code 631; VPPA 18 USC 2710; state wiretap acts)",
    "Law360, Bloomberg Law, LawStreetMedia litigation trackers",
    "ClassAction.org, Top Class Actions, Duane Morris class action review",
    "DLA Piper / Davis Polk / Gibson Dunn / Baker McKenzie privacy-litigation reports",
    "FTC, HHS OCR, CPPA, and state-AG enforcement actions and consent orders",
    "IAB TCF 2.3 deadline, Google Consent Mode v2, European Accessibility Act / EU AI Act timelines",
    "LinkedIn executive activity and job postings (privacy, MarTech, analytics governance)",
    "Earnings calls and SEC filings (litigation reserves, remediation, privacy risk)"
  ]
}
```

- [ ] **Step 2: Verify it is valid JSON and has the expected keys**

Run (from `observepoint-revenue/`):
```bash
python -c "import json,pathlib; d=json.loads(pathlib.Path('skills/research-account/references/scoring-config.json').read_text()); assert d['fitGate']==55 and len(d['fit'])==6 and len(d['whyNow'])==12; print('ok', len(d['fit']), len(d['whyNow']))"
```
Expected: `ok 6 12`

- [ ] **Step 3: Commit**

```bash
git add skills/research-account/references/scoring-config.json
git commit -m "feat: port NERD scoring config (weights/gates/recency/lists)"
```

---

## Task 2: `score_account.py` — deterministic scoring (TDD)

**Files:**
- Test: `tests/test_score_account.py`
- Create: `skills/research-account/scripts/score_account.py`

Port of `~/Documents/NERD/nerd/agents/src/scoring.ts` (`computeFit` + `recencyFactor`). The model classifies; this computes. `now` is passed explicitly (not `Date.now()`) so scoring is reproducible.

- [ ] **Step 1: Write the failing test**

Create `tests/test_score_account.py`:
```python
import json
import pathlib
import subprocess
import sys

import score_account as sa

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "research-account" / "scripts" / "score_account.py"
AS_OF = "2026-06-07"

# Acme Health classification, seeded from NERD agents/src/fixtures.ts (submit_fit).
ACME = {
    "account": "Acme Health",
    "date": AS_OF,
    "fit": [
        {"key": "privacyConsentSurface", "met": True, "evidence": "OneTrust CMP deployed."},
        {"key": "regulatoryExposure", "met": True, "evidence": "HIPAA + CCPA."},
        {"key": "tagPixelDensity", "met": True, "evidence": "GTM + Meta Pixel + 6 partners."},
        {"key": "webScale", "met": True, "evidence": "Thousands of pages, two domains."},
        {"key": "targetVertical", "met": True, "evidence": "Healthcare."},
        {"key": "analyticsAccuracy", "met": False},
    ],
    "triggers": [
        {"description": "CIPA class action re: tracking pixels.", "date": "2026-01-16",
         "sourceUrl": "https://example.com/cipa", "category": "litigation", "scoreKey": "pixelWiretapSuit"},
        {"description": "Hiring a Privacy Compliance PM.", "date": "2026-04",
         "sourceUrl": "https://example.com/job", "category": "hiring", "scoreKey": "governanceHiring"},
    ],
    "rationale": "Strong privacy fit with active CIPA exposure.",
}


def test_fit_score_sums_met_criteria_capped_at_100():
    s = sa.score(ACME, AS_OF)["score"]
    # 25+20+20+15+10 = 90 (analyticsAccuracy not met)
    assert s["fitScore"] == 90


def test_whynow_score_uses_recent_full_strength():
    s = sa.score(ACME, AS_OF)["score"]
    # both triggers < 6 months old -> full strength: 30 + 8
    assert s["whyNowScore"] == 38
    assert s["finalScore"] == 128


def test_qualified_by_fit_gate():
    s = sa.score(ACME, AS_OF)["score"]
    assert s["qualified"] is True
    assert s["lowFitHighTrigger"] is False


def test_trigger_override_qualifies_low_fit_account():
    low = {
        "account": "Thin Co", "date": AS_OF,
        "fit": [{"key": "targetVertical", "met": True}],   # 10 pts, below the 55 gate
        "triggers": [{"description": "CIPA suit", "date": "2026-05-01",
                      "sourceUrl": "https://x", "category": "litigation", "scoreKey": "pixelWiretapSuit"}],
        "rationale": "Low fit, hot trigger.",
    }
    s = sa.score(low, AS_OF)["score"]
    assert s["fitScore"] == 10
    assert s["whyNowScore"] == 30
    assert s["qualified"] is True
    assert s["lowFitHighTrigger"] is True


def test_recency_decay_old_trigger_hits_floor():
    old = {
        "account": "Old News", "date": AS_OF,
        "fit": [], "rationale": "",
        "triggers": [{"description": "ancient settlement", "date": "2020-01-01",
                      "sourceUrl": "https://x", "category": "litigation", "scoreKey": "settlement"}],
    }
    s = sa.score(old, AS_OF)["score"]
    # settlement base 15, >24mo old -> factor 0.1 -> round(1.5) = 2
    assert s["whyNowScore"] == 2


def test_undated_trigger_gets_partial_credit():
    und = {
        "account": "No Date", "date": AS_OF, "fit": [], "rationale": "",
        "triggers": [{"description": "demand letter", "sourceUrl": "https://x",
                      "category": "litigation", "scoreKey": "demandLetter"}],
    }
    s = sa.score(und, AS_OF)["score"]
    # demandLetter base 12, undated factor 0.6 -> round(7.2) = 7
    assert s["whyNowScore"] == 7


def test_unknown_scorekey_is_skipped_but_trigger_preserved():
    bad = {
        "account": "Mystery", "date": AS_OF, "fit": [], "rationale": "",
        "triggers": [{"description": "weird event", "date": AS_OF,
                      "sourceUrl": "https://x", "category": "other", "scoreKey": "bogusKey"}],
    }
    out = sa.score(bad, AS_OF)
    assert out["score"]["whyNowScore"] == 0
    assert out["score"]["whyNowBreakdown"] == []        # unscored -> not in breakdown
    assert out["triggers"][0]["scoreKey"] == "bogusKey"  # raw trigger preserved for the docx


def test_cli_writes_scored_json(tmp_path):
    f = tmp_path / "c.json"; f.write_text(json.dumps(ACME))
    out = tmp_path / "scored.json"
    res = subprocess.run([sys.executable, str(SCRIPT), str(f), str(out), AS_OF],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == str(out)
    data = json.loads(out.read_text())
    assert data["score"]["finalScore"] == 128
```

- [ ] **Step 2: Run the test to verify it fails**

Run (from `observepoint-revenue/`):
```bash
python -m pytest tests/test_score_account.py -q
```
Expected: FAIL / collection error — `ModuleNotFoundError: No module named 'score_account'`.

- [ ] **Step 3: Write the implementation**

Create `skills/research-account/scripts/score_account.py`:
```python
"""Deterministic ICP scoring for research-account.

The model CLASSIFIES (which fit criteria are met, which trigger events apply, with dates); this
computes the numbers from scoring-config.json. Keeping the math here (not in the model) makes scores
reproducible and tuning a config edit. Ported from NERD agents/src/scoring.ts.

`now` is passed explicitly (not the system clock) so a given classification always scores the same.

CLI:  score_account.py <classification.json> <out.json> [as_of=YYYY-MM-DD]
      as_of defaults to the classification's "date" field. Prints the output path.
"""
import json
import math
import pathlib
import sys
from datetime import datetime, timezone

CONFIG = pathlib.Path(__file__).resolve().parent.parent / "references" / "scoring-config.json"
MONTH_MS = 30 * 86_400_000


def load_config(path=None):
    return json.loads(pathlib.Path(path or CONFIG).read_text())


def _round_half_up(x):
    """Match JS Math.round (half rounds up), not Python's banker's rounding."""
    return int(math.floor(x + 0.5))


def _parse_ms(s):
    """Parse YYYY, YYYY-MM, YYYY-MM-DD, or full ISO to epoch ms (UTC). None if unparseable."""
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


def compute_fit(config, classification, now_ms):
    classified_fit = classification.get("fit", []) or []
    fit_breakdown = []
    for key, deff in config["fit"].items():
        m = next((f for f in classified_fit if f.get("key") == key), None)
        met = bool(m and m.get("met"))
        fit_breakdown.append({"key": key, "label": deff["label"],
                              "points": deff["points"] if met else 0,
                              "met": met, "evidence": (m or {}).get("evidence")})
    fit_score = min(100, sum(x["points"] for x in fit_breakdown))

    why_breakdown = []
    for t in classification.get("triggers", []) or []:
        sk = t.get("scoreKey")
        deff = config["whyNow"].get(sk) if sk else None
        if not deff:
            continue  # unscored trigger: stays in the raw list, no points
        pts = _round_half_up(deff["points"] * recency_factor(t.get("date"), config["recency"], now_ms))
        why_breakdown.append({"key": sk, "label": deff["label"], "basePoints": deff["points"],
                              "points": pts, "description": t.get("description"),
                              "date": t.get("date"), "sourceUrl": t.get("sourceUrl")})
    why_score = sum(x["points"] for x in why_breakdown)

    by_fit = fit_score >= config["fitGate"]
    by_trigger = why_score >= config["triggerOverride"]
    qualified = by_fit or by_trigger
    return {
        "fitScore": fit_score, "whyNowScore": why_score, "finalScore": fit_score + why_score,
        "qualified": qualified, "lowFitHighTrigger": qualified and not by_fit and by_trigger,
        "fitBreakdown": fit_breakdown, "whyNowBreakdown": why_breakdown,
    }


def score(classification, as_of=None, config=None):
    cfg = config or load_config()
    as_of = as_of or classification.get("date")
    now_ms = _parse_ms(as_of)
    if now_ms is None:
        raise ValueError("score() needs an as_of date (arg or classification['date']) in YYYY-MM-DD")
    out = dict(classification)
    out["score"] = compute_fit(cfg, classification, now_ms)
    out["scoredAsOf"] = as_of
    return out


def main(argv):
    if len(argv) < 3:
        sys.exit("usage: score_account.py <classification.json> <out.json> [as_of=YYYY-MM-DD]")
    data = json.loads(pathlib.Path(argv[1]).read_text())
    as_of = argv[3] if len(argv) > 3 else data.get("date")
    out = score(data, as_of)
    pathlib.Path(argv[2]).write_text(json.dumps(out, indent=2))
    print(argv[2])


if __name__ == "__main__":
    main(sys.argv)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run (from `observepoint-revenue/`):
```bash
python -m pytest tests/test_score_account.py -q
```
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add tests/test_score_account.py skills/research-account/scripts/score_account.py
git commit -m "feat: score_account.py deterministic ICP scoring (port of NERD scoring.ts)"
```

---

## Task 3: `build_dossier.py` — themed `.docx` (TDD)

**Files:**
- Test: `tests/test_build_dossier.py`
- Create: `skills/research-account/scripts/build_dossier.py`

Renders a `scored.json` (the §4 object + `score` block) to a themed dossier. Theming primitives are mirrored from `build_proposal.py` (smallest blast radius — no refactor of existing scripts).

- [ ] **Step 1: Write the failing test**

Create `tests/test_build_dossier.py`:
```python
import json
import pathlib
import subprocess
import sys

from docx import Document

import build_dossier as bd
import score_account as sa

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "research-account" / "scripts" / "build_dossier.py"
AS_OF = "2026-06-07"

CLASSIFICATION = {
    "account": "Acme Health", "domain": "acmehealth.com", "prepared_by": "Jarrod Wilbur", "date": AS_OF,
    "scan": {"cmp": "OneTrust", "cmp_supported": True, "cmp_confirmed": True,
             "tags": ["Google Tag Manager", "GA4", "Meta Pixel"],
             "tag_method": "homepage script-signature scan (WebFetch)", "site_census": None,
             "method": "observepoint detect_cmp + static tag scan"},
    "fit": [
        {"key": "privacyConsentSurface", "met": True, "evidence": "OneTrust CMP (confirmed via ObservePoint scan)."},
        {"key": "regulatoryExposure", "met": True, "evidence": "HIPAA + CCPA."},
        {"key": "tagPixelDensity", "met": True, "evidence": "GTM + Meta Pixel observed."},
        {"key": "webScale", "met": True, "evidence": "Thousands of pages."},
        {"key": "targetVertical", "met": True, "evidence": "Healthcare."},
        {"key": "analyticsAccuracy", "met": False},
    ],
    "triggers": [
        {"description": "CIPA class action re: tracking pixels.", "date": "2026-01-16",
         "sourceUrl": "https://example.com/cipa", "category": "litigation", "scoreKey": "pixelWiretapSuit"},
    ],
    "rationale": "Strong privacy fit with active CIPA exposure.",
    "research": {
        "companyOverview": "Acme Health is a large consumer healthcare web property.",
        "keyTriggers": ["Active CIPA class action."],
        "painHypotheses": ["Needs dated per-page evidence of what fires and the consent state."],
        "competitorIntel": "Likely OneTrust CMP; no incumbent pixel-audit vendor.",
        "techStackNotes": "GTM tag orchestration; multiple ad/analytics partners.",
        "bestOpeningAngle": "Offer a free scan tear sheet of what fires vs captured consent.",
        "researchSources": ["https://example.com/leadership", "https://example.com/news"],
    },
    "contacts": [
        {"name": "Dana Rivera", "title": "Senior Director, Privacy Counsel",
         "linkedin": "https://www.linkedin.com/in/example-dana", "sourceVerified": True,
         "sourceUrl": "https://www.linkedin.com/in/example-dana",
         "personalizationHook": "Posted about expanding the privacy team.",
         "toneGuidance": "Privacy-counsel voice.", "avoid": "Do not lead with their lawsuit."},
        {"name": "Sam Okonkwo", "title": "VP, Compliance",
         "linkedin": None, "sourceVerified": False, "sourceUrl": "",
         "personalizationHook": "Built the internal audit program.",
         "toneGuidance": "Operator voice.", "avoid": "Avoid legal-threat framing."},
    ],
}

SCORED = sa.score(CLASSIFICATION, AS_OF)


def _text(doc):
    parts = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                parts.append(c.text)
    return "\n".join(parts)


def test_header_and_verdict():
    t = _text(bd.build_dossier(SCORED))
    assert "Acme Health" in t
    assert "Account Research Dossier" in t
    assert "QUALIFIED" in t
    assert "120" in t            # final score (fit 90 + why-now 30; this fixture has ONE trigger)
    assert "90" in t and "30" in t  # fit + why-now


def test_why_now_and_fit_sections():
    t = _text(bd.build_dossier(SCORED))
    assert "Why now" in t
    assert "CIPA class action" in t
    assert "https://example.com/cipa" in t
    assert "Privacy & consent surface" in t        # a fit-criterion label
    assert "confirmed via ObservePoint scan" in t  # measured evidence folded in


def test_overview_and_internal_strategy_label():
    t = _text(bd.build_dossier(SCORED))
    assert "consumer healthcare web property" in t
    assert "tear sheet" in t                       # best opening angle text
    assert "Internal strategy" in t                # the strategy-vs-copy label
    assert "Meta Pixel" in t                       # measured tag inventory surfaced


def test_contacts_table_and_held_back_gate():
    t = _text(bd.build_dossier(SCORED))
    assert "Dana Rivera" in t and "Sam Okonkwo" in t
    assert "held back" in t.lower()                # Sam is unverified -> flagged, not hidden


def test_cli_writes_docx(tmp_path):
    f = tmp_path / "scored.json"; f.write_text(json.dumps(SCORED))
    out = tmp_path / "dossier.docx"
    res = subprocess.run([sys.executable, str(SCRIPT), str(f), str(out)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == str(out)
    assert "Acme Health" in _text(Document(out))
```

- [ ] **Step 2: Run the test to verify it fails**

Run (from `observepoint-revenue/`):
```bash
python -m pytest tests/test_build_dossier.py -q
```
Expected: FAIL / collection error — `ModuleNotFoundError: No module named 'build_dossier'`.

- [ ] **Step 3: Write the implementation**

Create `skills/research-account/scripts/build_dossier.py`:
```python
"""ObservePoint-themed account research dossier (.docx) for research-account.

Input: a scored.json object (the classification object + a `score` block from score_account.py).
This is an INTERNAL AE artifact. The "best opening angle" is labeled internal strategy (the sharp
legal framing belongs to the AE's strategy, never to prospect-facing copy — that is the future
sequence-contacts skill's job, under the tone governor).

Theming mirrors ObservePoint's brand (Montserrat / #1E1E1E / #F2CD14), matching build_proposal.py.

CLI:  build_dossier.py <scored.json> <out.docx>   (prints the output path)
"""
import json
import pathlib
import sys

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

FONT = "Montserrat"
DARK = RGBColor(0x1E, 0x1E, 0x1E)
GRAY = RGBColor(0x5C, 0x5C, 0x5C)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
RED = RGBColor(0xF3, 0x41, 0x46)
GREEN = RGBColor(0x1F, 0x9D, 0x55)
DARK_HEX, YELLOW_HEX, LIGHT_HEX = "1E1E1E", "F2CD14", "F2F2F2"
LOGO = pathlib.Path(__file__).resolve().parent.parent / "assets" / "op-logo.png"


# ---------- theming helpers (mirrored from build_proposal.py) ----------
def _run(p, text, *, bold=False, size=10.5, color=DARK):
    r = p.add_run(text)
    r.font.name, r.font.bold, r.font.size, r.font.color.rgb = FONT, bold, Pt(size), color
    return r


def _shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def _yellow_bar(doc):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", "18"), ("w:space", "1"), ("w:color", YELLOW_HEX)):
        bottom.set(qn(k), v)
    pbdr.append(bottom)
    p._p.get_or_add_pPr().append(pbdr)
    return p


def _heading(doc, text, *, color=DARK, size=13):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    _run(p, text, bold=True, size=size, color=color)
    _yellow_bar(doc)


def _para(doc, text, *, size=10.5, color=DARK, bold=False):
    p = doc.add_paragraph()
    _run(p, text, size=size, color=color, bold=bold)
    return p


def _table(doc, headers, rows):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.LEFT
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        _shade(c, DARK_HEX)
        _run(c.paragraphs[0], h, bold=True, size=9, color=WHITE)
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for i, val in enumerate(row):
            if ri % 2 == 1:
                _shade(cells[i], LIGHT_HEX)
            _run(cells[i].paragraphs[0], str(val), size=9)
    return t


def _highlight(doc, text, fill=YELLOW_HEX, color=DARK):
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = t.rows[0].cells[0]
    _shade(c, fill)
    p = c.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p, text, bold=True, size=15, color=color)
    return t


def _set_base_style(doc):
    st = doc.styles["Normal"]
    st.font.name, st.font.size, st.font.color.rgb = FONT, Pt(10.5), DARK


def _bullets(doc, items):
    for it in items or []:
        p = doc.add_paragraph(style="List Bullet")
        _run(p, str(it), size=10)


# ---------- builder ----------
def build_dossier(data):
    score = data.get("score", {})
    research = data.get("research", {})
    scan = data.get("scan", {})

    doc = Document()
    _set_base_style(doc)

    # Header
    if LOGO.exists():
        try:
            doc.add_picture(str(LOGO), width=Inches(2.0))
        except Exception:
            pass
    _run(doc.add_paragraph(), f"Account Research Dossier — {data.get('account', '')}", bold=True, size=20)
    _yellow_bar(doc)
    sub = [b for b in (data.get("date"),
                       ("Prepared by " + data["prepared_by"]) if data.get("prepared_by") else None,
                       data.get("domain")) if b]
    if sub:
        _run(doc.add_paragraph(), "  ·  ".join(sub), size=9, color=GRAY)

    # Verdict band
    qualified = score.get("qualified")
    verdict = (f"{'QUALIFIED' if qualified else 'NOT QUALIFIED'}   ·   "
               f"Score {score.get('finalScore', 0)}  "
               f"(fit {score.get('fitScore', 0)} + why-now {score.get('whyNowScore', 0)})")
    _highlight(doc, verdict, fill=(YELLOW_HEX if qualified else "F2F2F2"))
    if score.get("lowFitHighTrigger"):
        _para(doc, "Qualified on the why-now trigger override despite sub-gate fit — a timing play.",
              size=9, color=RED)
    if data.get("rationale"):
        _para(doc, data["rationale"], size=10, color=GRAY)

    # Why now (all triggers; points from the scored breakdown, 0 if unscored)
    _heading(doc, "Why now")
    pts_by_desc = {b.get("description"): b.get("points") for b in score.get("whyNowBreakdown", [])}
    trigs = sorted(data.get("triggers", []) or [],
                   key=lambda t: pts_by_desc.get(t.get("description"), 0), reverse=True)
    if trigs:
        _table(doc, ["Trigger", "Date", "Category", "Source", "Points"],
               [[t.get("description", ""), t.get("date", "—"), t.get("category", ""),
                 t.get("sourceUrl", ""), pts_by_desc.get(t.get("description"), 0)] for t in trigs])
    else:
        _para(doc, "No acute web-tracking trigger event found. A strong fit with no trigger is a "
                   "valid, honest result.", size=10, color=GRAY)

    # ICP fit
    _heading(doc, "ICP fit")
    _table(doc, ["Criterion", "Met?", "Points", "Evidence"],
           [[b["label"], "Yes" if b["met"] else "No", b["points"], b.get("evidence") or "—"]
            for b in score.get("fitBreakdown", [])])

    # Account overview
    _heading(doc, "Account overview")
    if research.get("companyOverview"):
        _para(doc, research["companyOverview"])
    if research.get("painHypotheses"):
        _para(doc, "Why ObservePoint matters here:", bold=True, size=10)
        _bullets(doc, research["painHypotheses"])
    if research.get("competitorIntel"):
        _para(doc, "Competitor intel: " + research["competitorIntel"], size=10)
    # Tech stack + the measured scan inventory
    tech = research.get("techStackNotes", "")
    tags = ", ".join(scan.get("tags") or [])
    cmp_line = scan.get("cmp")
    measured = []
    if cmp_line:
        measured.append(f"CMP: {cmp_line}" + (" (ObservePoint-supported)" if scan.get("cmp_supported") else ""))
    if tags:
        measured.append(f"Tags/pixels: {tags}")
    if scan.get("site_census"):
        measured.append(f"Site Census page count: {scan['site_census']}")
    line = "Tech stack: " + tech
    if measured:
        line += "  |  Measured on-site: " + "; ".join(measured) + "."
    _para(doc, line, size=10)

    # Best opening angle (internal strategy)
    _heading(doc, "Best opening angle")
    _para(doc, "Internal strategy — not prospect-facing copy.", bold=True, size=9, color=RED)
    _para(doc, research.get("bestOpeningAngle", ""))

    # Contacts
    _heading(doc, "Contacts")
    rows = []
    held = 0
    for c in data.get("contacts", []) or []:
        verified = bool(c.get("sourceVerified")) and bool(c.get("sourceUrl"))
        flag = "Yes" if verified else "⚠ held back — verify before outreach"
        if not verified:
            held += 1
        rows.append([c.get("name", ""), c.get("title", ""), c.get("linkedin") or "—",
                     flag, c.get("personalizationHook", ""), c.get("avoid", "")])
    if rows:
        _table(doc, ["Name", "Title", "LinkedIn", "Verified?", "Hook", "Avoid"], rows)
    if held:
        _para(doc, f"{held} contact(s) held back: missing source verification. Confirm the person and "
                   f"current title before any outreach (no fabricated or unverified contacts ship).",
              size=9, color=RED)

    # Sources & method
    _heading(doc, "Sources & method")
    _bullets(doc, research.get("researchSources", []))
    _para(doc, "Method: public web research + an ObservePoint CMP/tag scan of the live site. "
               "The score is computed deterministically from ObservePoint's ICP weights "
               "(reproducible; not a model guess).", size=9, color=GRAY)

    return doc


def main(argv):
    if len(argv) < 3:
        sys.exit("usage: build_dossier.py <scored.json> <out.docx>")
    data = json.loads(pathlib.Path(argv[1]).read_text())
    build_dossier(data).save(argv[2])
    print(argv[2])


if __name__ == "__main__":
    main(sys.argv)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run (from `observepoint-revenue/`):
```bash
python -m pytest tests/test_build_dossier.py -q
```
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add tests/test_build_dossier.py skills/research-account/scripts/build_dossier.py
git commit -m "feat: build_dossier.py themed account-research .docx"
```

---

## Task 4: Port the research prompts into reference files

**Files:**
- Create: `skills/research-account/references/trigger-and-fit.md`
- Create: `skills/research-account/references/research-and-contacts.md`
- Create: `skills/research-account/references/icp-and-tone.md`

The first two are near-verbatim ports of the NERD prompts; the third is a short condensed reference.

- [ ] **Step 1: Copy the two NERD prompts**

Run (from `observepoint-revenue/`):
```bash
cp ~/Documents/NERD/nerd/control-plane/config/prompts/trigger-and-fit.md skills/research-account/references/trigger-and-fit.md
cp ~/Documents/NERD/nerd/control-plane/config/prompts/research.md skills/research-account/references/research-and-contacts.md
```

- [ ] **Step 2: Add a skill-context note to the top of `trigger-and-fit.md`**

Insert immediately after the first line (`# Stage 1 — Trigger & Fit`) a blank line then this block:
```markdown
> **Skill context:** You are running inside the `research-account` Claude Code skill. Use `WebSearch`
> and `WebFetch` for all research. The skill has already run a light ObservePoint scan (CMP via
> `detect_cmp`, plus a homepage tag/pixel signature scan). Treat a POSITIVE scan finding as measured
> evidence (e.g. set `privacyConsentSurface.met=true` with evidence "CMP detected: <vendor> —
> confirmed via ObservePoint scan"; fold the tag list into `tagPixelDensity`). Treat a NEGATIVE scan
> as inconclusive (a static fetch misses dynamically-injected tags / lazy CMPs) — fall back to the
> web signal; never assert "no CMP / no tags" from a null scan. Output the classification as a JSON
> object per the skill's contract; do NOT compute scores (score_account.py does that).
```

- [ ] **Step 3: Add a skill-context note to the top of `research-and-contacts.md`**

Insert immediately after the first line (`# Stage 2 + 3 — Deep Research and Contact Sourcing`) a blank line then this block:
```markdown
> **Skill context:** You are running inside the `research-account` Claude Code skill. Use `WebSearch`
> and `WebFetch`. There is no Sequencer stage here — the "best opening angle" is INTERNAL strategy
> for the AE's dossier, never prospect-facing copy. Enrichment (email/phone) is out of scope: source
> real, named, currently-employed contacts with LinkedIn + a verification source URL; do not invent
> emails or phone numbers. Output the research + contacts as part of the skill's JSON contract.
```

- [ ] **Step 4: Create `icp-and-tone.md`**

```markdown
# ObservePoint ICP & framing (reference)

A condensed reference for the `research-account` skill. The authoritative scoring weights live in
`scoring-config.json`; this file is the qualitative framing.

## What ObservePoint does
A web governance platform: automated, browser-based auditing of the tags, pixels, cookies, and
third-party requests on enterprise websites. It proves what fired on which page under which consent
state, validates that a CMP enforces the user's choice, inventories every vendor receiving data, and
produces a dated, defensible audit trail.

## Four buying centers (privacy is the strongest, most durable fit)
- **Privacy / compliance** — "we deployed a consent platform; how do we prove it works on every page,
  every day?" Weight this highest.
- **Analytics / data quality** — "tracking breaks silently and we can't trust our numbers." A real but
  lighter signal than privacy.
- **Security** — "we have no inventory of which third parties receive data from our marketing pages."
- **Accessibility** — WCAG / European Accessibility Act conformance at scale.

## Strategy vs. copy (carry into the dossier)
Litigation, enforcement, and exposure are gold for TARGETING and for the AE's understanding. They are
NOT a weapon to wave at the recipient. In the dossier, the sharp legal framing lives only in
"best opening angle (internal strategy)". Prospect-facing outreach copy is a separate, later step and
is governed by a strict tone governor — out of scope for this skill.

## Persona priority titles
Chief Privacy Officer / VP Privacy; VP Marketing Technology / Director MarTech; VP Digital Analytics /
Head of Analytics; VP / Director Compliance or Legal (data-focused); Director Marketing Operations.
```

- [ ] **Step 5: Verify the files exist and the notes landed**

Run (from `observepoint-revenue/`):
```bash
grep -l "Skill context" skills/research-account/references/trigger-and-fit.md skills/research-account/references/research-and-contacts.md
test -f skills/research-account/references/icp-and-tone.md && echo "icp-and-tone ok"
```
Expected: both prompt paths print, then `icp-and-tone ok`.

- [ ] **Step 6: Commit**

```bash
git add skills/research-account/references/trigger-and-fit.md skills/research-account/references/research-and-contacts.md skills/research-account/references/icp-and-tone.md
git commit -m "feat: port NERD research prompts as research-account references"
```

---

## Task 5: Write `SKILL.md` (orchestration)

**Files:**
- Create: `skills/research-account/SKILL.md`

The SKILL ties it together. The frontmatter `description` is trigger-only (CSO-compliant), consistent with the plugin's other three skills. Verify triggering with a RED-baseline subagent run (writing-skills discipline).

- [ ] **Step 1: Create `SKILL.md` with this content**

````markdown
---
name: research-account
description: Use when a revenue or sales rep wants to research and qualify a single named prospect for ObservePoint — "research <company>", "is <company> a good fit", "qualify this account", "build an account dossier", "why now for <company>". Produces a scored ICP dossier (.docx) with dated/sourced why-now triggers and real sourced contacts. For sizing or pricing a deal use scope-calculator; this is account research, not contract scoping.
---

# Research Account

Given a named prospect, qualify it against ObservePoint's ICP, surface dated and sourced "why now"
triggers, build a deep dossier with real sourced contacts, score it deterministically, and render a
themed `.docx`.

This skill is the research brain ported from the NERD tool. The model classifies and researches;
`score_account.py` does the math; `build_dossier.py` renders the document.

## Inputs

- **Company name** (required).
- **Domain** (optional — look it up if not given).
- **`--deep-scan`** (optional flag) — also size an ObservePoint Site Census for `webScale`
  (time-intensive; only when asked).

## Workflow

Set `SKILL=${CLAUDE_PLUGIN_ROOT}/skills/research-account`. Read these references first:
`$SKILL/references/trigger-and-fit.md`, `$SKILL/references/research-and-contacts.md`,
`$SKILL/references/icp-and-tone.md`, and `$SKILL/references/scoring-config.json` (for the exact `fit`
keys and `whyNow` scoreKeys you must use).

1. **Resolve the domain.** Use the given domain, or find the prospect's primary domain via a quick
   `WebSearch`.

2. **Default scan (always):**
   - Call `detect_cmp({url: "https://<domain>/"})`. Record the CMP vendor (or none) and the
     `supported` flag.
   - **Tag/pixel inventory:** `WebFetch` the homepage (and 1–2 high-value pages) and identify the
     MarTech/pixel stack from script signatures — GTM (`googletagmanager.com/gtm.js`), GA4 (`gtag`),
     Adobe Launch (`assets.adobedtm.com`), Tealium (`tags.tiqcdn.com`), Segment, Meta Pixel
     (`fbevents.js`), etc.
   - **Caveat:** a POSITIVE finding is evidence; a NEGATIVE is inconclusive (static fetch misses
     dynamically-injected tags / lazy CMPs). Never assert "no CMP / no tags" from a null scan.

3. **`--deep-scan` only:** if the rep asked for it and a relevant Site Census exists, call
   `size_site_census` to measure `webScale` (real page count, multi-domain/SPA complexity); put the
   result in `scan.site_census`. Skip silently if unavailable.

4. **Research (WebSearch/WebFetch)** following the two reference prompts:
   - Classify each of the 6 ICP `fit` criteria (`met` true/false + short `evidence`), folding in the
     scan findings (CMP → `privacyConsentSurface`; tags → `tagPixelDensity`; census → `webScale`).
   - Find dated, **sourced** why-now triggers, each tagged with the single best `scoreKey` from
     `scoring-config.json`. Every trigger needs a real `sourceUrl` and a genuine web-tracking nexus.
     An empty trigger list is a valid, honest result — do not stretch (no BIPA, generic breaches,
     antitrust, product-safety).
   - Write the dossier fields (overview, pain hypotheses, competitor intel, tech-stack notes, best
     opening angle = INTERNAL strategy, research sources).
   - Source **2–5 real, currently-employed** contacts: name, title, linkedin, `sourceVerified`,
     `sourceUrl`, `personalizationHook`, `toneGuidance`, `avoid`. **No placeholders, no fabricated
     people or sources.** If you cannot verify a person, set `sourceVerified:false` (the dossier
     flags them as held back) — never invent.

5. **Write the classification JSON** to a temp file (e.g. `/tmp/<slug>-classification.json`) with
   keys: `account`, `domain`, `prepared_by`, `date` (today: 2026-06-07 or current), `scan{}`, `fit[]`,
   `triggers[]`, `rationale`, `research{}`, `contacts[]`. (See the spec §4 for the exact shape.)

6. **Score it:**
   ```bash
   python "$SKILL/scripts/score_account.py" /tmp/<slug>-classification.json /tmp/<slug>-scored.json
   ```

7. **Render the dossier:**
   ```bash
   python "$SKILL/scripts/build_dossier.py" /tmp/<slug>-scored.json <out>.docx
   ```

8. **Summarize in chat:** final score, QUALIFIED/NOT, dominant fit angle, the top trigger, number of
   sourced vs held-back contacts, and the `.docx` path.

## Red flags — stop and fix

| Rationalization | Reality |
|---|---|
| "I'll estimate the score myself." | No. `score_account.py` computes it from the config weights. You only classify. |
| "I couldn't find a contact, I'll put a likely name." | Never fabricate a person or a source URL. Set `sourceVerified:false`. |
| "The scan found no CMP, so they have none." | A static fetch misses lazy CMPs. Negative = inconclusive; use the web signal. |
| "There's a big lawsuit — lead the dossier with it as the pitch." | The legal angle is INTERNAL strategy only. Outreach copy is a separate, governed step. |
| "No trigger found, I'll stretch to a BIPA/antitrust item." | Triggers need a web-tracking nexus. An empty list is a valid result. |

## What this skill does not do (v1)

Discovery/territory prospecting, contact enrichment (email/phone), sequencing/sending, and Salesforce
sync are out of scope. The dossier is the deliverable; the rep takes it from there.
````

- [ ] **Step 2: Sanity-check the frontmatter parses and the scripts are reachable**

Run (from `observepoint-revenue/`):
```bash
python -c "import pathlib,re; t=pathlib.Path('skills/research-account/SKILL.md').read_text(); m=re.match(r'^---\n(.*?)\n---', t, re.S); assert m and 'name: research-account' in m.group(1) and 'description:' in m.group(1); print('frontmatter ok')"
test -f skills/research-account/scripts/score_account.py && test -f skills/research-account/scripts/build_dossier.py && echo "scripts ok"
```
Expected: `frontmatter ok` then `scripts ok`.

- [ ] **Step 3: RED-baseline trigger check (writing-skills discipline)**

Dispatch a subagent with a realistic user request that SHOULD trigger this skill, and confirm the
description would route to it. Use the Task/Agent tool with a prompt like: *"A rep says: 'Can you
research Arthur J. Gallagher and tell me if they're a good ObservePoint prospect?' Which
observepoint-revenue skill matches, based only on the skill descriptions?"* Expected: it names
`research-account`. If it instead routes to `scope-calculator`, tighten the description's "this is
account research, not contract scoping" clause. (This is a description-quality check, not a code test.)

- [ ] **Step 4: Commit**

```bash
git add skills/research-account/SKILL.md
git commit -m "feat: research-account SKILL.md (orchestration)"
```

---

## Task 6: Full suite, version bump, and final review

**Files:**
- Modify: `.claude-plugin/plugin.json`
- (check) `.claude-plugin/marketplace.json` if present

- [ ] **Step 1: Run the entire test suite**

Run (from `observepoint-revenue/`):
```bash
python -m pytest -q
```
Expected: all tests pass (the prior 47 + the new 13 = 60).

- [ ] **Step 2: Bump the plugin version**

In `.claude-plugin/plugin.json`, change `"version": "0.4.2"` to `"version": "0.5.0"`.

- [ ] **Step 3: Bump the version anywhere else it appears in the plugin manifest dir**

Run (from `observepoint-revenue/`):
```bash
grep -rn "0\.4\.2" .claude-plugin/ || echo "no other 0.4.2 references"
```
If `marketplace.json` (or any manifest) shows `0.4.2`, change it to `0.5.0` too.

- [ ] **Step 4: Final smoke — end-to-end with the test fixture**

Run (from `observepoint-revenue/`):
```bash
python - <<'PY'
import json, pathlib, subprocess, sys, tempfile
root = pathlib.Path('.').resolve()
sys.path.insert(0, str(root / 'skills/research-account/scripts'))
import score_account as sa
# reuse the build_dossier test's classification by importing the test module's data
sys.path.insert(0, str(root / 'tests'))
from test_build_dossier import CLASSIFICATION
d = tempfile.mkdtemp()
cj = pathlib.Path(d, 'c.json'); cj.write_text(json.dumps(CLASSIFICATION))
sj = pathlib.Path(d, 's.json'); dx = pathlib.Path(d, 'dossier.docx')
subprocess.run([sys.executable, 'skills/research-account/scripts/score_account.py', str(cj), str(sj), '2026-06-07'], check=True)
subprocess.run([sys.executable, 'skills/research-account/scripts/build_dossier.py', str(sj), str(dx)], check=True)
print('smoke ok ->', dx, 'final score', json.loads(sj.read_text())['score']['finalScore'])
PY
```
Expected: `smoke ok -> ...dossier.docx final score 120` (the build_dossier fixture has one trigger).

- [ ] **Step 5: Plan self-review against the spec**

Confirm each spec section maps to a task: §2 scan tiers → SKILL.md Task 5 + scan caveat in Task 4;
§3 components → Tasks 1–5; §4 classification contract → SKILL.md step 5 + scripts; §5 dossier sections
→ Task 3; §6 preserved properties → tests in Tasks 2–3 + SKILL red-flags; §8 testing/version → Tasks
2,3,6. No gaps. Fix any found inline.

- [ ] **Step 6: Commit**

```bash
git add .claude-plugin/
git commit -m "chore: bump observepoint-revenue to 0.5.0 (research-account skill)"
```

- [ ] **Step 7: (Optional) Supervised live run**

With the user's go-ahead, run the skill end-to-end on a real named prospect (e.g. the one they
choose), supervising the `detect_cmp` call and web research, and confirm the `.docx` renders. Do NOT
commit any real-prospect `.docx` (the gitignore already excludes `sample-output/`; write live output
there).

---

## Self-Review (completed by plan author)

- **Spec coverage:** §1 goal → Task 5; §2 data flow / scan tiers → Tasks 1–5 (scan logic in SKILL +
  reference note); §3 components → one task each; §4 classification JSON → SKILL step 5 + script
  inputs; §5 dossier sections → Task 3 tests assert each; §6 preserved properties → score split
  (Task 2), held-back gate + no-fabrication (Task 3 test + SKILL red flags), strategy-vs-copy label
  (Task 3), privacy weighting (Task 1 config), no-fabricated-scan (SKILL + reference); §7 out-of-scope
  → SKILL "does not do"; §8 testing/version/theming → Tasks 2,3,6; §9 port map → Tasks 1,2,4. No gaps.
- **Placeholder scan:** none — every code/step is complete.
- **Type consistency:** `score()` / `compute_fit()` / `recency_factor()` signatures and the
  `score{fitScore,whyNowScore,finalScore,qualified,lowFitHighTrigger,fitBreakdown,whyNowBreakdown}`
  shape are identical across Task 2 (impl), Task 3 (consumer), and the tests. The classification keys
  (`fit`,`triggers`,`scan`,`research`,`contacts`) match across spec §4, scripts, tests, and SKILL.
```
