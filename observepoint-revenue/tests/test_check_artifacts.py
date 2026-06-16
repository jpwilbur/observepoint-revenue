import json
import pathlib
import subprocess
import sys

import check_artifacts as ca

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "scope-calculator" / "scripts" / "check_artifacts.py"

CLEAN = ["https://calix.com/", "https://calix.com/products", "https://calix.com/support/contact"]
DIRTY = ['https://tkogrp.com/%22//news//x///%22', 'https://tkogrp.com/a"b', "https://tkogrp.com/p//q"]

# Path-recursion trap (post-mortem Issue 1 — stevenson-insurance.com, 1.71M URLs). A relative-link
# trap re-appends a nav segment onto the path over and over. It has NO %22, NO doubled-slash, NO
# query string — so the %22-artifact gate AND the query-param spiral gate are BOTH blind to it.
RECURSION = ["https://stevenson-insurance.com/contact/" + "/".join(["business-insurance"] * n)
             + "/commercial-property-insurance" for n in range(3, 13)]
# Genuinely deep but NON-repeating paths must stay clean (guard against false positives).
LEGIT_DEEP = ["https://docs.acme.com/api/v2/reference/objects/user/methods/create",
              "https://shop.acme.com/category/mens/shoes/running/trail/waterproof"]


def test_is_artifact_flags_escaped_quote_literal_quote_and_doubled_slash():
    assert ca.is_artifact("https://x.com/%22//news") is True
    assert ca.is_artifact('https://x.com/a"b') is True
    assert ca.is_artifact("https://x.com/p//q") is True
    assert ca.is_artifact("https://x.com/clean/path") is False
    assert ca.is_artifact("https://x.com/") is False


def test_clean_list_is_clean():
    r = ca.detect_artifacts(CLEAN)
    assert r["artifact_count"] == 0 and r["artifact_pct"] == 0.0 and r["verdict"] == "clean"


def test_inflated_list_flags_majority_like_tko():
    # TKO: ~226 escaped-quote artifacts among 306 raw URLs (~74%); real pages ~80.
    urls = ["https://tkogrp.com/%22//n%22"] * 226 + [f"https://tkogrp.com/real/{i}" for i in range(80)]
    r = ca.detect_artifacts(urls)
    assert r["total"] == 306
    assert r["artifact_count"] == 226
    assert 73.0 <= r["artifact_pct"] <= 75.0
    assert r["verdict"] == "inflated"
    assert r["artifact_samples"]                       # carries examples for the rep


def test_empty_is_clean():
    assert ca.detect_artifacts([]) == {
        "total": 0, "artifact_count": 0, "artifact_pct": 0.0, "artifact_samples": [],
        "recursion_count": 0, "recursion_pct": 0.0, "recursion_samples": [],
        "junk_count": 0, "junk_pct": 0.0, "collapsed_distinct": 0, "verdict": "clean"}


# --- Path-recursion detection (post-mortem Issue 1) -----------------------------------------
def test_is_recursion_flags_repeated_segments():
    assert ca.is_recursion("https://x.com/a/a/a/b") is True               # 3 consecutive repeats
    assert ca.is_recursion("https://x.com/a/b/a/b/a/b/a") is True          # one segment 4x total
    assert ca.is_recursion("https://x.com/contact/biz/biz/biz/biz") is True


def test_is_recursion_does_not_flag_legit_or_artifact_paths():
    assert ca.is_recursion("https://x.com/api/v2/reference/objects/user") is False
    assert ca.is_recursion("https://x.com/category/mens/shoes/running") is False
    assert ca.is_recursion("https://x.com/p//q") is False                 # doubled-slash = ARTIFACT, not recursion
    assert ca.is_recursion("https://x.com/news/news-archive") is False    # distinct segments that merely share a prefix
    assert ca.is_recursion("https://x.com/") is False


def test_recursion_trap_is_flagged_inflated_not_clean():
    # The exact post-mortem failure: a host that is ~100% recursion junk must NOT verdict "clean".
    r = ca.detect_artifacts(RECURSION)
    assert r["recursion_count"] == len(RECURSION)
    assert r["artifact_count"] == 0            # NOT a %22 artifact — a distinct failure mode
    assert r["verdict"] == "inflated"          # was "clean" before the fix → the silent ~15× over-count
    assert r["recursion_samples"]
    assert r["collapsed_distinct"] == 1        # the whole sample collapses to one real template


def test_legit_deep_paths_stay_clean():
    r = ca.detect_artifacts(LEGIT_DEEP)
    assert r["recursion_count"] == 0 and r["verdict"] == "clean"


def test_cli_json_list_inflated(tmp_path):
    f = tmp_path / "u.json"; f.write_text(json.dumps(DIRTY))
    res = subprocess.run([sys.executable, str(SCRIPT), str(f)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert "inflated" in res.stdout.lower() and "3/3" in res.stdout


def test_cli_newline_text_clean(tmp_path):
    f = tmp_path / "u.txt"; f.write_text("\n".join(CLEAN))
    res = subprocess.run([sys.executable, str(SCRIPT), str(f)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert "clean" in res.stdout.lower()
