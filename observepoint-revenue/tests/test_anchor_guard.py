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
