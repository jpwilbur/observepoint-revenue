# owned-properties Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `owned-properties` skill that, from an org name and/or seed domain, discovers the organization's owned web properties and produces a confirmable `.xlsx` inventory + a confirmed-domains feed for scope-calculator.

**Architecture:** Mirror the plugin's pattern — Claude gathers judgment-level evidence (brand/subsidiary web research) while deterministic scripts do the bulky network work and rendering. `discover_domains.py` enumerates a seed apex via Certificate Transparency (crt.sh) + WHOIS and returns a compact summary; `build_inventory.py` renders the candidates JSON into the workbook + `domains.txt`. Bulk hostname lists stay in files, not in the agent's context.

**Tech Stack:** Python 3 stdlib (`urllib`, `subprocess`), `openpyxl` (already a dep). No new dependencies — eTLD+1 uses a bundled PSL-lite; `whois` is the system CLI (`/usr/bin/whois`); network I/O is injected so tests run offline.

**Spec:** `docs/superpowers/specs/2026-06-09-owned-properties-design.md`

---

## File Structure

```
observepoint-revenue/
  skills/owned-properties/
    SKILL.md                         # orchestration (Task 3)
    scripts/
      discover_domains.py            # crt.sh + WHOIS enumeration, eTLD+1, dedup (Task 1)
      build_inventory.py             # candidates JSON -> .xlsx + domains.txt (Task 2)
    references/
      discovery-methodology.md       # source playbook + guardrails (Task 3)
  tests/
    conftest.py                      # MODIFY: add owned-properties/scripts to sys.path (Task 0)
    test_discover_domains.py         # (Task 1)
    test_build_inventory.py          # (Task 2)
  .claude-plugin/plugin.json         # MODIFY: 0.7.2 -> 0.8.0 (Task 4)
```

---

## Task 0: Scaffold + test path

**Files:** create dirs `skills/owned-properties/{scripts,references}`; modify `tests/conftest.py`.

- [ ] **Step 1: Create the directory tree**

Run (from `observepoint-revenue/`):
```bash
mkdir -p skills/owned-properties/scripts skills/owned-properties/references
```

- [ ] **Step 2: Add the new scripts dir to the test sys.path**

In `tests/conftest.py`, append `"skills/owned-properties/scripts"` to the `for rel in (...)` tuple so it reads:
```python
for rel in (
    "skills/size-and-price/scripts",
    "skills/derive-page-count/scripts",
    "skills/scope-calculator/scripts",
    "skills/research-account/scripts",
    "skills/owned-properties/scripts",
):
```

- [ ] **Step 3: Verify the existing suite still collects**

Run: `python3 -m pytest observepoint-revenue/tests -q`
Expected: 64 passed (no collection errors).

- [ ] **Step 4: Commit**
```bash
git add observepoint-revenue/tests/conftest.py
git commit -m "chore: scaffold owned-properties skill dir + test path"
```

---

## Task 1: `discover_domains.py` (TDD)

**Files:** Test `tests/test_discover_domains.py`; Create `skills/owned-properties/scripts/discover_domains.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_discover_domains.py`:
```python
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


def test_whois_registrant_parsed():
    r = dd.whois_registrant("ajg.com", whois_fn=lambda d: WHOIS_SAMPLE)
    assert r == {"org": "Arthur J. Gallagher & Co.", "source": "whois"}


def test_whois_registrant_redacted_is_none():
    r = dd.whois_registrant("x.com", whois_fn=lambda d: "Registrant Organization: REDACTED FOR PRIVACY\n")
    assert r is None


def test_discover_summary_shape():
    out = dd.discover("ajg.com", fetcher=lambda url: CRT_SAMPLE, whois_fn=lambda d: WHOIS_SAMPLE)
    assert out["registrable"] == "ajg.com"
    assert out["host_count"] == 3
    assert out["all_hosts"] == ["ajg.com", "jobs.ajg.com", "www.ajg.com"]   # sorted
    assert out["registrant"]["org"].startswith("Arthur")
    assert "crt.sh" in out["sources"] and "whois" in out["sources"]


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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest observepoint-revenue/tests/test_discover_domains.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'discover_domains'`.

- [ ] **Step 3: Write the implementation**

