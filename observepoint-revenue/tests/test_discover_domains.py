import json
import socket
import urllib.error

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


def test_enumerate_crt_network_failure_is_empty(monkeypatch):
    monkeypatch.setattr(dd.time, "sleep", lambda s: None)   # don't actually wait between retries
    calls = {"n": 0}

    def boom(url):
        calls["n"] += 1
        raise RuntimeError("network down")
    assert dd.enumerate_crt("ajg.com", fetcher=boom) == set()
    assert calls["n"] == dd.CRT_ATTEMPTS                    # retried, not one-and-done


def test_enumerate_crt_retries_then_succeeds(monkeypatch):
    # crt.sh is flaky (503/empty); the first two attempts fail, the third returns data.
    monkeypatch.setattr(dd.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def flaky(url):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("503 Service Unavailable")
        return CRT_SAMPLE
    assert dd.enumerate_crt("ajg.com", fetcher=flaky) == {"ajg.com", "www.ajg.com", "jobs.ajg.com"}
    assert calls["n"] == 3


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


def test_discover_crt_status_unreachable_after_retries(monkeypatch):
    # FETCH-FAILED: crt.sh raises/returns empty after every retry. host_count is 0, but crt_status
    # must say "unreachable" so a silently-lost apex is distinguishable from a truly-zero one.
    monkeypatch.setattr(dd.time, "sleep", lambda s: None)

    def boom(url):
        raise RuntimeError("503 Service Unavailable")
    summary, hosts = dd.discover("ajg.com", fetcher=boom, whois_fn=lambda d: WHOIS_SAMPLE)
    assert summary["host_count"] == 0
    assert hosts == []
    assert summary["crt_status"] == "unreachable"


def test_discover_crt_status_unreachable_on_persistent_empty(monkeypatch):
    # Empty body (not an exception) on every attempt is also a fetch failure -> unreachable.
    monkeypatch.setattr(dd.time, "sleep", lambda s: None)
    summary, _ = dd.discover("ajg.com", fetcher=lambda url: "", whois_fn=lambda d: WHOIS_SAMPLE)
    assert summary["host_count"] == 0
    assert summary["crt_status"] == "unreachable"


def test_discover_crt_status_ok_when_truly_zero():
    # TRULY-ZERO: the fetch SUCCEEDED and returned a valid-but-empty cert list. crt_status is "ok"
    # with host_count 0 — a genuine no-cert apex, not a lost enumeration.
    summary, hosts = dd.discover("ajg.com", fetcher=lambda url: "[]", whois_fn=lambda d: WHOIS_SAMPLE)
    assert summary["host_count"] == 0
    assert hosts == []
    assert summary["crt_status"] == "ok"


def test_discover_crt_status_ok_with_hosts():
    summary, _ = dd.discover("ajg.com", fetcher=lambda url: CRT_SAMPLE, whois_fn=lambda d: WHOIS_SAMPLE)
    assert summary["host_count"] == 3
    assert summary["crt_status"] == "ok"


def test_discover_surfaces_blocked_status(monkeypatch):
    # A blocked CT fetch must surface crt_status "blocked" in the summary (host_count 0, but NOT a real 0).
    monkeypatch.setattr(dd.time, "sleep", lambda s: None)

    def blocked(url):
        raise urllib.error.HTTPError("https://crt.sh/", 403, "Forbidden", {}, None)

    summary, hosts = dd.discover("ajg.com", fetcher=blocked, whois_fn=lambda d: WHOIS_SAMPLE)
    assert summary["crt_status"] == "blocked"
    assert summary["host_count"] == 0
    assert hosts == []


def test_enumerate_crt_blocked_fails_fast(monkeypatch):
    # A policy block (e.g. 403 at the egress proxy) must NOT burn the retry budget: one call, then stop.
    monkeypatch.setattr(dd.time, "sleep", lambda s: (_ for _ in ()).throw(AssertionError("slept")))
    calls = {"n": 0}

    def blocked(url):
        calls["n"] += 1
        raise OSError("Tunnel connection failed: 403 Forbidden")

    hosts, status = dd.enumerate_crt_with_status("ajg.com", fetcher=blocked)
    assert hosts == set()
    assert status == "blocked"
    assert calls["n"] == 1                  # failed fast — did NOT retry CRT_ATTEMPTS times


def test_enumerate_crt_transient_still_retries_to_unreachable(monkeypatch):
    # A transient error keeps the existing behavior: retry CRT_ATTEMPTS times, end "unreachable".
    monkeypatch.setattr(dd.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def flaky(url):
        calls["n"] += 1
        raise RuntimeError("503 Service Unavailable")

    hosts, status = dd.enumerate_crt_with_status("ajg.com", fetcher=flaky)
    assert hosts == set()
    assert status == "unreachable"
    assert calls["n"] == dd.CRT_ATTEMPTS


def test_classify_fetch_error_blocked_signals():
    # Forbidden / proxy-auth-required / unavailable-for-legal-reasons HTTP codes are permanent here.
    for code in (403, 407, 451):
        err = urllib.error.HTTPError("https://crt.sh/", code, "blocked", {}, None)
        assert dd._classify_fetch_error(err) == "blocked"
    # Proxy rejects the CONNECT tunnel (the exact sandbox symptom), raw and URLError-wrapped:
    assert dd._classify_fetch_error(OSError("Tunnel connection failed: 403 Forbidden")) == "blocked"
    assert dd._classify_fetch_error(
        urllib.error.URLError(OSError("Tunnel connection failed: 403 Forbidden"))) == "blocked"
    # DNS blackholed at egress:
    assert dd._classify_fetch_error(
        urllib.error.URLError(socket.gaierror(8, "nodename nor servname provided, or not known"))) == "blocked"


def test_classify_fetch_error_transient_signals():
    assert dd._classify_fetch_error(
        urllib.error.HTTPError("https://crt.sh/", 503, "Service Unavailable", {}, None)) == "transient"
    assert dd._classify_fetch_error(RuntimeError("503 Service Unavailable")) == "transient"
    assert dd._classify_fetch_error(socket.timeout("timed out")) == "transient"
    assert dd._classify_fetch_error(ConnectionResetError("connection reset by peer")) == "transient"


def test_crt_url_builds_query():
    assert dd.crt_url("ajg.com") == "https://crt.sh/?q=%25.ajg.com&output=json"
    assert dd.crt_url("postholdings.com") == "https://crt.sh/?q=%25.postholdings.com&output=json"


def test_crt_url_refuses_bare_suffix_or_tld():
    assert dd.crt_url("co.uk") is None     # bare multi-label public suffix
    assert dd.crt_url("com") is None       # bare TLD


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
