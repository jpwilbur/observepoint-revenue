"""TDD tests for consumption_pacing recipe (Plan 3 Task 3).

Parse + compute tests are deterministic and run without MCP calls.
today_iso = 2026-06-26 throughout.
"""
import consumption_pacing as cp


# ---------------------------------------------------------------------------
# 1. parse_usage_overview
# ---------------------------------------------------------------------------

_OVERVIEW_NO_LIMIT = """\
═══ Account Usage Overview ═══
Audit Pages: 402,929 pages used (no contract limit)
  Contract: 2025-12-27 → 2026-12-27
Journey Runs: 0 runs used (no contract limit)
Overages: Allowed"""

_OVERVIEW_WITH_LIMIT = """\
═══ Account Usage Overview ═══
Audit Pages: 120,000 pages used (limit 200,000)
  Contract: 2026-01-01 → 2026-12-31
Journey Runs: 5 runs used (no contract limit)
Overages: Not Allowed"""


def test_parse_no_limit_used_and_dates():
    r = cp.parse_usage_overview(_OVERVIEW_NO_LIMIT)
    assert r["used"] == 402929
    assert r["limit"] is None
    assert r["contract_start"] == "2025-12-27"
    assert r["contract_end"] == "2026-12-27"


def test_parse_with_limit():
    r = cp.parse_usage_overview(_OVERVIEW_WITH_LIMIT)
    assert r["used"] == 120000
    assert r["limit"] == 200000
    assert r["contract_start"] == "2026-01-01"
    assert r["contract_end"] == "2026-12-31"


def test_parse_junk_returns_all_none():
    r = cp.parse_usage_overview("nothing useful here")
    assert r == {"used": None, "limit": None, "contract_start": None, "contract_end": None}


def test_parse_empty_string_returns_all_none():
    r = cp.parse_usage_overview("")
    assert r == {"used": None, "limit": None, "contract_start": None, "contract_end": None}


# ---------------------------------------------------------------------------
# 2. period_fraction
# ---------------------------------------------------------------------------

def test_period_fraction_halfway():
    # Jan 1 start, Dec 31 end, today is Jul 1 ≈ half year
    pf = cp.period_fraction("2026-01-01", "2026-12-31", "2026-07-01")
    assert 0.49 < pf < 0.52


def test_period_fraction_clamped_to_zero():
    # today before start
    pf = cp.period_fraction("2026-06-01", "2026-12-31", "2026-01-01")
    assert pf == 0.0


def test_period_fraction_clamped_to_one():
    # today after end
    pf = cp.period_fraction("2026-01-01", "2026-06-01", "2026-12-31")
    assert pf == 1.0


def test_period_fraction_bad_dates_returns_none():
    assert cp.period_fraction(None, "2026-12-31", "2026-06-26") is None
    assert cp.period_fraction("bad", "2026-12-31", "2026-06-26") is None


# ---------------------------------------------------------------------------
# 3. compute_from_normalized
# ---------------------------------------------------------------------------

NORM = [
    # Acme: used 600k vs expected 500k → pace 1.2 → "over"
    {"account": "Acme", "used": 600_000, "contracted": 1_000_000, "period_fraction": 0.5},
    # Globex: used 400k vs expected 500k → pace 0.8 → "under"
    {"account": "Globex", "used": 400_000, "contracted": 1_000_000, "period_fraction": 0.5},
    # Initech: used 495k vs expected 500k → pace 0.99 → "on"
    {"account": "Initech", "used": 495_000, "contracted": 1_000_000, "period_fraction": 0.5},
    # Umbrella: no usage data
    {"account": "Umbrella", "used": None, "contracted": 1_000_000, "period_fraction": 0.5},
]


def test_acme_is_over():
    result = cp.compute_from_normalized(NORM)
    acme = next(r for r in result["accounts"] if r["account"] == "Acme")
    assert acme["status"] == "over"
    assert acme["pace_pct"] > 1.1


def test_globex_is_under():
    result = cp.compute_from_normalized(NORM)
    globex = next(r for r in result["accounts"] if r["account"] == "Globex")
    assert globex["status"] == "under"


def test_initech_is_on():
    result = cp.compute_from_normalized(NORM)
    initech = next(r for r in result["accounts"] if r["account"] == "Initech")
    assert initech["status"] == "on"


def test_umbrella_is_unknown():
    result = cp.compute_from_normalized(NORM)
    umbrella = next(r for r in result["accounts"] if r["account"] == "Umbrella")
    assert umbrella["status"] == "unknown"
    assert umbrella["pace_pct"] is None


