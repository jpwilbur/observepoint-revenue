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
