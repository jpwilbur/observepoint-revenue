"""Domain-footprint enumeration for owned-properties (free sources; deterministic; no LLM).

Given a seed apex, enumerate its hostnames via Certificate Transparency (crt.sh) and read the WHOIS
registrant. Dedupe/normalize, group by registrable domain (eTLD+1), return a COMPACT apex-level
summary; the full hostname list is written to a sidecar file so it never floods the agent's context.

Network I/O is injected (fetcher, whois_fn) so tests run offline. Optional paid reverse-WHOIS /
passive-DNS is a documented hook (see references/discovery-methodology.md) — a no-op without a key.

CLI:  discover_domains.py <apex> <out_hosts.json>   # writes hosts file, prints compact summary JSON
"""
import argparse
import json
import pathlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# eTLD+1 PSL-lite: two-label public suffixes. Extend as needed; PSL lib is a future upgrade.
_MULTI_SUFFIXES = {
    "co.uk", "org.uk", "gov.uk", "ac.uk", "me.uk", "ltd.uk", "plc.uk",
    "com.au", "net.au", "org.au", "edu.au", "gov.au",
    "co.jp", "or.jp", "ne.jp", "go.jp", "co.nz", "org.nz", "govt.nz",
    "co.za", "com.br", "com.mx", "com.ar", "com.sg", "com.hk", "com.tr", "com.cn",
    "co.in", "co.kr", "co.id", "com.my", "com.ph", "com.tw", "co.il", "com.sa", "com.eg",
}
SAMPLE_CAP = 25  # max hosts shown in the compact summary; the full list goes to the sidecar file
CRT_ATTEMPTS = 3  # crt.sh is frequently overloaded (503) — retry transient failures
CRT_BACKOFF = 2.0  # seconds; multiplied by attempt number between retries
# Fetch-failure signatures that mean a PERMANENT egress/policy block (retrying is futile) rather than
# crt.sh being flaky (503/timeout — worth a retry). Drives the "blocked" vs "unreachable" distinction.
_BLOCK_HTTP_CODES = {403, 407, 451}  # forbidden / proxy-auth-required / unavailable-for-legal-reasons
_BLOCK_PHRASES = (
    "tunnel connection failed",                         # urllib's exact string when a proxy 403s CONNECT
    "name or service not known", "nodename nor servname",  # DNS blackholed at the egress allowlist
    "temporary failure in name resolution",
)


def registrable_domain(host):
    host = (host or "").strip().strip(".").lower().split(":")[0]
    labels = [p for p in host.split(".") if p]
    if len(labels) < 2:
        return host
    last2 = ".".join(labels[-2:])
    if last2 in _MULTI_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return last2


def parse_crt_json(text):
    """crt.sh ?output=json -> a set of clean hostnames (wildcards stripped; emails/junk dropped)."""
    try:
        rows = json.loads(text or "[]")
    except (ValueError, TypeError):
        return set()
    hosts = set()
    for r in rows:
        nv = r.get("name_value", "") if isinstance(r, dict) else ""
        for name in str(nv).split("\n"):
            n = name.strip().lstrip("*.").lower()
            if n and " " not in n and "@" not in n and "." in n:
                hosts.add(n)
    return hosts


def crt_url(apex):
    """The crt.sh JSON URL for an apex, or None if the seed is a bare public suffix / TLD — which we
    refuse, because "%.com" would over-match every unrelated domain under that suffix."""
    reg = registrable_domain(apex)
    if "." not in reg or reg in _MULTI_SUFFIXES:
        return None
    return "https://crt.sh/?q=" + urllib.parse.quote("%." + apex) + "&output=json"


def _classify_fetch_error(exc):
    """'blocked' = a policy/egress block that will never clear on retry (403/407/451, a proxy CONNECT
    rejection, or a DNS blackhole); 'transient' = flaky/overloaded (503, timeout, reset) — retry.
    Unknown errors default to 'transient' so a retryable blip is never mistaken for a hard block."""
    if isinstance(exc, urllib.error.HTTPError) and exc.code in _BLOCK_HTTP_CODES:
        return "blocked"
    if isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, socket.gaierror):
        return "blocked"
    msg = str(getattr(exc, "reason", "") or exc).lower()
    if any(phrase in msg for phrase in _BLOCK_PHRASES):
        return "blocked"
    return "transient"