Create `skills/owned-properties/scripts/discover_domains.py`:
```python
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
SAMPLE_CAP = 25


def registrable_domain(host):
    host = (host or "").strip().strip(".").lower().split(":")[0]
    labels = [l for l in host.split(".") if l]
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
    url = "https://crt.sh/?q=" + urllib.parse.quote("%." + apex) + "&output=json"
    try:
        text = fetcher(url)
    except Exception:
        return set()
    reg = registrable_domain(apex)
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
    hosts = sorted(enumerate_crt(apex, fetcher))
    registrant = whois_registrant(apex, whois_fn)
    sources = ["crt.sh"] + (["whois"] if registrant else [])
    return {
        "seed": apex, "registrable": registrable_domain(apex), "registrant": registrant,
        "host_count": len(hosts), "sample_hosts": hosts[:SAMPLE_CAP],
        "all_hosts": hosts, "sources": sources,
    }


def main(argv):
    if len(argv) < 3:
        sys.exit("usage: discover_domains.py <apex> <out_hosts.json>")
    result = discover(argv[1])
    pathlib.Path(argv[2]).write_text(json.dumps(
        {"registrable": result["registrable"], "all_hosts": result["all_hosts"]}, indent=2))
    summary = {k: v for k, v in result.items() if k != "all_hosts"}
    summary["all_hosts_file"] = argv[2]
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main(sys.argv)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest observepoint-revenue/tests/test_discover_domains.py -q`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**
```bash
git add observepoint-revenue/tests/test_discover_domains.py observepoint-revenue/skills/owned-properties/scripts/discover_domains.py
git commit -m "feat: discover_domains.py — crt.sh + WHOIS enumeration, eTLD+1 grouping"
```

---

## Task 2: `build_inventory.py` (TDD)

**Files:** Test `tests/test_build_inventory.py`; Create `skills/owned-properties/scripts/build_inventory.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_build_inventory.py`:
```python
import json
import pathlib
import subprocess
import sys

import build_inventory as bi

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "owned-properties" / "scripts" / "build_inventory.py"

DATA = {
    "org": "Arthur J. Gallagher & Co.", "prepared_by": "Jarrod Wilbur", "date": "2026-06-09",
    "properties": [
        {"registrable": "ajg.com", "type": "primary", "confidence": "confirmed",
         "evidence": "Corporate primary; WHOIS registrant match.", "source": "https://ajg.com/",
         "host_count": 3, "sample_hosts": ["ajg.com", "www.ajg.com", "jobs.ajg.com"]},
        {"registrable": "gallagherbassett.com", "type": "subsidiary", "confidence": "confirmed",
         "evidence": "SEC 10-K Exhibit 21 subsidiary.", "source": "https://sec.gov/x",
         "host_count": 1, "sample_hosts": ["www.gallagherbassett.com"]},
        {"registrable": "ajginternational.com", "type": "regional", "confidence": "likely",
         "evidence": "Linked from ajg.com footer.", "source": "https://ajg.com/",
         "host_count": 0, "sample_hosts": []},
        {"registrable": "gallagher-maybe.com", "type": "other", "confidence": "possible",
         "evidence": "Similar branding, unconfirmed.", "source": "", "host_count": 0, "sample_hosts": []},
    ],
    "excluded": [{"domain": "cdn.cookielaw.org", "why": "OneTrust CMP vendor — third-party"}],
}


def _col1(ws):
    return [row[0] for row in ws.iter_rows(min_row=2, values_only=True) if row and row[0] is not None]


def _text(ws):
    return "\n".join(str(v) for row in ws.iter_rows(values_only=True) for v in row if v is not None)


def test_four_sheets():
    wb = bi.build_workbook(DATA)
    assert wb.sheetnames == ["Confirmed Properties", "For Review (unconfirmed)",
                             "All hostnames", "Methodology & sources"]


def test_confirmed_only_on_confirmed_sheet():
    wb = bi.build_workbook(DATA)
    assert _col1(wb["Confirmed Properties"]) == ["ajg.com", "gallagherbassett.com"]


def test_unconfirmed_only_on_review_sheet():
    wb = bi.build_workbook(DATA)
    assert _col1(wb["For Review (unconfirmed)"]) == ["ajginternational.com", "gallagher-maybe.com"]


def test_review_confidence_column():
    ws = bi.build_workbook(DATA)["For Review (unconfirmed)"]
    confs = [row[2] for row in ws.iter_rows(min_row=2, values_only=True)]
    assert confs == ["LIKELY", "POSSIBLE"]


def test_all_hostnames_from_confirmed_only():
    t = _text(bi.build_workbook(DATA)["All hostnames"])
    assert "jobs.ajg.com" in t and "www.gallagherbassett.com" in t


def test_methodology_lists_excluded():
    t = _text(bi.build_workbook(DATA)["Methodology & sources"])
    assert "cdn.cookielaw.org" in t and "third-party" in t


def test_confirmed_domains_feed_is_confirmed_only():
    assert bi.confirmed_domains(DATA) == ["ajg.com", "gallagherbassett.com"]


def test_cli_writes_xlsx_and_domains(tmp_path):
    f = tmp_path / "c.json"; f.write_text(json.dumps(DATA))
    xlsx = tmp_path / "out.xlsx"; dom = tmp_path / "domains.txt"
    res = subprocess.run([sys.executable, str(SCRIPT), str(f), str(xlsx), str(dom)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert xlsx.exists()
    assert dom.read_text().split() == ["ajg.com", "gallagherbassett.com"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest observepoint-revenue/tests/test_build_inventory.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'build_inventory'`.

