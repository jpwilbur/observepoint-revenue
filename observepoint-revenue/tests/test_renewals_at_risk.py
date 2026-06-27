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


def test_normalize_sf_maps_nested_account_name_no_health():
    # SF does NOT carry health (confirmed in Plan 1 Task 5) — normalize_sf_records omits it.
    raw = [{"Account": {"Name": "Acme"}, "Renewal_Forecast__c": "Will Not Renew",
            "Renewable_ARR__c": 200, "CurrencyIsoCode": "GBP", "CloseDate": "2026-07-12"}]
    norm = rar.normalize_sf_records(raw)
    assert norm[0]["account"] == "Acme" and norm[0]["arr"] == 200
    assert norm[0]["currency"] == "GBP" and norm[0]["status"] == "Will Not Renew"
    assert "health" not in norm[0] or norm[0]["health"] is None


def test_health_token_extracts_color_from_string():
    assert rar.health_token("Green") == "green"
    assert rar.health_token("Red - At Risk") == "red"
    assert rar.health_token("BLUE") == "blue"
    assert rar.health_token("") is None
    assert rar.health_token(None) is None


def test_health_by_account_and_join():
    domo_health = [
        {"account_name": "Acme", "account_health_score": "Green", "days_in_current_health": 10},
        {"account_name": "Globex", "account_health_score": "Red - At Risk", "days_in_current_health": 5},
    ]
    hmap = rar.health_by_account(domo_health)
    assert hmap == {"acme": "green", "globex": "red"}
    sf_rows = [
        {"account": "Acme", "status": "Will Renew", "arr": 1, "currency": "USD", "close_date": "2026-07-01"},
        {"account": "Nomatch", "status": "Undetermined", "arr": 2, "currency": "USD", "close_date": "2026-07-01"},
    ]
    joined = rar.join_health(sf_rows, hmap)
    assert joined[0]["health"] == "green"
    assert joined[1]["health"] is None   # no Domo health for this account
