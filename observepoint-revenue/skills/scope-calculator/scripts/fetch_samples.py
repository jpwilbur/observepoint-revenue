"""Deterministically build + parse the `/v3/reports/grid/links` query for per-domain url_samples.

This module does NOT touch the network. The actual POST goes through the `op_api_call` MCP tool;
this builds the EXACT request body to paste into it and parses the LINK_URL values back out.
Moving the hand-authored grid filter JSON here removes the most error-prone manual step in Stage 1.

Two modes:
  - NORMAL (raw=False): isolate the host (`LINK_URL contains "//<hostname>"`) under one census and
    EXCLUDE the query-string spiral (`?`) and crawler/asset junk (`%22`, `.pdf`, `.jpg`) → clean
    real pages for the "Sample Pages" evidence.
  - RAW (raw=True): keep ONLY the SITE_CENSUS_ID + `//<hostname>` filters so the junk is NOT filtered
    and CAN be measured — feed this query's results to check_artifacts.py for the artifact check.

CLI:  fetch_samples.py <census_id> <hostname> [--raw]
      Prints build_query(...) as JSON so the rep/model pastes it into op_api_call, then parses the
      response with parse_samples().
"""
import json
import sys

# Junk excluded in NORMAL mode (negated string_contains on LINK_URL). See site-census-methodology.md.
_NORMAL_EXCLUSIONS = ("?", "%22", ".pdf", ".jpg")


def _contains(arg, negated):
    return {
        "operator": "string_contains",
        "filteredColumn": {"columnId": "LINK_URL"},
        "arg": arg,
        "wildcardStart": True,
        "wildcardEnd": True,
        "negated": negated,
    }


def build_query(census_id, hostname, raw=False):
    """Return the POST body for /v3/reports/grid/links.

    groupBy LINK_URL; SITE_CENSUS_ID integer_in [census_id]; LINK_URL contains "//<hostname>".
    NORMAL mode also negates-contains ?/%22/.pdf/.jpg. RAW mode keeps only the 2 base filters.
    """
    conditions = [
        {
            "operator": "integer_in",
            "filteredColumn": {"columnId": "SITE_CENSUS_ID"},
            "args": [int(census_id)],
            "negated": False,
        },
        _contains("//" + hostname, negated=False),
    ]
    if not raw:
        conditions += [_contains(arg, negated=True) for arg in _NORMAL_EXCLUSIONS]
    return {
        "columns": [{"columnId": "LINK_URL", "groupBy": True}],
        "filters": {
            "conditionMatchMode": "all",
            "conditions": conditions,
            "allAccounts": False,
        },
        "page": 0,
        "size": 10,
    }


def parse_samples(response_json):
    """Pull the LINK_URL values out of a grid response. Tolerates empty/missing → []."""
    if not response_json:
        return []
    rows = response_json.get("rows") or []
    return [r["LINK_URL"] for r in rows if isinstance(r, dict) and r.get("LINK_URL")]


def main(argv):
    if len(argv) < 3:
        sys.exit("usage: fetch_samples.py <census_id> <hostname> [--raw]")
    raw = "--raw" in argv[3:]
    print(json.dumps(build_query(argv[1], argv[2], raw=raw), indent=2))


if __name__ == "__main__":
    main(sys.argv)