- [ ] **Step 3: Write the implementation**

Create `skills/owned-properties/scripts/build_inventory.py`:
```python
"""Render an owned-properties inventory workbook (.xlsx) + a confirmed-domains feed (deterministic).

Input: a candidates JSON (org + properties[] each with registrable/type/confidence/evidence/source/
host_count/sample_hosts/[all_hosts_file] + an excluded[] list). Output: an editable .xlsx with four
sheets (Confirmed Properties / For Review (unconfirmed) / All hostnames / Methodology & sources) and
a domains.txt of CONFIRMED registrable domains only (we do not scope on guesses).

CLI:  build_inventory.py <candidates.json> <out.xlsx> <out_domains.txt>
"""
import json
import pathlib
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

DARK, GREEN, AMBER, GRAY = "1E1E1E", "27A567", "E8B500", "D9D9D9"
HDR_FONT = Font(bold=True, color="FFFFFF", size=11)
CHIP_FILL = {"likely": AMBER, "possible": GRAY}


def _headers(ws, headers):
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=i, value=h)
        c.font = HDR_FONT
        c.fill = PatternFill("solid", fgColor=DARK)
        c.alignment = Alignment(horizontal="left", vertical="center")


def _hyperlink(ws, row, col, url):
    if url:
        cell = ws.cell(row=row, column=col)
        cell.hyperlink = url
        cell.font = Font(color="0563C1", underline="single")  # explicit (avoid named-style dependency)


def _hosts_for(prop):
    f = prop.get("all_hosts_file")
    if f and pathlib.Path(f).exists():
        try:
            return json.loads(pathlib.Path(f).read_text()).get("all_hosts", [])
        except Exception:
            pass
    return prop.get("sample_hosts", []) or []


def build_workbook(data):
    props = data.get("properties", []) or []
    confirmed = [p for p in props if p.get("confidence") == "confirmed"]
    review = [p for p in props if p.get("confidence") in ("likely", "possible")]
    wb = Workbook()

    ws = wb.active
    ws.title = "Confirmed Properties"
    _headers(ws, ["Domain", "Type", "Evidence", "Source", "Subdomains found", "In scope?", "Notes"])
    for p in confirmed:
        ws.append([p.get("registrable", ""), p.get("type", ""), p.get("evidence", ""),
                   p.get("source", ""), p.get("host_count", 0), "", p.get("notes", "")])
        _hyperlink(ws, ws.max_row, 4, p.get("source"))

    ws2 = wb.create_sheet("For Review (unconfirmed)")
    _headers(ws2, ["Domain", "Type", "Confidence", "Why flagged", "Source",
                   "Subdomains found", "In scope?", "Notes"])
    for p in review:
        conf = p.get("confidence", "")
        ws2.append([p.get("registrable", ""), p.get("type", ""), conf.upper(),
                    p.get("evidence", ""), p.get("source", ""), p.get("host_count", 0), "",
                    p.get("notes", "")])
        chip = ws2.cell(row=ws2.max_row, column=3)
        chip.fill = PatternFill("solid", fgColor=CHIP_FILL.get(conf, GRAY))
        chip.font = Font(bold=True, color=("FFFFFF" if conf == "likely" else "1E1E1E"))
        _hyperlink(ws2, ws2.max_row, 5, p.get("source"))

    ws3 = wb.create_sheet("All hostnames")
    _headers(ws3, ["Hostname", "Registrable domain", "Source"])
    for p in confirmed:
        for h in _hosts_for(p):
            ws3.append([h, p.get("registrable", ""), "crt.sh"])

    ws4 = wb.create_sheet("Methodology & sources")
    for row in [
        ["How this footprint was built"],
        ["Certificate Transparency (crt.sh), WHOIS registrant, SEC 10-K Exhibit 21 subsidiaries, the "
         "org's own brand/footer pages, and (when keyed) reverse-WHOIS / passive-DNS."],
        [""],
        ["Confidence definitions"],
        ["confirmed — WHOIS registrant match, SEC Exhibit-21 subsidiary, listed on the org's own "
         "brand/footer page, or a subdomain of a confirmed apex."],
        ["likely — strong web evidence (acquisition / Crunchbase / Wikipedia parent), not registrant-confirmed."],
        ["possible — shared cert / similar branding, unconfirmed."],
        [""],
        ["Owned vs observed: vendor / CDN / third-party domains a site merely loads or links to are "
         "NOT owned and are excluded below."],
    ]:
        ws4.append(row)
    for d in data.get("excluded", []) or []:
        ws4.append([f"Excluded: {d.get('domain', '')} — {d.get('why', '')}"])

    for ws_ in wb.worksheets:
        for col in range(1, (ws_.max_column or 1) + 1):
            ws_.column_dimensions[get_column_letter(col)].width = 28
    return wb


def confirmed_domains(data):
    return sorted({p.get("registrable", "") for p in data.get("properties", []) or []
                   if p.get("confidence") == "confirmed" and p.get("registrable")})


def main(argv):
    if len(argv) < 4:
        sys.exit("usage: build_inventory.py <candidates.json> <out.xlsx> <out_domains.txt>")
    data = json.loads(pathlib.Path(argv[1]).read_text())
    build_workbook(data).save(argv[2])
    pathlib.Path(argv[3]).write_text("\n".join(confirmed_domains(data)) + "\n")
    print(argv[2])
    print(argv[3])


if __name__ == "__main__":
    main(sys.argv)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest observepoint-revenue/tests/test_build_inventory.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**
```bash
git add observepoint-revenue/tests/test_build_inventory.py observepoint-revenue/skills/owned-properties/scripts/build_inventory.py
git commit -m "feat: build_inventory.py — confirmable .xlsx (confirmed vs for-review) + confirmed domains.txt"
```

---

## Task 3: References + `SKILL.md`

**Files:** Create `skills/owned-properties/references/discovery-methodology.md` and `skills/owned-properties/SKILL.md`.

- [ ] **Step 1: Create `references/discovery-methodology.md`**

```markdown
# Owned-properties discovery methodology

