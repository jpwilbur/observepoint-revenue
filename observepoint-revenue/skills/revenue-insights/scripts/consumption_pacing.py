"""consumption-pacing recipe (CSM): OP page-scan usage text vs SF Subscription__c contracted
allowance -> over/on/under pacing view per account.

The MODEL runs the SF SOQL (lib/salesforce/salesforce-org.md "Contract / subscription") and calls
OP get_usage_overview for each account in the CSM's book; this script joins them and computes every
number. No SF/OP calls, no model math.
"""
import argparse
import datetime as _dt
import json
import pathlib
import re
import sys

_HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[3] / "lib" / "salesforce"))
import sf_io   # noqa: E402
import viz_kit  # noqa: E402  (same scripts dir)
import currency  # noqa: E402
import periods   # noqa: E402


# ---------------------------------------------------------------------------
# 1. parse_usage_overview — parse OP get_usage_overview formatted text
# ---------------------------------------------------------------------------

# Matches: "Audit Pages: 120,000 pages used (limit 200,000)"
# or:       "Audit Pages: 402,929 pages used (no contract limit)"
_RE_USED = re.compile(r"Audit Pages:\s*([\d,]+)\s*pages used", re.IGNORECASE)
_RE_LIMIT = re.compile(r"\(limit\s*([\d,]+)\)", re.IGNORECASE)
# Matches: "Contract: 2025-12-27 → 2026-12-27" (unicode arrow or ASCII ->)
_RE_CONTRACT = re.compile(
    r"Contract:\s*(\d{4}-\d{2}-\d{2})\s*[→\-]+>?\s*(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)


def parse_usage_overview(text: str) -> dict:
    """Parse OP get_usage_overview formatted text (not JSON) into a dict.

    Returns:
        {used: int|None, limit: int|None, contract_start: "YYYY-MM-DD"|None,
         contract_end: "YYYY-MM-DD"|None}

    "Audit Pages: N pages used" → used=N (strip commas).
    "(limit M)" → limit=M; "(no contract limit)" → limit=None.
    "Contract: A → B" → start/end (handles unicode → arrow).
    Junk/empty input → all-None.
    """
    used = limit = start = end = None
    if not text:
        return {"used": used, "limit": limit, "contract_start": start, "contract_end": end}

    m = _RE_USED.search(text)
    if m:
        used = int(m.group(1).replace(",", ""))

    m = _RE_LIMIT.search(text)
    if m:
        limit = int(m.group(1).replace(",", ""))
    # if "(no contract limit)" is present, limit stays None — correct by default

    m = _RE_CONTRACT.search(text)
    if m:
        start = m.group(1)
        end = m.group(2)

    return {"used": used, "limit": limit, "contract_start": start, "contract_end": end}


# ---------------------------------------------------------------------------
# 2. period_fraction — elapsed / total, clamped to [0, 1]
# ---------------------------------------------------------------------------

def _parse_date(s):
    if not s:
        return None
    try:
        return _dt.date.fromisoformat(str(s)[:10])
    except (ValueError, TypeError):
        return None


def period_fraction(start_iso: str, end_iso: str, today_iso: str):
    """Elapsed fraction of the contract window as of today, clamped to [0, 1].

    Bad/missing dates → None.
    """
    start = _parse_date(start_iso)
    end = _parse_date(end_iso)
    today = _parse_date(today_iso)
    if start is None or end is None or today is None:
        return None
    total = (end - start).days
    if total <= 0:
        return 1.0
    elapsed = (today - start).days
    return max(0.0, min(1.0, elapsed / total))


# ---------------------------------------------------------------------------
# 3. compute_from_normalized — core pacing math
# ---------------------------------------------------------------------------

def compute_from_normalized(rows: list, *, on_band: float = 0.1) -> dict:
    """Compute pacing status for pre-normalized rows.

    Each row must have:
        account          str
        used             int|None      (page scans consumed)
        contracted       float|None    (contracted page-scan allowance)
        period_fraction  float|None    (elapsed fraction of contract window)

    Returns:
        {"accounts": [{...row, "pace_pct": float|None, "status": str}, ...],
         "summary": {"over": n, "on": n, "under": n, "unknown": n}}

    status values: "over" | "on" | "under" | "unknown"
    """
    out_rows = []
    for r in rows:
        used = r.get("used")
        contracted = r.get("contracted")
        pf = r.get("period_fraction")

        # Guard: contracted and period_fraction must be usable, expected must be > 0
        if (used is None or contracted is None or pf is None
                or contracted == 0 or pf == 0):
            out_rows.append({**r, "pace_pct": None, "status": "unknown"})
            continue

        expected = contracted * pf
        if expected == 0:
            out_rows.append({**r, "pace_pct": None, "status": "unknown"})
            continue

        pace_pct = used / expected
        if pace_pct > 1 + on_band:
            status = "over"
        elif pace_pct < 1 - on_band:
            status = "under"
        else:
            status = "on"

        out_rows.append({**r, "pace_pct": pace_pct, "status": status})

    summary = {
        "over": sum(1 for r in out_rows if r["status"] == "over"),
        "on": sum(1 for r in out_rows if r["status"] == "on"),
        "under": sum(1 for r in out_rows if r["status"] == "under"),
        "unknown": sum(1 for r in out_rows if r["status"] == "unknown"),
    }
    return {"accounts": out_rows, "summary": summary}


# ---------------------------------------------------------------------------
# 4. compute — full pipeline: SF JSON + usage-text dict
# ---------------------------------------------------------------------------

def compute(contract_records: dict, usage_by_account: dict, *, today_iso: str) -> dict:
    """SF Subscription__c JSON + {account_name: usage_overview_text} -> pacing result.

    Filters to Active subscriptions only.
    Accounts with no usage text → used None → status "unknown".
    """
    records = sf_io.parse_records(contract_records)
    rows = []
    for rec in records:
        if str(rec.get("Status__c") or "").strip() != "Active":
            continue
        acct_node = rec.get("Account__r") or {}
        account = acct_node.get("Name") or rec.get("Account__r.Name")
        contracted = rec.get("Page_Scans_per_Month__c")
        # Contract window from SF (authoritative); fall back to OP text
        sf_start = rec.get("Subscription_Start_Date__c")
        sf_end = rec.get("Subscription_End_Date__c")

        usage_text = usage_by_account.get(account, "")
        parsed = parse_usage_overview(usage_text)

        # Prefer SF dates for the contract window
        start = sf_start or parsed["contract_start"]
        end = sf_end or parsed["contract_end"]
        used = parsed["used"]

        pf = period_fraction(start, end, today_iso)
        rows.append({
            "account": account,
            "used": used,
            "contracted": contracted,
            "period_fraction": pf,
        })

    return compute_from_normalized(rows)


# ---------------------------------------------------------------------------
# 5. render — branded HTML
# ---------------------------------------------------------------------------

_STATUS_COLORS = {
    "over": "red",
    "under": "yellow",
    "on": "green",
    "unknown": "black",
}


def _fmt_scans(n):
    """Format a page-scan count as a comma-separated integer, or em-dash."""
    if n is None:
        return "—"
    return f"{int(n):,}"


def _pace_str(pace_pct):
    if pace_pct is None:
        return "—"
    return f"{pace_pct * 100:.0f}%"


def render(result: dict) -> str:
    """Render the pacing result as branded HTML."""
    s = result["summary"]
    cards = '<div class="cards">' + "".join([
        viz_kit.stat_card("Over-Pacing", s["over"], "accounts above expected usage"),
        viz_kit.stat_card("On-Pace", s["on"], "accounts within ±10% of expected"),
        viz_kit.stat_card("Under-Pacing", s["under"], "accounts below expected usage"),
    ]) + "</div>"

    # Sort: over first, then under, then on, then unknown; within each, by used desc
    def _sort_key(r):
        order = {"over": 0, "under": 1, "on": 2, "unknown": 3}
        return (order.get(r["status"], 99), -(r.get("used") or 0))

    sorted_rows = sorted(result["accounts"], key=_sort_key)

    def _status_cell(r):
        tok = _STATUS_COLORS.get(r["status"], "black")
        c = viz_kit.HEALTH_COLORS.get(tok, viz_kit._T["muted"])
        lbl = r["status"].upper()
        return (f'<span class="hb"><span class="dot" style="background:{c}"></span>'
                f'{lbl}</span>')

    table = viz_kit.ranked_table(
        [
            ("ACCOUNT", "account"),
            ("USED (pages)", lambda r: _fmt_scans(r.get("used"))),
            ("CONTRACTED (pages)", lambda r: _fmt_scans(r.get("contracted"))),
            ("PACE%", lambda r: _pace_str(r.get("pace_pct"))),
            ("STATUS", _status_cell),
        ],
        sorted_rows,
    )

    body = (
        cards
        + viz_kit.section_header("Consumption Pacing — Page Scans")
        + table
        + viz_kit.caveats([
            "Contracted allowance from SF Subscription__c.Page_Scans_per_Month__c.",
            "Usage from OP get_usage_overview (parsed text). Over/on/under band ±10%.",
            "Accounts with no usage data show status: UNKNOWN.",
        ])
    )

    return viz_kit.page(
        "Consumption Pacing",
        body,
        kicker="CSM · page-scan usage vs contracted allowance",
        subtitle=(
            "Source: SF Subscription__c (allowance) · OP get_usage_overview (usage text) "
            "· pace = used ÷ (contracted × period fraction)"
        ),
    )


# ---------------------------------------------------------------------------
# 6. main
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="consumption-pacing recipe → branded HTML"
    )
    ap.add_argument("subscriptions_json", help="SF Subscription__c SOQL result JSON")
    ap.add_argument("--usage", required=True,
                    help="JSON file mapping account_name → usage_overview_text")
    ap.add_argument("--today", required=True, help="ISO date (YYYY-MM-DD)")
    ap.add_argument("--out", default="consumption-pacing.html", help="HTML output path")
    a = ap.parse_args(argv)

    sf_data = json.loads(pathlib.Path(a.subscriptions_json).read_text())
    usage_data = json.loads(pathlib.Path(a.usage).read_text())

    try:
        result = compute(sf_data, usage_data, today_iso=a.today)
    except sf_io.SalesforceResultError as e:
        sys.exit(f"SF subscription result unusable: {e}")

    out_path = pathlib.Path(a.out)
    out_path.write_text(render(result))
    print(out_path)


if __name__ == "__main__":
    main()
