import json
import pathlib
import subprocess
import sys

import build_inventory as bi

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "owned-properties" / "scripts" / "build_inventory.py"

DATA = {
    "org": "Arthur J. Gallagher & Co.", "prepared_by": "Jarrod Wilbur", "date": "2026-06-09",
    "properties": [
        {"registrable": "ajg.com", "type": "primary", "confidence": "confirmed",
         "evidence": "Corporate primary; WHOIS registrant match.", "source": "https://ajg.com/",
         "host_count": 3, "sample_hosts": ["ajg.com", "www.ajg.com", "jobs.ajg.com"]},
        {"registrable": "gallagherbassett.com", "type": "subsidiary", "confidence": "confirmed",
         "evidence": "SEC 10-K Exhibit 21 subsidiary.", "source": "https://sec.gov/x",
         "host_count": 1, "sample_hosts": ["www.gallagherbassett.com"]},
        {"registrable": "ajginternational.com", "type": "regional", "confidence": "likely",
         "evidence": "Linked from ajg.com footer.", "source": "https://ajg.com/",
         "host_count": 0, "sample_hosts": []},
        {"registrable": "gallagher-maybe.com", "type": "other", "confidence": "possible",
         "evidence": "Similar branding, unconfirmed.", "source": "", "host_count": 0, "sample_hosts": []},
    ],
    "excluded": [{"domain": "cdn.cookielaw.org", "why": "OneTrust CMP vendor — third-party"}],
}


def _col1(ws):
    return [row[0] for row in ws.iter_rows(min_row=2, values_only=True) if row and row[0] is not None]


def _text(ws):
    return "\n".join(str(v) for row in ws.iter_rows(values_only=True) for v in row if v is not None)


def test_four_sheets():
    wb = bi.build_workbook(DATA)
    assert wb.sheetnames == ["Confirmed Properties", "For Review (unconfirmed)",
                             "All hostnames", "Methodology & sources"]


def test_confirmed_only_on_confirmed_sheet():
    wb = bi.build_workbook(DATA)
    assert _col1(wb["Confirmed Properties"]) == ["ajg.com", "gallagherbassett.com"]


def test_unconfirmed_only_on_review_sheet():
    wb = bi.build_workbook(DATA)
    assert _col1(wb["For Review (unconfirmed)"]) == ["ajginternational.com", "gallagher-maybe.com"]


def test_review_confidence_column():
    ws = bi.build_workbook(DATA)["For Review (unconfirmed)"]
    confs = [row[2] for row in ws.iter_rows(min_row=2, values_only=True)]
    assert confs == ["LIKELY", "POSSIBLE"]


def test_all_hostnames_from_confirmed_only():
    t = _text(bi.build_workbook(DATA)["All hostnames"])
    assert "jobs.ajg.com" in t and "www.gallagherbassett.com" in t


def test_methodology_lists_excluded():
    t = _text(bi.build_workbook(DATA)["Methodology & sources"])
    assert "cdn.cookielaw.org" in t and "third-party" in t


def test_confirmed_domains_feed_is_confirmed_only():
    assert bi.confirmed_domains(DATA) == ["ajg.com", "gallagherbassett.com"]


def test_empty_properties_yields_four_sheets_and_no_domains():
    data = {"org": "Empty Co", "properties": [], "excluded": []}
    wb = bi.build_workbook(data)
    assert wb.sheetnames == ["Confirmed Properties", "For Review (unconfirmed)",
                             "All hostnames", "Methodology & sources"]
    assert bi.confirmed_domains(data) == []


