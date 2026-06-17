# observepoint-revenue/tests/test_make_document.py
import json
import pathlib
import make_document

CONTENT = {
    "title": "Privacy Scan Overview",
    "subtitle": "Acme Pharma",
    "prepared_for": "Acme Pharma",
    "sections": [
        {"heading": "What we found", "body": "37 unique tags across 40 pages."},
        {"heading": "Next steps", "bullets": ["Block unapproved cookies", "Validate analytics"]},
    ],
}


def test_onepager_builds_html_with_brand(tmp_path, monkeypatch):
    monkeypatch.setattr(make_document.brand_kit, "html_to_pdf", lambda h, p: None)
    cj = tmp_path / "c.json"
    cj.write_text(json.dumps(CONTENT))
    out = tmp_path / "onepager.pdf"
    result = make_document.build("onepager", json.loads(cj.read_text()), str(out))
    assert result["engine"] is None
    produced = pathlib.Path(result["path"])
    assert produced.suffix == ".html" and produced.exists() and produced.stat().st_size > 0
    html = result["html"]
    assert "#14151A" in html.upper()            # dark theme by default
    assert "data:image/png;base64," in html      # logo embedded
    assert "Privacy Scan Overview" in html
    assert "© " in html and "ObservePoint" in html


def test_report_respects_light_override(tmp_path, monkeypatch):
    monkeypatch.setattr(make_document.brand_kit, "html_to_pdf", lambda h, p: None)
    out = tmp_path / "r.pdf"
    result = make_document.build("report", CONTENT, str(out), theme="light")
    assert "#FFFFFF" in result["html"].upper()
    assert result["theme"] == "light"
