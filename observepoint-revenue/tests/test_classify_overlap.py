import json
import pathlib
import subprocess
import sys

import classify_overlap as co

TERR_IDS = ["a0X1"]
TARGET = "005AAA"


def _acct(name, website, type_="Prospect", owner_id="005ZZZ", owner_name="Other Rep", terr=None):
    return {"Name": name, "Website": website, "Type": type_, "OwnerId": owner_id,
            "Owner": {"Name": owner_name}, "OP_Territory__c": terr}


def _cand(name, domain=None):
    c = {"name": name, "triggerKey": "pixelWiretapSuit", "sourceUrl": "https://x.test/a"}
    if domain:
        c["domain"] = domain
    return c


def test_net_new_kept_with_null_status():
    kept, summ = co.classify([_cand("New Co", "newco.com")], [], TERR_IDS, TARGET)
    assert len(kept) == 1 and kept[0]["sf_status"] is None
    assert summ["kept"] == 1


def test_in_territory_hard_excluded():
    accts = [_acct("Acme", "acme.com", terr="a0X1")]
    kept, summ = co.classify([_cand("Acme", "acme.com")], accts, TERR_IDS, TARGET)
    assert kept == []
    assert summ["hard_excluded"]["own_or_territory"] == ["Acme"]


def test_owned_by_target_hard_excluded_outside_territory():
    accts = [_acct("Named Co", "named.com", owner_id=TARGET, terr=None)]
    kept, summ = co.classify([_cand("Named Co", "named.com")], accts, TERR_IDS, TARGET)
    assert kept == []
    assert summ["hard_excluded"]["own_or_territory"] == ["Named Co"]


def test_customer_hard_excluded_any_owner():
    accts = [_acct("BigCust", "bigcust.com", type_="Customer", terr=None)]
    kept, summ = co.classify([_cand("BigCust", "bigcust.com")], accts, TERR_IDS, TARGET)
    assert kept == []
    assert summ["hard_excluded"]["customer"] == ["BigCust"]


def test_other_rep_prospect_flagged_not_dropped():
    accts = [_acct("Rival Owned", "rival.com", type_="Prospect", owner_name="Pat Other")]
    kept, summ = co.classify([_cand("Rival Owned", "rival.com")], accts, TERR_IDS, TARGET)
    assert len(kept) == 1
    assert kept[0]["sf_status"] == {"owner": "Pat Other", "type": "Prospect"}
    assert summ["flagged"] == ["Rival Owned"]


def test_name_fallback_when_no_domain():
    accts = [_acct("Example Health System Inc", "", type_="Prospect", owner_name="Pat")]
    kept, summ = co.classify([_cand("The Example Health-System, Inc.")], accts, TERR_IDS, TARGET)
    assert kept[0]["sf_status"]["owner"] == "Pat"
    assert len(kept) == 1
    assert kept[0]["sf_status"] == {"owner": "Pat", "type": "Prospect"}
    assert summ["flagged"] == ["The Example Health-System, Inc."]


def test_cli_writes_annotated_and_summary(tmp_path):
    cands = {"date": "2026-06-25", "candidates": [_cand("New Co", "newco.com"),
                                                  _cand("BigCust", "bigcust.com")]}
    matches = {"records": [_acct("BigCust", "bigcust.com", type_="Customer")], "done": True}
    boundary = {"territory_ids": TERR_IDS}
    cf = tmp_path / "c.json"; cf.write_text(json.dumps(cands))
    mf = tmp_path / "m.json"; mf.write_text(json.dumps(matches))
    bf = tmp_path / "b.json"; bf.write_text(json.dumps(boundary))
    out = tmp_path / "annotated.json"
    script = pathlib.Path(co.__file__).resolve().parent / "classify_overlap.py"
    res = subprocess.run([sys.executable, str(script), str(cf), str(mf),
                          "--territory", str(bf), "--target-user", TARGET, "--out", str(out)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    data = json.loads(out.read_text())
    assert [c["name"] for c in data["candidates"]] == ["New Co"]   # customer hard-excluded
    assert data["date"] == "2026-06-25"                            # top-level keys preserved
    assert "hard-excluded" in res.stderr
