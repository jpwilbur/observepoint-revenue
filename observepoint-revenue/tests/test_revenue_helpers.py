import pytest
import currency
import periods
import risk_weight


def test_to_number_handles_currency_strings_blanks():
    assert currency.to_number("$1,234.50") == 1234.5
    assert currency.to_number(1000) == 1000.0
    assert currency.to_number("") is None
    assert currency.to_number(None) is None


def test_sum_by_currency_keeps_currencies_separate():
    rows = [
        {"arr": 79590, "currency": "USD"},
        {"arr": "1,000", "currency": "GBP"},
        {"arr": 410, "currency": "USD"},
        {"arr": None, "currency": "USD"},   # ignored
    ]
    assert currency.sum_by_currency(rows) == {"USD": 80000.0, "GBP": 1000.0}


def test_sum_by_currency_defaults_missing_currency_to_usd():
    assert currency.sum_by_currency([{"arr": 5}]) == {"USD": 5.0}


def test_format_money_symbols_and_fallback():
    assert currency.format_money(79590, "USD") == "$79,590"
    assert currency.format_money(1000, "GBP") == "£1,000"
    assert currency.format_money(1234, "SEK") == "1,234 SEK"
    assert currency.format_money(None) == "—"


def test_fiscal_quarter_feb_start_matches_screenshot():
    q = periods.fiscal_quarter("2026-05-01", fy_start_month=2)
    assert q == {"fy_label": "FY26", "quarter": "Q2",
                 "start": "2026-05-01", "end": "2026-07-31"}


def test_fiscal_quarter_january_belongs_to_prior_fy_q4():
    q = periods.fiscal_quarter("2027-01-15", fy_start_month=2)
    assert q["fy_label"] == "FY26" and q["quarter"] == "Q4"
    assert q["start"] == "2026-11-01" and q["end"] == "2027-01-31"


def test_in_window_inclusive_and_safe():
    assert periods.in_window("2026-07-31", "2026-05-01", "2026-07-31") is True
    assert periods.in_window("2026-08-01", "2026-05-01", "2026-07-31") is False
    assert periods.in_window("", "2026-05-01", "2026-07-31") is False


def test_risk_weighted_applies_health_weight():
    w = {"red": 0.25, "yellow": 0.5}
    assert risk_weight.risk_weighted(65500, "Red", w) == 16375.0
    assert risk_weight.risk_weighted(65200, "yellow", w) == 32600.0
    assert risk_weight.risk_weighted(100, "Green", w) == 0.0   # not in undetermined weights
    assert risk_weight.risk_weighted(None, "Red", w) == 0.0