def test_all_hostnames_reads_all_hosts_file(tmp_path):
    hosts_file = tmp_path / "h.json"
    hosts_file.write_text(json.dumps({"registrable": "ajg.com",
                                      "all_hosts": ["ajg.com", "api.ajg.com", "vpn.ajg.com"]}))
    data = {"org": "X", "excluded": [], "properties": [
        {"registrable": "ajg.com", "type": "primary", "confidence": "confirmed", "evidence": "e",
         "source": "https://ajg.com/", "host_count": 3, "sample_hosts": ["ajg.com"],
         "all_hosts_file": str(hosts_file)}]}
    t = _text(bi.build_workbook(data)["All hostnames"])
    assert "api.ajg.com" in t and "vpn.ajg.com" in t   # full list from the file, not just sample_hosts


def test_typoed_confidence_is_dropped_with_warning(capsys):
    # A "confidense" typo means the real `confidence` key is MISSING -> the row must be dropped
    # LOUDLY (named WARNING on stderr), not silently lost from the feed. The good row still lands.
    data = {"org": "X", "excluded": [], "properties": [
        {"registrable": "good.com", "type": "primary", "confidence": "confirmed",
         "evidence": "WHOIS match", "source": "https://good.com/", "host_count": 1,
         "sample_hosts": ["good.com"]},
        {"registrable": "typo.com", "type": "primary", "confidense": "confirmed",  # typo'd key
         "evidence": "should have been confirmed", "source": "https://typo.com/",
         "host_count": 1, "sample_hosts": ["typo.com"]},
    ]}
    wb = bi.build_workbook(data)
    err = capsys.readouterr().err
    assert "WARNING" in err and "typo.com" in err          # dropped entry is named
    assert _col1(wb["Confirmed Properties"]) == ["good.com"]  # the good domain still lands
    assert bi.confirmed_domains(data) == ["good.com"]         # and feeds scope-calculator


def test_unknown_confidence_value_is_dropped_with_warning(capsys):
    # An out-of-enum confidence value (e.g. "definitely") is also dropped with a named warning.
    data = {"org": "X", "excluded": [], "properties": [
        {"registrable": "ok.com", "confidence": "likely", "evidence": "footer",
         "source": "https://ok.com/", "host_count": 0, "sample_hosts": []},
        {"registrable": "bad.com", "confidence": "definitely", "evidence": "guess",
         "source": "https://bad.com/", "host_count": 0, "sample_hosts": []},
    ]}
    wb = bi.build_workbook(data)
    err = capsys.readouterr().err
    assert "WARNING" in err and "bad.com" in err
    assert _col1(wb["For Review (unconfirmed)"]) == ["ok.com"]  # only the valid row survives


def test_missing_registrable_or_source_is_dropped_with_warning(capsys):
    data = {"org": "X", "excluded": [], "properties": [
        {"registrable": "", "confidence": "confirmed", "evidence": "e",
         "source": "https://x.com/", "host_count": 0, "sample_hosts": []},      # missing registrable
        {"registrable": "nosrc.com", "confidence": "confirmed", "evidence": "e",
         "host_count": 0, "sample_hosts": []},                                  # missing source
    ]}
    wb = bi.build_workbook(data)
    err = capsys.readouterr().err
    assert err.count("WARNING") == 2
    assert "nosrc.com" in err
    assert _col1(wb["Confirmed Properties"]) == []   # both invalid rows dropped


def test_valid_data_emits_no_warning(capsys):
    bi.build_workbook(DATA)
    assert "WARNING" not in capsys.readouterr().err


def test_cli_writes_only_xlsx_and_prints_confirmed_domains(tmp_path):
    f = tmp_path / "c.json"; f.write_text(json.dumps(DATA))
    xlsx = tmp_path / "out.xlsx"
    res = subprocess.run([sys.executable, str(SCRIPT), str(f), str(xlsx)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert xlsx.exists()
    # ONLY the .xlsx is written — no stray .txt cluttering the deliverable folder.
    assert list(tmp_path.glob("*.txt")) == []
    # confirmed domains are printed (copy-pasteable for scope-calculator); unconfirmed are not.
    assert "ajg.com" in res.stdout and "gallagherbassett.com" in res.stdout
    assert "ajginternational.com" not in res.stdout and "gallagher-maybe.com" not in res.stdout
