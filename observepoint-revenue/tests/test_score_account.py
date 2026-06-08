import json
import pathlib
import subprocess
import sys

import pytest

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


def test_score_raises_without_a_usable_date():
    with pytest.raises(ValueError):
        sa.score({"account": "X", "fit": [], "triggers": [], "rationale": ""})