A playbook for the `owned-properties` skill. Goal: the **complete set of web properties the org owns**,
each with evidence — never a guess presented as fact.

## Sources (free core)
- **Certificate Transparency (crt.sh)** — `discover_domains.py <apex>` returns every hostname seen on
  certs for that apex (subdomains + the apex). Run it on each owned apex you identify.
- **WHOIS registrant** — `discover_domains.py` reads the registrant org (a pivot + confirmation).
- **SEC 10-K Exhibit 21** ("Subsidiaries of the Registrant") — for public orgs, the authoritative
  subsidiary list (EDGAR full-text search). Map each subsidiary to its primary domain.
- **The org's own site** — "our brands" / "family of companies" / footer / regional-site links.
- **Acquisition press, Wikipedia "subsidiaries", Crunchbase** parent/child relationships.

## Optional paid (only if a key is set)
Reverse-WHOIS / passive-DNS (SecurityTrails / WhoisXML / DomainTools) give registrant-level ownership
and far better completeness. Wire via the documented env var; absent a key, the free path is used.
(Implementation is a future extension; the free path is the v1 default.)

## Confidence
- **confirmed** — WHOIS registrant match; SEC Exhibit-21 subsidiary; listed on the org's own
  brand/footer page; or a subdomain of a confirmed apex.
- **likely** — strong web evidence, not registrant-confirmed.
- **possible** — shared cert / similar branding, unconfirmed.

## Guardrails (non-negotiable)
- Every domain carries real evidence + a source URL. **Never fabricate a domain.**
- **Observed ≠ owned.** Vendor / CDN / martech / third-party domains a site merely loads or links to
  are NOT owned — put them in `excluded` with a reason, never in `properties`.
- Only **confirmed** domains feed `domains.txt` (downstream scoping). likely/possible go to the
  "For Review" sheet for the customer to confirm.
