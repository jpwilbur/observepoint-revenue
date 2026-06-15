import json
import pathlib
import subprocess
import sys

import fetch_samples as fs

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "scope-calculator" / "scripts" / "fetch_samples.py"


def _conditions(body):
    return body["filters"]["conditions"]


def _find(conditions, column_id):
    return [c for c in conditions if c["filteredColumn"]["columnId"] == column_id]


def test_build_query_groups_by_link_url():
    body = fs.build_query(711, "jobs.acme.com")
    assert body["columns"] == [{"columnId": "LINK_URL", "groupBy": True}]
    assert body["filters"]["conditionMatchMode"] == "all"
    assert body["size"] >= 10


def test_build_query_census_id_filter():
    body = fs.build_query(711, "jobs.acme.com")
    census = _find(_conditions(body), "SITE_CENSUS_ID")
    assert len(census) == 1
    c = census[0]
    assert c["operator"] == "integer_in"
    assert c["args"] == [711]
    assert c["negated"] is False


def test_build_query_host_filter():
    body = fs.build_query(711, "jobs.acme.com")
    link = _find(_conditions(body), "LINK_URL")
    host = [c for c in link if c.get("arg") == "//jobs.acme.com"]
    assert len(host) == 1
    assert host[0]["operator"] == "string_contains"
    assert host[0]["negated"] is False


def test_build_query_normal_mode_excludes_junk():
    body = fs.build_query(711, "jobs.acme.com")
    conditions = _conditions(body)
    # The four junk exclusions are negated string_contains on LINK_URL.
    excluded = {c["arg"] for c in conditions if c.get("negated") is True}
    assert excluded == {"?", "%22", ".pdf", ".jpg"}


def test_build_query_raw_mode_keeps_only_two_filters():
    body = fs.build_query(711, "jobs.acme.com", raw=True)
    conditions = _conditions(body)
    # raw mode: ONLY SITE_CENSUS_ID + //<hostname> — no junk exclusions so junk can be measured.
    assert len(conditions) == 2
    assert all(c.get("negated") is False for c in conditions)
    cols = {c["filteredColumn"]["columnId"] for c in conditions}
    assert cols == {"SITE_CENSUS_ID", "LINK_URL"}
    host = [c for c in conditions if c["filteredColumn"]["columnId"] == "LINK_URL"]
    assert host[0]["arg"] == "//jobs.acme.com"


def test_build_query_normal_mode_has_six_conditions():
    # 2 keep (census + host) + 4 negated junk exclusions
    body = fs.build_query(711, "jobs.acme.com")
    assert len(_conditions(body)) == 6


def test_parse_samples_extracts_link_urls():
    response = {
        "rows": [
            {"LINK_URL": "https://jobs.acme.com/"},
            {"LINK_URL": "https://jobs.acme.com/careers"},
            {"LINK_URL": "https://jobs.acme.com/apply"},
        ]
    }
    assert fs.parse_samples(response) == [
        "https://jobs.acme.com/",
        "https://jobs.acme.com/careers",
        "https://jobs.acme.com/apply",
    ]


def test_parse_samples_empty_returns_empty():
    assert fs.parse_samples({}) == []
    assert fs.parse_samples({"rows": []}) == []
    assert fs.parse_samples(None) == []


def test_parse_samples_tolerates_missing_link_url():
    response = {"rows": [{"LINK_URL": "https://jobs.acme.com/"}, {"OTHER": "x"}, {}]}
    assert fs.parse_samples(response) == ["https://jobs.acme.com/"]


def test_cli_prints_normal_query_json():
    res = subprocess.run([sys.executable, str(SCRIPT), "711", "jobs.acme.com"],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    body = json.loads(res.stdout)
    assert len(body["filters"]["conditions"]) == 6


def test_cli_raw_flag_prints_raw_query():
    res = subprocess.run([sys.executable, str(SCRIPT), "711", "jobs.acme.com", "--raw"],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    body = json.loads(res.stdout)
    assert len(body["filters"]["conditions"]) == 2
