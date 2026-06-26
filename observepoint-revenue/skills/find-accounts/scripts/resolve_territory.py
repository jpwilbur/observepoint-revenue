"""Normalize an OP_Territories__c SOQL result into a find-accounts territory boundary.

The MODEL runs the territory query (see salesforce-core/references/salesforce-org.md) and
passes its JSON here; this script computes the boundary the sweep is constrained to.
No Salesforce calls, no model math.

CLI:  resolve_territory.py <territory-soql.json>     # prints boundary JSON to stdout
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "salesforce-core" / "scripts"))
import sf_io  # noqa: E402


def _collect(records, key):
    """Sorted unique non-empty string values of `key` across records."""
    out = []
    for r in records:
        v = (r or {}).get(key)
        if isinstance(v, str):
            v = v.strip()
        if v and v not in out:
            out.append(v)
    return sorted(out)


def _rel_name(records, rel):
    """Sorted unique .Name values from a relationship field (e.g. AE__r.Name)."""
    out = []
    for r in records:
        sub = (r or {}).get(rel)
        n = (sub.get("Name") or "").strip() if isinstance(sub, dict) else ""
        if n and n not in out:
            out.append(n)
    return sorted(out)


def normalize_territory(mcp_result):
    """OP_Territories__c records -> boundary dict. An empty result -> all-empty boundary
    (territory_ids == []), which the skill treats as 'no territory — get an explicit target'."""
    records = sf_io.parse_records(mcp_result)
    return {
        "territory_ids": sorted({r.get("Id") for r in records if (r or {}).get("Id")}),
        "regions": _collect(records, "World_Region__c"),
        "sub_regions": _collect(records, "Sub_Region__c"),
        "countries": _collect(records, "Country__c"),
        "states": _collect(records, "State__c"),
        "segments": _collect(records, "Segment__c"),
        "ae_names": _rel_name(records, "AE__r"),
        "adm_names": _rel_name(records, "ADM__r"),
        "csm_names": _rel_name(records, "CSM__r"),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Normalize an OP_Territories__c SOQL result.")
    ap.add_argument("territory_json", help="JSON file of the territory SOQL result")
    a = ap.parse_args(argv)
    try:
        data = json.loads(pathlib.Path(a.territory_json).read_text())
    except (OSError, ValueError) as e:
        sys.exit(f"could not read territory JSON {a.territory_json!r}: {e}")
    try:
        boundary = normalize_territory(data)
    except sf_io.SalesforceResultError as e:
        sys.exit(f"territory result unusable: {e}")
    print(json.dumps(boundary, indent=2))


if __name__ == "__main__":
    main()