def test_rollup_counts():
    result = cp.compute_from_normalized(NORM)
    s = result["summary"]
    assert s["over"] == 1
    assert s["under"] == 1
    assert s["on"] == 1
    assert s["unknown"] == 1


def test_no_period_fraction_gives_unknown():
    rows = [{"account": "X", "used": 100, "contracted": 1000, "period_fraction": None}]
    result = cp.compute_from_normalized(rows)
    assert result["accounts"][0]["status"] == "unknown"


def test_zero_contracted_gives_unknown():
    rows = [{"account": "X", "used": 100, "contracted": 0, "period_fraction": 0.5}]
    result = cp.compute_from_normalized(rows)
    assert result["accounts"][0]["status"] == "unknown"


# ---------------------------------------------------------------------------
# 4. compute (integration: SF JSON + usage text dict)
# ---------------------------------------------------------------------------

_SF_CONTRACT_RECORDS = {
    "totalSize": 4,
    "done": True,
    "records": [
        {
            "attributes": {"type": "Subscription__c"},
            "Account__r": {"Name": "Acme"},
            "Page_Scans_per_Month__c": 1_000_000,
            "Limit_Type__c": "Monthly",
            "Status__c": "Active",
            "App_Id__c": "acme-001",
            "Subscription_Start_Date__c": "2026-01-01",
            "Subscription_End_Date__c": "2026-12-31",
            "CurrencyIsoCode": "USD",
        },
        {
            "attributes": {"type": "Subscription__c"},
            "Account__r": {"Name": "Globex"},
            "Page_Scans_per_Month__c": 1_000_000,
            "Limit_Type__c": "Monthly",
            "Status__c": "Active",
            "App_Id__c": "globex-002",
            "Subscription_Start_Date__c": "2026-01-01",
            "Subscription_End_Date__c": "2026-12-31",
            "CurrencyIsoCode": "USD",
        },
        {
            "attributes": {"type": "Subscription__c"},
            "Account__r": {"Name": "Initech"},
            "Page_Scans_per_Month__c": 1_000_000,
            "Limit_Type__c": "Monthly",
            "Status__c": "Active",
            "App_Id__c": "initech-003",
            "Subscription_Start_Date__c": "2026-01-01",
            "Subscription_End_Date__c": "2026-12-31",
            "CurrencyIsoCode": "USD",
        },
        {
            # Expired — should be ignored
            "attributes": {"type": "Subscription__c"},
            "Account__r": {"Name": "OldCo"},
            "Page_Scans_per_Month__c": 500_000,
            "Limit_Type__c": "Monthly",
            "Status__c": "Expired",
            "App_Id__c": "oldco-004",
            "Subscription_Start_Date__c": "2025-01-01",
            "Subscription_End_Date__c": "2025-12-31",
            "CurrencyIsoCode": "USD",
        },
    ],
}

_USAGE_BY_ACCOUNT = {
    "Acme": "Audit Pages: 600,000 pages used (no contract limit)\n  Contract: 2026-01-01 → 2026-12-31",
    "Globex": "Audit Pages: 400,000 pages used (no contract limit)\n  Contract: 2026-01-01 → 2026-12-31",
    "Initech": "Audit Pages: 495,000 pages used (no contract limit)\n  Contract: 2026-01-01 → 2026-12-31",
}


def test_compute_filters_expired_sub():
    result = cp.compute(_SF_CONTRACT_RECORDS, _USAGE_BY_ACCOUNT, today_iso="2026-06-26")
    accounts = {r["account"] for r in result["accounts"]}
    assert "OldCo" not in accounts
    assert len(result["accounts"]) == 3


def test_compute_acme_over():
    result = cp.compute(_SF_CONTRACT_RECORDS, _USAGE_BY_ACCOUNT, today_iso="2026-06-26")
    acme = next(r for r in result["accounts"] if r["account"] == "Acme")
    assert acme["status"] == "over"


def test_compute_no_usage_text_gives_unknown():
    result = cp.compute(_SF_CONTRACT_RECORDS, {}, today_iso="2026-06-26")
    for row in result["accounts"]:
        assert row["status"] == "unknown"


# ---------------------------------------------------------------------------
# 5. render
# ---------------------------------------------------------------------------

def test_render_contains_title_and_bg():
    result = cp.compute_from_normalized(NORM)
    out = cp.render(result)
    assert "Consumption" in out
    assert "var(--op-bg)" in out


def test_render_has_account_names():
    result = cp.compute_from_normalized(NORM)
    out = cp.render(result)
    assert "Acme" in out
    assert "Globex" in out
