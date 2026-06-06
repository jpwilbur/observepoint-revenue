import json
import subprocess
import sys
import pathlib

import pytest
from openpyxl import load_workbook

import build_evidence_appendix as bea

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "derive-page-count" / "scripts" / "build_evidence_appendix.py"

DATA = {
    "customer": "Acme",
    "rollup": {
        "url_total": 268_042, "path_floor": 1_900, "spiral_adjusted_anchor": 2_661,
        "low": 2_500, "high": 3_000, "confidence": "MEDIUM",
        "census_ids": [711], "crawl_status": "paused",
    },
    "per_domain": [
        {"hostname": "www.1stagency.com", "raw_urls": 266_042, "paths": 761,
         "patterns": 120, "spiral_flag": True, "spiral_ratio": 349.0,
         "defensible_pages": 761, "discounted": 265_281,
         "why": "349x query-param spiral",
         "url_samples": ["https://www.1stagency.com/", "https://www.1stagency.com/about"]},
        {"hostname": "shop.acme.com", "raw_urls": 2_000, "paths": 1_900,
         "patterns": 90, "spiral_flag": False, "spiral_ratio": 1.05,
         "defensible_pages": 1_900, "discounted": 100, "why": "",
         "url_samples": ["https://shop.acme.com/p/1"]},
    ],
}


def test_invariant_raises_on_mismatch():
    bad = json.loads(json.dumps(DATA))
    bad["rollup"]["spiral_adjusted_anchor"] = 9_999  # != 761 + 1900
    with pytest.raises(ValueError):
        bea.build_workbook(bad)


def test_workbook_structure(tmp_path):
    wb = bea.build_workbook(DATA)
    assert wb.sheetnames == ["Scope Summary", "Pages by Domain", "Raw Evidence", "URL Samples"]

    pbd = wb["Pages by Domain"]
    assert [c.value for c in pbd[1]] == [
        "Domain", "Defensible pages", "Spiral?", "Include in scope?", "Priority", "Notes"]
    assert pbd[2][0].value == "www.1stagency.com"
    assert pbd[2][1].value == 761
    assert pbd[2][2].value == "Yes"
    # customer-fillable columns present and empty
    assert pbd[2][3].value is None and pbd[2][4].value is None and pbd[2][5].value is None

    raw = wb["Raw Evidence"]
    assert raw[2][1].value == 266_042            # raw distinct URLs
    assert raw[2][5].value == "349x query-param spiral"

    samples = wb["URL Samples"]
    assert samples.max_row == 1 + 2 + 1          # header + 2 + 1 sample rows


def test_cli_writes_file(tmp_path):
    f = tmp_path / "in.json"; f.write_text(json.dumps(DATA))
    out = tmp_path / "evidence.xlsx"
    res = subprocess.run([sys.executable, str(SCRIPT), str(f), str(out)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    wb = load_workbook(out)
    assert "Scope Summary" in wb.sheetnames
