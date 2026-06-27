import json
import pathlib
import pytest
import domo_io

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "domo"


def test_parses_a_representative_envelope_into_row_dicts():
    # Use any one synthetic fixture authored in Task 3 (real envelope shape, fake values).
    fixtures = sorted(FIXTURES.glob("*.json"))
    assert fixtures, "no domo fixtures present (Task 3 should have authored them)"
    fixture = fixtures[0]
    rows = domo_io.parse_query_result(json.loads(fixture.read_text()))
    assert isinstance(rows, list)
    assert rows and isinstance(rows[0], dict)


def test_passthrough_list_of_dicts():
    rows = [{"a": 1}, {"a": 2}]
    assert domo_io.parse_query_result(rows) == rows


def test_columns_plus_rows_envelope_zips_to_dicts():
    env = {"columns": ["arr", "stage"], "rows": [[100, "Closed Won"], [200, "Commit"]]}
    assert domo_io.parse_query_result(env) == [
        {"arr": 100, "stage": "Closed Won"},
        {"arr": 200, "stage": "Commit"},
    ]


def test_error_envelope_raises():
    with pytest.raises(domo_io.DomoResultError):
        domo_io.parse_query_result({"error": "bad query"})


def test_unrecognized_shape_raises():
    with pytest.raises(domo_io.DomoResultError):
        domo_io.parse_query_result(42)


def test_coerce_number_handles_currency_strings_and_blanks():
    assert domo_io.coerce_number("$1,234.50") == 1234.5
    assert domo_io.coerce_number("") is None
    assert domo_io.coerce_number(None) is None
    assert domo_io.coerce_number("12%") == 12.0


def test_coerce_date_normalizes_to_iso():
    assert domo_io.coerce_date("2026-05-01T00:00:00") == "2026-05-01"
    assert domo_io.coerce_date("") is None


def test_list_of_non_dicts_raises():
    with pytest.raises(domo_io.DomoResultError):
        domo_io.parse_query_result([[1, 2], [3, 4]])


def test_empty_list_is_allowed():
    assert domo_io.parse_query_result([]) == []
