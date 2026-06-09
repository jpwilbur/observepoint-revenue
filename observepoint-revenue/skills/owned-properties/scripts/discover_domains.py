"""Domain-footprint enumeration for owned-properties (free sources; deterministic; no LLM).

Given a seed apex, enumerate its hostnames via Certificate Transparency (crt.sh) and read the WHOIS
registrant. Dedupe/normalize, group by registrable domain (eTLD+1), return a COMPACT apex-level
summary; the full hostname list is written to a sidecar file so it never floods the agent's context.

Network I/O is injected (fetcher, whois_fn) so tests run offline. Optional paid reverse-WHOIS /
passive-DNS is a documented hook (see references/discovery-methodology.md) — a no-op without a key.

CLI:  discover_domains.py <apex> <out_hosts.json>   # writes hosts file, prints compact summary JSON
"""
import json
import pathlib
import subprocess
import sys
import time
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


def enumerate_crt(apex, fetcher=None):
    """All hostnames under `apex` (same registrable domain) seen in CT. Empty set on any failure."""
    fetcher = fetcher or _default_fetcher
    reg = registrable_domain(apex)
    # Refuse a bare public suffix / TLD as the seed (e.g. "co.uk", "com") — it would over-match every
    # unrelated domain under that suffix.
    if "." not in reg or reg in _MULTI_SUFFIXES:
        return set()
    url = "https://crt.sh/?q=" + urllib.parse.quote("%." + apex) + "&output=json"
    text = ""
    for attempt in range(CRT_ATTEMPTS):  # crt.sh is flaky (503/empty); retry transient failures
        try:
            text = fetcher(url)
        except Exception:
            text = ""
        if text:
            break
        if attempt < CRT_ATTEMPTS - 1:
            time.sleep(CRT_BACKOFF * (attempt + 1))
    return {h for h in parse_crt_json(text) if registrable_domain(h) == reg}


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
    hosts = sorted(enumerate_crt(apex, fetcher))
    registrant = whois_registrant(apex, whois_fn)
    sources = ["crt.sh"] + (["whois"] if registrant else [])
    summary = {
        "seed": apex, "registrable": registrable_domain(apex), "registrant": registrant,
        "host_count": len(hosts), "sample_hosts": hosts[:SAMPLE_CAP], "sources": sources,
    }
    return summary, hosts


def main(argv):
    if len(argv) < 3:
        sys.exit("usage: discover_domains.py <apex> <out_hosts.json>")
    summary, hosts = discover(argv[1])
    pathlib.Path(argv[2]).write_text(json.dumps(
        {"registrable": summary["registrable"], "all_hosts": hosts}, indent=2))
    summary["all_hosts_file"] = argv[2]
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main(sys.argv)
