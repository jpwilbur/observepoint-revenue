import json
import pathlib
import subprocess
import sys

import check_artifacts as ca

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "scope-calculator" / "scripts" / "check_artifacts.py"

CLEAN = ["https://calix.com/", "https://calix.com/products", "https://calix.com/support/contact"]
DIRTY = ['https://tkogrp.com/%22//news//x///%22', 'https://tkogrp.com/a"b', "https://tkogrp.com/p//q"]


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
    assert ca.detect_artifacts([]) == {"total": 0, "artifact_count": 0, "artifact_pct": 0.0,
                                       "artifact_samples": [], "verdict": "clean"}


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