```

- [ ] **Step 2: Create `SKILL.md`**

````markdown
---
name: owned-properties
description: Use when you need to discover all the web properties / domains an organization owns — "what domains does <org> own", "find their full web footprint", "map all their properties", "they don't know everything they own", before scoping an account. Produces a confirmable .xlsx inventory + a confirmed-domains list that feeds scope-calculator. For sizing/pricing a known domain set use scope-calculator; this finds the domains in the first place.
---

# Owned Properties

From an org name and/or a seed domain, discover the organization's **owned** web properties and
produce a confirmable inventory the customer can validate, plus a clean domain list for scoping.

The scripts do the bulky network work and rendering; you do the ownership judgment. Read first:
`${CLAUDE_PLUGIN_ROOT}/skills/owned-properties/references/discovery-methodology.md`.

Set `SKILL=${CLAUDE_PLUGIN_ROOT}/skills/owned-properties`.

## Workflow

1. **Seeds.** Take the seed domain(s) given, or find the org's primary domain via `WebSearch`.

2. **Enumerate each known apex** (deterministic; keeps thousands of subdomains out of your context):
   ```bash
   python3 "$SKILL/scripts/discover_domains.py" <apex> /tmp/<apex>-hosts.json
   ```
   It prints a compact summary (registrable domain, WHOIS registrant, host_count, sample_hosts,
   `all_hosts_file`). Note the registrant — it confirms ownership of that apex.

3. **Find other owned registrable domains (the judgment crt.sh can't do)** via `WebSearch`/`WebFetch`:
   - SEC **10-K Exhibit 21** subsidiaries (public orgs); the org's **"our brands"/footer/family-of-
     companies** pages; acquisition press; Wikipedia/Crunchbase parent-child.
   - For each new owned apex you find, **run `discover_domains.py` on it too** to enumerate its hosts.

4. **Classify** each registrable domain: `confidence` (confirmed / likely / possible) + `type`
   (primary / subsidiary / brand / regional / microsite / other) + `evidence` + a real `source` URL.
   Put vendor/CDN/third-party domains in `excluded` — **observed ≠ owned**. Never invent a domain.

5. **Assemble the candidates JSON** (`/tmp/<org>-candidates.json`): `org`, `prepared_by`, `date`,
   `properties[]` (each: `registrable`, `type`, `confidence`, `evidence`, `source`, `host_count`,
   `sample_hosts`, and `all_hosts_file` from step 2 when available), and `excluded[]`.

6. **Render:**
   ```bash
   python3 "$SKILL/scripts/build_inventory.py" /tmp/<org>-candidates.json "<out>.xlsx" "<domains>.txt"
   ```
   **Output location (uniform across the plugin) — one folder per account:** default to
   `~/Documents/ObservePoint Revenue/Owned Properties/<Org>/` (rep override honored; `mkdir -p` first).
   Name them `<Org> - owned properties.xlsx` and `<Org> - domains.txt`.

7. **Summarize in chat:** # confirmed properties, # for-review, total hostnames under confirmed apexes,
   and the two output paths. Note that `domains.txt` (confirmed only) is ready for scope-calculator.

## Red flags — stop and fix

| Rationalization | Reality |
|---|---|
| "This domain is probably theirs, mark it confirmed." | Confirmed needs registrant / SEC / brand-page evidence. Else it's likely/possible → For Review sheet. |
| "Their site loads cdn.vendor.com, add it." | Observed ≠ owned. Vendor/CDN domains go in `excluded`. |
| "I'll put the likely ones in domains.txt too." | No. Only confirmed domains feed scoping; we don't scope on guesses. |
| "I'll list a domain I assume exists." | Never fabricate a domain. Every entry needs a real source. |

## What this skill does not do (v1)
Auto-running Site Census/audits on the discovered domains (hand `domains.txt` to scope-calculator),
per-page analysis, and continuous re-discovery.
````

- [ ] **Step 3: Sanity-check frontmatter + paths**

Run (from `observepoint-revenue/`):
```bash
python3 -c "import pathlib,re; t=pathlib.Path('skills/owned-properties/SKILL.md').read_text(); m=re.match(r'^---\n(.*?)\n---', t, re.S); assert m and 'name: owned-properties' in m.group(1) and 'description:' in m.group(1); print('frontmatter ok')"
test -f skills/owned-properties/references/discovery-methodology.md && echo "methodology ok"
```
Expected: `frontmatter ok` then `methodology ok`.

- [ ] **Step 4: Routing check (description quality)**

Dispatch a subagent given ONLY the five `observepoint-revenue` skill descriptions and the request
*"What domains does Arthur J. Gallagher own? Map their full web footprint."* — confirm it routes to
`owned-properties` (not scope-calculator/research-account). If it mis-routes, tighten the description.

- [ ] **Step 5: Commit**
```bash
git add observepoint-revenue/skills/owned-properties/SKILL.md observepoint-revenue/skills/owned-properties/references/discovery-methodology.md
git commit -m "feat: owned-properties SKILL.md + discovery methodology"
```

---

## Task 4: Full suite, version bump, final review

**Files:** Modify `.claude-plugin/plugin.json`; (check) `.claude-plugin/marketplace.json`.

- [ ] **Step 1: Run the entire suite**

Run: `python3 -m pytest observepoint-revenue/tests -q`
Expected: all pass (prior 64 + 9 discover + 8 inventory = 81).

- [ ] **Step 2: Bump the plugin version**

In `observepoint-revenue/.claude-plugin/plugin.json`, change `"version": "0.7.2"` → `"version": "0.8.0"`.
Optionally extend the `description` to mention owned-properties.

- [ ] **Step 3: Update ROADMAP**

In `docs/ROADMAP.md`, move **owned-properties** out of "▶ Next up" into a shipped note (or check it off).

- [ ] **Step 4: Smoke test (offline) — scripts end to end**

Run (from `observepoint-revenue/`):
```bash
python3 - <<'PY'
import json, pathlib, sys, tempfile
root = pathlib.Path('.').resolve()
sys.path.insert(0, str(root / 'skills/owned-properties/scripts'))
import build_inventory as bi
d = tempfile.mkdtemp()
data = {"org":"Demo Co","properties":[
  {"registrable":"demo.com","type":"primary","confidence":"confirmed","evidence":"WHOIS match","source":"https://demo.com/","host_count":2,"sample_hosts":["demo.com","www.demo.com"]},
  {"registrable":"demo-maybe.com","type":"other","confidence":"possible","evidence":"similar branding","source":"","host_count":0,"sample_hosts":[]}],
  "excluded":[{"domain":"cdn.vendor.com","why":"CDN — third-party"}]}
