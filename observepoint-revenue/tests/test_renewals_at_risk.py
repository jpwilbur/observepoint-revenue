import json
import pathlib

import renewals_at_risk as rar


NORM = [
    {"account": "Acme", "status": "Will Renew", "health": "Green",
     "arr": 1000, "currency": "USD", "close_date": "2026-07-01"},
    {"account": "Globex", "status": "Will Not Renew", "health": "Yellow",
     "arr": 500, "currency": "USD", "close_date": "2026-07-10"},
    {"account": "Initech", "status": "Will Not Renew", "health": "Green",
     "arr": 200, "currency": "GBP", "close_date": "2026-07-12"},
    {"account": "Umbrella", "status": "Undetermined", "health": "Red",
     "arr": 400, "currency": "USD", "close_date": "2026-07-20"},
    {"account": "Soylent", "status": "Undetermined", "health": "Yellow",
     "arr": 1000, "currency": "GBP", "close_date": "2026-07-22"},
]


def test_buckets_count_and_currency_split():
    r = rar.compute_from_normalized(NORM, today_iso="2026-06-26")
    s = r["summary"]
    assert s["will_renew"]["count"] == 1
    assert s["will_not_renew"]["count"] == 2
    assert s["will_not_renew"]["arr"] == {"USD": 500.0, "GBP": 200.0}
    assert s["undetermined"]["count"] == 2


def test_undetermined_is_risk_weighted_by_currency():
    r = rar.compute_from_normalized(NORM, today_iso="2026-06-26")
    # Red 400*0.25 = 100 USD; Yellow 1000*0.5 = 500 GBP
    assert r["summary"]["undetermined"]["risk_weighted"] == {"USD": 100.0, "GBP": 500.0}


def test_period_is_q2_fy26():
    r = rar.compute_from_normalized(NORM, today_iso="2026-06-26")
    assert r["period"]["quarter"] == "Q2" and r["period"]["fy_label"] == "FY26"


def test_green_but_will_not_renew_raises_a_caveat():
    r = rar.compute_from_normalized(NORM, today_iso="2026-06-26")
    assert any("Initech" in c and "Green" in c for c in r["caveats"])


def test_rows_sorted_by_arr_desc():
    r = rar.compute_from_normalized(NORM, today_iso="2026-06-26")
    arrs = [row["arr"] for row in r["will_not_renew_rows"]]
    assert arrs == sorted(arrs, reverse=True)


def test_normalize_sf_maps_nested_account_and_health_score():
    # SF now carries health via Account.Health_Score__c — normalize_sf_records extracts it.
    raw = [{"Account": {"Name": "Acme", "Health_Score__c": "5- Green"},
            "Renewal_Forecast__c": "Will Not Renew",
            "Renewable_ARR__c": 200, "CurrencyIsoCode": "GBP", "CloseDate": "2026-07-12"}]
    norm = rar.normalize_sf_records(raw)
    assert norm[0]["account"] == "Acme" and norm[0]["arr"] == 200
    assert norm[0]["currency"] == "GBP" and norm[0]["status"] == "Will Not Renew"
    assert norm[0]["health"] == "green"  # health_token normalizes "5- Green" -> "green"


def test_normalize_sf_health_none_when_field_absent():
    # When Health_Score__c is absent from the SF record, health should be None (not KeyError).
    raw = [{"Account": {"Name": "Bare"}, "Renewal_Forecast__c": "Will Renew",
            "Renewable_ARR__c": 100, "CurrencyIsoCode": "USD", "CloseDate": "2026-07-01"}]
    norm = rar.normalize_sf_records(raw)
    assert norm[0]["account"] == "Bare"
    assert norm[0]["health"] is None


def test_health_token_extracts_color_from_string():
    assert rar.health_token("Green") == "green"
    assert rar.health_token("Red - At Risk") == "red"
    assert rar.health_token("BLUE") == "blue"
    assert rar.health_token("") is None
    assert rar.health_token(None) is None


def test_health_token_sf_picklist_values():
    # Verify health_token handles the full SF picklist ("N- Color" format).
    assert rar.health_token("1- Black") == "black"
    assert rar.health_token("2- Red") == "red"
    assert rar.health_token("3- Yellow") == "yellow"
    assert rar.health_token("4- Blue") == "blue"
    assert rar.health_token("5- Green") == "green"


FIX = pathlib.Path(__file__).parent / "fixtures"


def test_end_to_end_render_from_sf_fixture_only():
    # Single SF gather — no Domo health file; health comes from Account.Health_Score__c.
    sf = json.loads((FIX / "sf" / "renewals_sample.json").read_text())
    result = rar.compute(sf, today_iso="2026-06-26")
    out = rar.render(result)
    assert "Renewals at Risk" in out
    assert "Will Not Renew" in out and "Undetermined" in out
    assert "var(--op-bg)" in out                      # branded page
    assert "despite a Green health score" in out      # caveat fired from the SF-health edge row
    # SF health on Umbrella (Red = 0.25 weight) drives risk-weighting
    assert result["summary"]["undetermined"]["risk_weighted"].get("USD") == 65500.0 * 0.25
