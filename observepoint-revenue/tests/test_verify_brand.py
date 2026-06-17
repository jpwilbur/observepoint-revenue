# observepoint-revenue/tests/test_verify_brand.py
import pathlib
import verify_brand

FIX = pathlib.Path(__file__).resolve().parent / "fixtures" / "site_homepage.html"


def test_extract_yellow_from_css():
    html = FIX.read_text()
    assert verify_brand.extract_site_yellow(html).upper() == "#F2CD14"


def test_check_drift_reports_match(monkeypatch):
    monkeypatch.setattr(verify_brand, "fetch", lambda url: FIX.read_text())
    report = verify_brand.check_drift()
    assert report["yellow"]["site"].upper() == "#F2CD14"
    assert report["yellow"]["spec"].upper() == "#F2CD14"
    assert report["yellow"]["match"] is True
    assert report["ok"] is True


def test_check_drift_flags_mismatch(monkeypatch):
    monkeypatch.setattr(verify_brand, "fetch",
                        lambda url: '<style>.logo{color:#ABCDEF}</style>')
    report = verify_brand.check_drift()
    assert report["yellow"]["match"] is False
    assert report["ok"] is False


def test_extract_yellow_ignores_background_color():
    # background-color must NOT be mistaken for the logo's color
    html = '<style>.logo{background-color:#000000;color:#f2cd14}</style>'
    assert verify_brand.extract_site_yellow(html).upper() == "#F2CD14"


def test_check_drift_when_logo_css_absent(monkeypatch):
    monkeypatch.setattr(verify_brand, "fetch", lambda url: "<html>no logo css here</html>")
    report = verify_brand.check_drift()
    assert report["yellow"]["site"] is None
    assert report["yellow"]["match"] is False
    assert report["ok"] is False
