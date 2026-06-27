"""Deterministic helpers for digesting Domo MCP results (read side).

The MODEL calls the Domo MCP (gather); this module only parses/normalizes the JSON
it returns (compute). Nothing here calls Domo. Shared via the lib/domo sys.path entry
(tests) or a relative-path shim (runtime CLI). Mirrors lib/salesforce/sf_io.py.
"""
import re


class DomoResultError(ValueError):
    """A Domo MCP result that isn't a usable query-success envelope."""


def parse_query_result(mcp_result):
    """Return a list of row dicts from a DomoSqlQueryTool/FileSetQueryTool result.

    Handles the shapes Domo returns: an already-extracted list of dicts; a
    {"columns":[...], "rows":[[...], ...]} envelope (zipped to dicts); a nested
    {"data": <one of the above>} wrapper. Raises DomoResultError on an error envelope
    or unrecognized shape so callers fall back cleanly instead of computing on garbage.
    """
    if isinstance(mcp_result, list):
        if not mcp_result or isinstance(mcp_result[0], dict):
            return mcp_result
        raise DomoResultError("list envelope must contain row dicts")
    if not isinstance(mcp_result, dict):
        raise DomoResultError(f"expected dict or list, got {type(mcp_result).__name__}")
    if "error" in mcp_result:
        raise DomoResultError(str(mcp_result["error"]))
    if "data" in mcp_result:
        return parse_query_result(mcp_result["data"])
    rows = mcp_result.get("rows")
    cols = mcp_result.get("columns")
    if isinstance(rows, list):
        if cols and rows and isinstance(rows[0], (list, tuple)):
            names = [c if isinstance(c, str) else c.get("name") for c in cols]
            return [dict(zip(names, r)) for r in rows]
        if all(isinstance(r, dict) for r in rows):
            return rows
    raise DomoResultError("no usable rows — not a Domo query-success envelope")


_NUM = re.compile(r"[^0-9.\-]")


def coerce_number(value):
    """Best-effort float from a number or a currency/percent string. '' / None -> None."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = _NUM.sub("", str(value))
    if cleaned in ("", "-", ".", "-."):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def coerce_date(value):
    """ISO YYYY-MM-DD from a date or ISO-ish datetime string. '' / None -> None."""
    if not value:
        return None
    return str(value).strip()[:10]
