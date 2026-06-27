import pipeline_coverage as pc

OPPS = [
    {"Amount": 100000, "CurrencyIsoCode": "USD", "ForecastCategoryName": "Commit",
     "StageName": "Negotiation", "IsClosed": False, "CloseDate": "2026-07-01",
     "Acquisition_Segment__c": "Sales", "Owner": {"Name": "Rep A"}},
    {"Amount": 50000, "CurrencyIsoCode": "USD", "ForecastCategoryName": "Best Case",
     "StageName": "Discovery", "IsClosed": False, "CloseDate": "2026-07-10",
     "Acquisition_Segment__c": "Sales", "Owner": {"Name": "Rep B"}},
    {"Amount": 999999, "CurrencyIsoCode": "USD", "ForecastCategoryName": "Closed",
     "StageName": "Closed Won", "IsClosed": True, "CloseDate": "2026-05-02",
     "Acquisition_Segment__c": "Sales", "Owner": {"Name": "Rep A"}},  # closed -> excluded from open pipeline
]
QUOTA = [
    {"Month_Quota__c": 50000, "Month_Start__c": "2026-05-01", "Type__c": "New ACV", "CurrencyIsoCode": "USD"},
    {"Month_Quota__c": 50000, "Month_Start__c": "2026-06-01", "Type__c": "New ACV", "CurrencyIsoCode": "USD"},
    {"Month_Quota__c": 50000, "Month_Start__c": "2026-07-01", "Type__c": "New ACV", "CurrencyIsoCode": "USD"},
    {"Month_Quota__c": 9999, "Month_Start__c": "2026-07-01", "Type__c": "MQL", "CurrencyIsoCode": "USD"},  # wrong type -> excluded
]


def test_open_pipeline_excludes_closed():
    r = pc.compute(OPPS, QUOTA, today_iso="2026-06-26")
    assert r["open_pipeline"]["USD"] == 150000.0   # 100k + 50k; the closed 999999 excluded


def test_quota_total_sums_in_window_and_type():
    r = pc.compute(OPPS, QUOTA, today_iso="2026-06-26")
    assert r["quota"]["USD"] == 150000.0           # 3x 50k New ACV; MQL excluded


def test_coverage_ratio_and_gap():
    r = pc.compute(OPPS, QUOTA, today_iso="2026-06-26")
    assert round(r["coverage_ratio"]["USD"], 2) == 1.0   # 150k pipeline / 150k quota
    assert r["gap_to_quota"]["USD"] == 0.0               # quota - committed/closed coverage (see canon)


def test_forecast_pacing_buckets():
    r = pc.compute(OPPS, QUOTA, today_iso="2026-06-26")
    assert r["forecast"]["Commit"]["USD"] == 100000.0
    assert r["forecast"]["Best Case"]["USD"] == 50000.0


def test_render_is_branded():
    out = pc.render(pc.compute(OPPS, QUOTA, today_iso="2026-06-26"))
    assert "Pipeline Coverage" in out and "var(--op-bg)" in out