def _default_fetcher(url):
    req = urllib.request.Request(url, headers={"User-Agent": "observepoint-revenue/owned-properties"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def _default_whois(domain):
    try:
        out = subprocess.run(["whois", domain], capture_output=True, text=True, timeout=30)
        return out.stdout or ""
    except Exception:
        return ""


def enumerate_crt_with_status(apex, fetcher=None):
    """Like enumerate_crt, but ALSO reports whether crt.sh was reachable so callers can tell a
    FETCH-FAILED apex (lost subdomains) apart from a TRULY-ZERO one (no certs).

    Returns (hosts:set, crt_status:str) where crt_status is one of:
      - "ok"          a body came back (even if it parsed to 0 hosts — a genuine no-cert apex);
      - "blocked"     a PERMANENT egress/policy block (e.g. 403 at an allowlisting proxy); we fail
                      fast, so host_count:0 is a LOST enumeration, never a real zero;
      - "unreachable" every attempt raised/returned empty after all retries (crt.sh flaky/down).
    A refused seed (bare public suffix / TLD) is "unreachable" — we never queried crt.sh."""
    fetcher = fetcher or _default_fetcher
    reg = registrable_domain(apex)
    url = crt_url(apex)
    if url is None:  # bare public suffix / TLD seed — refused, never queried
        return set(), "unreachable"
    text = ""
    for attempt in range(CRT_ATTEMPTS):  # crt.sh is flaky (503/empty); retry transient failures
        try:
            text = fetcher(url)
        except Exception as exc:  # noqa: BLE001 - classify below: a policy block is permanent
            text = ""
            if _classify_fetch_error(exc) == "blocked":
                # Permanent egress/policy block (e.g. 403 at an allowlisting proxy). Retrying is
                # futile, so fail fast — and report "blocked" so host_count:0 isn't read as a real 0.
                return set(), "blocked"
        if text:
            break
        if attempt < CRT_ATTEMPTS - 1:
            time.sleep(CRT_BACKOFF * (attempt + 1))
    if not text:  # raised or empty on every attempt -> fetch failed, NOT a genuine zero
        return set(), "unreachable"
    return {h for h in parse_crt_json(text) if registrable_domain(h) == reg}, "ok"


def enumerate_crt(apex, fetcher=None):
    """All hostnames under `apex` (same registrable domain) seen in CT. Empty set on any failure."""
    hosts, _status = enumerate_crt_with_status(apex, fetcher)
    return hosts


def whois_registrant(domain, whois_fn=None):
    whois_fn = whois_fn or _default_whois
    text = whois_fn(domain) or ""
    org = name = None
    for line in text.splitlines():
        low = line.lower()
        if ":" not in line:
            continue
        val = line.split(":", 1)[1].strip()
        if not val or val.lower() in ("redacted for privacy", "redacted"):
            continue
        if org is None and "registrant organization" in low:
            org = val
        elif name is None and "registrant name" in low:
            name = val
    chosen = org or name
    return {"org": chosen, "source": "whois"} if chosen else None


def discover(apex, fetcher=None, whois_fn=None):
    """Returns (compact_summary, all_hosts). The bulk host list is the SECOND value so callers must
    opt into it explicitly — the summary alone is safe to hand to an LLM (no thousands of hostnames)."""
    host_set, crt_status = enumerate_crt_with_status(apex, fetcher)
    hosts = sorted(host_set)
    registrant = whois_registrant(apex, whois_fn)
    sources = ["crt.sh"] + (["whois"] if registrant else [])
    summary = {
        "seed": apex, "registrable": registrable_domain(apex), "registrant": registrant,
        "host_count": len(hosts), "sample_hosts": hosts[:SAMPLE_CAP], "sources": sources,
        # "ok" = crt.sh answered (0 hosts = genuinely no certs). "blocked" = permanent egress/policy
        # block; "unreachable" = flaky/down after retries. For BOTH non-ok states host_count:0 is a
        # LOST enumeration, not a real zero — flag the apex & recover via the two-step --crt-json path.
        "crt_status": crt_status,
    }
    return summary, hosts


def main(argv):
    ap = argparse.ArgumentParser(
        prog="discover_domains.py",
        description="Enumerate an apex's hostnames via Certificate Transparency (crt.sh) + WHOIS.")
    ap.add_argument("apex", nargs="?", help="seed apex, e.g. example.com")
    ap.add_argument("out_hosts", nargs="?", help="path to write the full hostnames JSON sidecar")
    ap.add_argument("--print-crt-url", action="store_true",
                    help="print the crt.sh URL for <apex> and exit; fetch it via your own egress, "
                         "then feed the saved JSON back with --crt-json")
    ap.add_argument("--crt-json", metavar="FILE",
                    help="parse a pre-fetched crt.sh JSON payload from FILE instead of the network "
                         "(use when direct egress to crt.sh is blocked)")
    args = ap.parse_args(argv[1:])

    if args.print_crt_url:
        if not args.apex:
            ap.error("--print-crt-url requires <apex>")
        url = crt_url(args.apex)
        if url is None:
            sys.exit(f"refusing bare public suffix / TLD as seed: {args.apex!r}")
        print(url)
        return

    if not args.apex or not args.out_hosts:
        ap.error("the following arguments are required: apex, out_hosts")

    fetcher = None
    if args.crt_json:
        try:
            crt_text = pathlib.Path(args.crt_json).read_text()
        except OSError as e:
            sys.exit(f"could not read --crt-json file {args.crt_json!r}: {e}")
        if not crt_text.strip():
            sys.exit(f"--crt-json file is empty: {args.crt_json!r} — fetch the URL from "
                     "--print-crt-url first, then pass the saved JSON here")
        fetcher = lambda _url: crt_text  # noqa: E731 - parse-only: feed the pre-fetched body, no net

    summary, hosts = discover(args.apex, fetcher=fetcher)
    pathlib.Path(args.out_hosts).write_text(json.dumps(
        {"registrable": summary["registrable"], "all_hosts": hosts}, indent=2))
    summary["all_hosts_file"] = args.out_hosts
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main(sys.argv)
