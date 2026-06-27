import json
import pathlib
import subprocess
import sys

import resolve_territory as rt


def _terr(**kw):
    base = {"Id": "a0X1", "World_Region__c": "AMER", "Sub_Region__c": "US West",
            "Country__c": "United States", "State__c": "California", "Segment__c": "Enterprise",
            "AE__r": {"Name": "Dana AE"}, "ADM__r": {"Name": "Sam ADM"}, "CSM__r": None}
    base.update(kw)
    return base


def test_normalize_collects_unique_sorted():
    res = {"records": [_terr(), _terr(Id="a0X2", State__c="Nevada")], "done": True}
    b = rt.normalize_territory(res)
    assert b["territory_ids"] == ["a0X1", "a0X2"]
    assert b["states"] == ["California", "Nevada"]
    assert b["regions"] == ["AMER"]
    assert b["segments"] == ["Enterprise"]
    assert b["ae_names"] == ["Dana AE"]
    assert b["adm_names"] == ["Sam ADM"]
    assert b["csm_names"] == []          # a None relationship is tolerated


def test_empty_result_is_empty_boundary():
    b = rt.normalize_territory({"records": [], "done": True})
    assert b["territory_ids"] == [] and b["regions"] == []


def test_cli_prints_boundary(tmp_path):
    f = tmp_path / "t.json"
    f.write_text(json.dumps({"records": [_terr()], "done": True}))
    script = pathlib.Path(rt.__file__).resolve().parent / "resolve_territory.py"
    res = subprocess.run([sys.executable, str(script), str(f)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["countries"] == ["United States"]