cj = pathlib.Path(d,'c.json'); cj.write_text(json.dumps(data))
x = pathlib.Path(d,'demo.xlsx'); t = pathlib.Path(d,'demo-domains.txt')
bi.build_workbook(data).save(str(x)); t.write_text("\n".join(bi.confirmed_domains(data)))
print('smoke ok ->', x.name, '| domains.txt:', t.read_text().split())
PY
```
Expected: `smoke ok -> demo.xlsx | domains.txt: ['demo.com']` (confirmed only).

- [ ] **Step 5: Plan self-review against the spec** — confirm each spec section maps to a task
  (§2 flow → Tasks 1-3; §4 contracts → Tasks 1-2; §5 sheets/feed → Task 2; §6 guardrails → SKILL +
  methodology; §8 cost-control → discover sidecar; §9 testing/version/PSL → Tasks 1,2,4). Fix gaps.

- [ ] **Step 6: Commit**
```bash
git add observepoint-revenue/.claude-plugin/ docs/ROADMAP.md
git commit -m "chore: bump observepoint-revenue to 0.8.0 (owned-properties skill)"
```

- [ ] **Step 7: (Optional) supervised live run** — with the user's go-ahead, run `owned-properties`
  on a real org (crt.sh + WHOIS are live, public, unauthenticated). Write output to the per-account
  folder; do not commit customer data.

---

## Self-Review (completed by plan author)
- **Spec coverage:** §1 goal → SKILL (Task 3); §2 iterative flow → discover (T1) + SKILL research loop
  (T3) + build (T2); §3 components → one task each; §4 contracts → T1 summary + T2 candidates JSON;
  §5 four sheets + confirmed-only domains.txt → T2 tests; §6 confidence/guardrails → SKILL red-flags +
  methodology; §7 out-of-scope → SKILL; §8 cost-control → discover writes hosts to a sidecar, summary
  omits `all_hosts`; §9 testing/version/PSL-lite → T1/T2/T4. No gaps.
- **Placeholder scan:** none — all code/tests/commands complete.
- **Type consistency:** `registrable_domain`/`parse_crt_json`/`enumerate_crt`/`whois_registrant`/
  `discover` signatures match across T1 impl + tests; the candidates-JSON property keys
  (`registrable`,`type`,`confidence`,`evidence`,`source`,`host_count`,`sample_hosts`,`all_hosts_file`)
  match across the spec §4, `build_inventory`/`confirmed_domains` (T2), and the SKILL assembly step.
```
