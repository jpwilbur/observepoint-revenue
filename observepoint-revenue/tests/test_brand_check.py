# observepoint-revenue/tests/test_brand_check.py
import brand_check


def test_flags_misspelled_company_name():
    issues = brand_check.check_text("We love Observepoint and Observe Point.")
    kinds = {i["kind"] for i in issues}
    assert "naming" in kinds
    # both bad spellings flagged
    bad = {i["found"] for i in issues if i["kind"] == "naming"}
    assert "Observepoint" in bad and "Observe Point" in bad


def test_clean_text_has_no_naming_issues():
    issues = brand_check.check_text("ObservePoint scans your site.")
    assert [i for i in issues if i["kind"] == "naming"] == []


def test_flags_off_palette_hex():
    issues = brand_check.check_text("color: #ABCDEF; accent: #F2CD14;")
    offp = [i for i in issues if i["kind"] == "color"]
    assert any(i["found"].upper() == "#ABCDEF" for i in offp)
    assert all(i["found"].upper() != "#F2CD14" for i in offp)  # brand color is allowed


def test_fix_text_corrects_naming():
    fixed = brand_check.fix_text("Observepoint and Observe Point rock.")
    assert "ObservePoint and ObservePoint rock." == fixed


import subprocess as _sp
import sys as _sys
import brand_check as _bc


def test_cli_exit_codes(tmp_path):
    script = _bc.__file__
    dirty = tmp_path / "dirty.txt"
    dirty.write_text("We use Observepoint daily.")
    # report mode: issues found -> exit 1
    r = _sp.run([_sys.executable, script, str(dirty)], capture_output=True, text=True)
    assert r.returncode == 1
    # --fix rewrites and exits 0; file no longer contains the bad spelling
    r = _sp.run([_sys.executable, script, str(dirty), "--fix"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "Observepoint" not in dirty.read_text()
    assert "ObservePoint" in dirty.read_text()
    # clean file -> exit 0
    clean = tmp_path / "clean.txt"
    clean.write_text("ObservePoint is great.")
    r = _sp.run([_sys.executable, script, str(clean)], capture_output=True, text=True)
    assert r.returncode == 0
    # no args -> usage error exit 2
    r = _sp.run([_sys.executable, script], capture_output=True, text=True)
    assert r.returncode == 2
