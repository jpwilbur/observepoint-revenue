import pytest
import sf_io


def test_parse_records_success_dict():
    assert sf_io.parse_records({"records": [{"Id": "1"}], "done": True, "totalSize": 1}) == [{"Id": "1"}]


def test_parse_records_list_passthrough():
    assert sf_io.parse_records([{"Id": "1"}]) == [{"Id": "1"}]


def test_parse_records_error_envelope_raises():
    with pytest.raises(sf_io.SalesforceResultError):
        sf_io.parse_records({"error": "Tool call timed out waiting for server response."})


def test_parse_records_missing_records_raises():
    with pytest.raises(sf_io.SalesforceResultError):
        sf_io.parse_records({"totalSize": 0, "done": True})


def test_parse_records_non_dict_raises():
    with pytest.raises(sf_io.SalesforceResultError):
        sf_io.parse_records("nope")


def test_normalize_domain_strips_scheme_www_path():
    assert sf_io.normalize_domain("https://www.Acme-Corp.com/path?q=1") == "acme-corp.com"


def test_normalize_domain_bare_host_and_port():
    assert sf_io.normalize_domain("Acme.com:443") == "acme.com"


def test_normalize_domain_keeps_subdomain():
    assert sf_io.normalize_domain("https://shop.acme.com") == "shop.acme.com"


def test_normalize_domain_empty_and_none():
    assert sf_io.normalize_domain("") == ""
    assert sf_io.normalize_domain(None) == ""
