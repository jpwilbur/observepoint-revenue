"""find-accounts overlap-guard: 'own hard, others flagged'.

Given the swept candidates, the Salesforce account-match result, the resolved territory
boundary, and the target AE/ADM user id, classify each candidate against SF:
  - hard-exclude  : in the target's territory OR owned by the target, OR Type == 'Customer'
  - flag (keep)   : exists in SF under another rep / a non-customer prospect/previous/defunct
  - net-new (keep): no SF match
Hard-excludes are removed; survivors get an `sf_status` that rank_candidates displays.
The MODEL gathers the SF data; this script only classifies. No Salesforce calls.

CLI:  classify_overlap.py <candidates.json> <sf-matches.json> --territory <boundary.json>
                          --target-user <UserId> [--out <annotated.json>]
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "salesforce-core" / "scripts"))
import sf_io  # noqa: E402
from rank_candidates import normalize_name  # noqa: E402  (same dir; on sys.path at runtime + via conftest)

HARD_EXCLUDE_TYPES = {"Customer"}


def _index(accounts):
    """domain -> account and normalized-name -> account lookup tables (first match wins)."""
    by_domain, by_name = {}, {}
    for a in accounts:
        dom = sf_io.normalize_domain((a or {}).get("Website"))
        if dom and dom not in by_domain:
            by_domain[dom] = a
        nm = normalize_name((a or {}).get("Name"))
        if nm and nm not in by_name:
            by_name[nm] = a
    return by_domain, by_name


def _match(cand, by_domain, by_name):
    """Domain match first (most reliable), then exact normalized-name fallback."""
    dom = sf_io.normalize_domain(cand.get("domain"))
    if dom and dom in by_domain:
        return by_domain[dom]
    nm = normalize_name(cand.get("name"))
    if nm and nm in by_name:
        return by_name[nm]
    return None


def classify(candidates, accounts, territory_ids, target_user_id):
    """Return (kept, summary). See module docstring for the policy."""
    tids = set(territory_ids or [])
    by_domain, by_name = _index(accounts or [])
    kept, flagged = [], []
    excluded = {"own_or_territory": [], "customer": []}
    for c in candidates or []:
        acct = _match(c, by_domain, by_name)
        if acct is None:
            entry = dict(c); entry["sf_status"] = None
            kept.append(entry); continue
        owner_obj = acct.get("Owner")
        owner = owner_obj.get("Name") if isinstance(owner_obj, dict) else None
        atype = acct.get("Type")
        in_terr = bool(acct.get("OP_Territory__c")) and acct.get("OP_Territory__c") in tids
        owned = bool(target_user_id) and acct.get("OwnerId") == target_user_id
        if in_terr or owned:
            excluded["own_or_territory"].append(c.get("name")); continue
        if atype in HARD_EXCLUDE_TYPES:
            excluded["customer"].append(c.get("name")); continue
        entry = dict(c); entry["sf_status"] = {"owner": owner, "type": atype}
        kept.append(entry); flagged.append(c.get("name"))
    summary = {"kept": len(kept), "hard_excluded": excluded, "flagged": flagged}
    return kept, summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="find-accounts overlap-guard (own hard, others flagged).")
    ap.add_argument("candidates")
    ap.add_argument("sf_matches")
    ap.add_argument("--territory", required=True, help="boundary JSON from resolve_territory.py")
    ap.add_argument("--target-user", default="", help="target AE/ADM Salesforce UserId")
    ap.add_argument("--out", help="write annotated candidates JSON here (default: stdout)")
    a = ap.parse_args(argv)
    try:
        data = json.loads(pathlib.Path(a.candidates).read_text())
        boundary = json.loads(pathlib.Path(a.territory).read_text())
        raw_matches = json.loads(pathlib.Path(a.sf_matches).read_text())
    except (OSError, ValueError) as e:
        sys.exit(f"overlap-guard: could not read inputs: {e}")
    try:
        accounts = sf_io.parse_records(raw_matches)
    except sf_io.SalesforceResultError as e:
        sys.exit(f"overlap-guard: SF account-match result unusable: {e}")
    kept, summary = classify(data.get("candidates", []), accounts,
                             boundary.get("territory_ids", []), a.target_user)
    out_data = dict(data); out_data["candidates"] = kept
    payload = json.dumps(out_data, indent=2)
    if a.out:
        p = pathlib.Path(a.out); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(payload)
    else:
        print(payload)
    he = summary["hard_excluded"]
    print(f"overlap-guard: kept {summary['kept']} (hard-excluded "
          f"{len(he['own_or_territory'])} own/territory, {len(he['customer'])} customer; "
          f"flagged {len(summary['flagged'])} owned by others)", file=sys.stderr)


if __name__ == "__main__":
    main()
