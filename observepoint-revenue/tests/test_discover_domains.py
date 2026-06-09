import json

import discover_domains as dd

CRT_SAMPLE = json.dumps([
    {"name_value": "www.ajg.com\najg.com"},
    {"name_value": "*.ajg.com"},
    {"name_value": "jobs.ajg.com"},
    {"name_value": "mail.gallagherbassett.com"},   # different registrable -> filtered by enumerate
    {"name_value": "bad host.ajg.com"},             # whitespace -> dropped
    {"name_value": "abuse@ajg.com"},                # email -> dropped
])
WHOIS_SAMPLE = ("Domain Name: AJG.COM\n"
                "Registrant Organization: Arthur J. Gallagher & Co.\n"
                "Registrant Country: US\n")


def test_registrable_domain():
    assert dd.registrable_domain("jobs.ajg.com") == "ajg.com"
    assert dd.registrable_domain("ajg.com") == "ajg.com"
    assert dd.registrable_domain("a.b.c.example.com") == "example.com"
    assert dd.registrable_domain("www.shop.example.co.uk") == "example.co.uk"
    assert dd.registrable_domain("WWW.AJG.COM:443") == "ajg.com"
    assert dd.registrable_domain("localhost") == "localhost"   # single label -> returned as-is
    assert dd.registrable_domain("com") == "com"


def test_parse_crt_json_cleans():
    hosts = dd.parse_crt_json(CRT_SAMPLE)
    assert {"www.ajg.com", "ajg.com", "jobs.ajg.com", "mail.gallagherbassett.com"} <= hosts
    assert "*.ajg.com" not in hosts                       # wildcard stripped to ajg.com (already present)
    assert not any(" " in h or "@" in h for h in hosts)   # junk dropped


def test_parse_crt_json_bad_input():
    assert dd.parse_crt_json("not json") == set()
    assert dd.parse_crt_json("") == set()


def test_enumerate_crt_filters_to_apex():
    hosts = dd.enumerate_crt("ajg.com", fetcher=lambda url: CRT_SAMPLE)
    assert hosts == {"ajg.com", "www.ajg.com", "jobs.ajg.com"}  # gallagherbassett.com excluded


def test_enumerate_crt_network_failure_is_empty():
    def boom(url):
        raise RuntimeError("network down")
    assert dd.enumerate_crt("ajg.com", fetcher=boom) == set()


def test_enumerate_crt_refuses_bare_suffix_or_tld_apex():
    # A bare public suffix / TLD as the seed must not over-match every domain under it.
    assert dd.enumerate_crt("co.uk", fetcher=lambda url: CRT_SAMPLE) == set()
    assert dd.enumerate_crt("com", fetcher=lambda url: CRT_SAMPLE) == set()


def test_whois_registrant_parsed():
    r = dd.whois_registrant("ajg.com", whois_fn=lambda d: WHOIS_SAMPLE)
    assert r == {"org": "Arthur J. Gallagher & Co.", "source": "whois"}


def test_whois_registrant_redacted_is_none():
    r = dd.whois_registrant("x.com", whois_fn=lambda d: "Registrant Organization: REDACTED FOR PRIVACY\n")
    assert r is None


def test_discover_returns_summary_and_hosts():
    summary, hosts = dd.discover("ajg.com", fetcher=lambda url: CRT_SAMPLE, whois_fn=lambda d: WHOIS_SAMPLE)
    assert summary["registrable"] == "ajg.com"
    assert summary["host_count"] == 3
    assert len(hosts) == summary["host_count"]                 # count matches the list (contract)
    assert hosts == ["ajg.com", "jobs.ajg.com", "www.ajg.com"]  # sorted; second return value
    assert "all_hosts" not in summary                           # bulk list is NOT in the summary
    assert summary["registrant"]["org"].startswith("Arthur")
    assert "crt.sh" in summary["sources"] and "whois" in summary["sources"]


def test_cli_main_writes_hosts_and_compact_summary(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(dd, "_default_fetcher", lambda url: CRT_SAMPLE)
    monkeypatch.setattr(dd, "_default_whois", lambda d: WHOIS_SAMPLE)
    out = tmp_path / "hosts.json"
    dd.main(["discover_domains.py", "ajg.com", str(out)])
    summary = json.loads(capsys.readouterr().out)
    assert summary["host_count"] == 3
    assert summary["all_hosts_file"] == str(out)
    assert "all_hosts" not in summary                       # bulk list stays in the file
    saved = json.loads(out.read_text())
    assert saved["registrable"] == "ajg.com" and len(saved["all_hosts"]) == 3
