# tests/test_render_post_mortem.py
import json, subprocess, sys, pathlib
import render_post_mortem as rpm

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "op-mcp-post-mortem" / "scripts" / "render_post_mortem.py"

SECTIONS = ["## Summary", "## Severity & impact", "## Environment", "## Tools involved",
            "## What happened vs. expected", "## Reproduction config", "## Conversation evidence",
            "## Sharing & redaction notes", "## Maintainer section"]


def _facts(**over):
    base = {
        "title": "OP MCP: stale latest run", "date": "2026-06-25", "mcp_version": "0.6.40",
        "reporter": "Jarrod Wilbur <jarrod.wilbur@observepoint.com>", "severity": "Medium",
        "summary": "get_audit_runs surfaced an older run as latest.",
        "impact": "User read a tag count off the wrong run.",
        "client": "Claude Desktop", "account_context": "redacted account",
        "tools": [{"name": "mcp__ObservePoint__get_audit_runs", "params": {"auditId": 90233}}],
        "observed": "Run #771 (May 30) reported as latest.", "expected": "June 24 run is latest.",
        "reproduction": {"complete": False, "account_id": "[redacted]",
                         "resources": [{"type": "audit", "id": "90233"}],
                         "notes": "config snapshot not captured"},
        "evidence": "tool returned 5 runs; topmost was #771.",
        "redaction_notes": "credentials and customer email redacted; reporter email kept.",
    }
    base.update(over)
    return base


def test_valid_facts_have_no_problems():
    assert rpm.validate(_facts()) == []


def test_render_contains_all_sections():
    md = rpm.render(_facts())
    for h in SECTIONS:
        assert h in md, f"missing section {h}"


def test_missing_required_field_is_a_problem():
    f = _facts()
    del f["summary"]
    assert any("summary" in p for p in rpm.validate(f))


def test_unknown_severity_rejected():
    assert any("severity" in p for p in rpm.validate(_facts(severity="Huge")))


def test_incomplete_repro_requires_notes():
    assert any("notes" in p for p in rpm.validate(_facts(reproduction={"complete": False})))
    assert rpm.validate(_facts(reproduction={"complete": False, "notes": "snapshot missing"})) == []


def test_complete_repro_ok_without_notes():
    assert rpm.validate(_facts(
        reproduction={"complete": True, "resources": [{"type": "audit", "id": "1"}]})) == []


def test_tools_entry_must_have_name():
    assert any("tools[0]" in p for p in rpm.validate(_facts(tools=[{"params": {}}])))


def test_maintainer_section_is_blank_skeleton():
    md = rpm.render(_facts())
    assert "Classification:" in md and "Root cause:" in md and "Verification evidence:" in md


def test_incomplete_repro_flagged_in_output():
    md = rpm.render(_facts())
    assert "INCOMPLETE" in md


def test_cli_fails_loudly_on_missing_fields(tmp_path):
    f = tmp_path / "facts.json"
    f.write_text(json.dumps({"date": "2026-06-25"}))
    r = subprocess.run([sys.executable, str(SCRIPT), str(f)], capture_output=True, text=True)
    assert r.returncode != 0 and "fix these first" in r.stderr


def test_cli_writes_out_with_dirs(tmp_path):
    f = tmp_path / "facts.json"
    f.write_text(json.dumps(_facts()))
    out = tmp_path / "nested" / "dir" / "post-mortem.md"
    r = subprocess.run([sys.executable, str(SCRIPT), str(f), "--out", str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0 and out.exists()
    assert "## Summary" in out.read_text(encoding="utf-8")
