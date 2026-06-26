"""Deterministic helpers for digesting Salesforce MCP results (read side).

The MODEL calls the Salesforce MCP (the gather step); this module only parses and
normalizes the JSON it returns (the compute step). Nothing here calls Salesforce.
Shared across SF-backed skills via the skills/salesforce-core/scripts sys.path entry
(tests) or a relative-path shim (runtime CLI).
"""
import re


class SalesforceResultError(ValueError):
    """An MCP result that isn't a usable SOQL/SOSL success envelope."""


def parse_records(mcp_result):
    """Return the records list from a soqlQuery/find result.

    Accepts the dict the MCP returns ({"records": [...], "done": true, ...}) or an
    already-extracted list. Raises SalesforceResultError on an error envelope or an
    unrecognized shape, so callers fall back cleanly instead of computing on garbage.
    """
    if isinstance(mcp_result, list):
        return mcp_result
    if not isinstance(mcp_result, dict):
        raise SalesforceResultError(f"expected dict or list, got {type(mcp_result).__name__}")
    if "error" in mcp_result:
        raise SalesforceResultError(str(mcp_result["error"]))
    recs = mcp_result.get("records")
    if not isinstance(recs, list):
        raise SalesforceResultError("no 'records' list — not a SOQL success envelope")
    return recs


_SCHEME = re.compile(r"^[a-z][a-z0-9+.\-]*://", re.I)


def normalize_domain(url_or_host):
    """Bare, comparable host for account matching.

    'https://www.Acme-Corp.com/path?q=1' -> 'acme-corp.com'. Lowercases; drops scheme,
    userinfo, leading 'www.', port, path/query/fragment, and surrounding dots/space.
    Returns '' for falsy/junk input (a candidate with no usable domain won't match by domain).
    """
    if not url_or_host:
        return ""
    s = str(url_or_host).strip().lower()
    s = _SCHEME.sub("", s)
    s = s.split("@")[-1]
    s = re.split(r"[/?#]", s, maxsplit=1)[0]
    s = s.split(":")[0]
    if s.startswith("www."):
        s = s[4:]
    return s.strip(". ")
