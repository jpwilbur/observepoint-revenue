---
name: owned-properties
description: Use when you need to discover all the web properties / domains an organization owns — "what domains does <org> own", "find their full web footprint", "map all their properties", "they don't know everything they own", before scoping an account. Produces a confirmable .xlsx inventory + a confirmed-domains list that feeds scope-calculator. For sizing/pricing a known domain set use scope-calculator; this finds the domains in the first place.
---

# Owned Properties

From an org name and/or a seed domain, discover the organization's **owned** web properties and
produce a confirmable inventory the customer can validate, plus a clean domain list for scoping.

The scripts do the bulky network work and rendering; you do the ownership judgment. Read first:
`${CLAUDE_PLUGIN_ROOT}/skills/owned-properties/references/discovery-methodology.md`.

> **Coverage ceiling — this is a floor, not an exhaustive list.** v1 completeness is **crt.sh +
> manual web research only**. An apex with no logged certificate is **invisible** to enumeration, and
> **reverse-WHOIS / passive-DNS is NOT implemented in v1**. So the `.xlsx` is **"a starting inventory
> for the customer to confirm and extend,"** not a guaranteed-complete footprint. Say this plainly in
> the chat summary, and make sure the workbook's Methodology sheet carries the same one-liner (see
> step 6). If `crt_status` is `unreachable` for an apex, that apex's enumeration is incomplete — flag
> it for re-run; don't present it as a complete 0-host apex.

Set `SKILL=${CLAUDE_PLUGIN_ROOT}/skills/owned-properties`.

## Workflow

1. **Seeds.** Take the seed domain(s) given, or find the org's primary domain via `WebSearch`.

2. **Enumerate each known apex** (deterministic; keeps thousands of subdomains out of your context).
   **Preflight:** before running, ensure a Python with `openpyxl` and the system `whois` binary are
   available (prefer `/opt/homebrew/bin/python3`); if `build_inventory.py` errors with
   ModuleNotFoundError, install the repo requirements first.
   ```bash
   python3 "$SKILL/scripts/discover_domains.py" <apex> /tmp/<apex>-hosts.json
   ```
   It prints a compact summary (registrable domain, WHOIS registrant, host_count, sample_hosts,
   `all_hosts_file`, and **`crt_status`**). Note the registrant — it confirms ownership of that apex.
   **Check `crt_status`:** `"ok"` means crt.sh answered (so `host_count: 0` is a genuine no-cert
   apex); **`"unreachable"`** means the crt.sh fetch failed after all retries, so a `host_count: 0`
   here is a LOST enumeration, not a real zero. If `crt_status` is `unreachable` for an apex, FLAG
   that apex in the workbook (Notes) and in chat as **"enumeration incomplete — re-run"** — do NOT
   report it as a complete 0-host apex, and do NOT pass its (missing) subdomains downstream.

3. **Find other owned registrable domains (the judgment crt.sh can't do)** via `WebSearch`/`WebFetch`:
   - SEC **10-K Exhibit 21** subsidiaries (public orgs); the org's **"our brands"/footer/family-of-
     companies** pages; acquisition press; Wikipedia/Crunchbase parent-child.
   - For each new owned apex you find, **run `discover_domains.py` on it too** to enumerate its hosts.

   **EDGAR Exhibit-21 recipe (worked).** Exhibit 21 of a 10-K is the company's list of subsidiaries —
   names, not domains, so you map each name to its primary domain.
   1. Hit EDGAR full-text search for the parent + the exhibit, e.g.
      `https://efts.sec.gov/LATEST/search-index?q=%22Exhibit+21%22&entityName=<Company>` — or just use
      the EDGAR full-text search UI at `https://efts.sec.gov/LATEST/search-index?q=...` /
      `https://www.sec.gov/cgi-bin/srqsb` → the **EDGAR full-text search** page
      (`https://efts.sec.gov` backs `https://www.sec.gov/cgi-bin/browse-edgar`; the human UI is at
      `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=<Company>&type=10-K`).
      Practical path: search `https://efts.sec.gov/LATEST/search-index?q="Exhibit 21"&forms=10-K` or
      open the **EDGAR full-text search UI** (`https://www.sec.gov` → Full-Text Search) and query
      `"<Company>" "subsidiaries of the registrant"`.
   2. Open the latest 10-K's **EX-21.1** attachment; read the subsidiary names.
   3. Map each subsidiary name → primary domain: `WebSearch` the exact legal name, prefer the result
      whose homepage **brand/footer names the parent** or whose WHOIS registrant matches; confirm with
      `discover_domains.py` (registrant) before marking `confirmed`. A name with no findable owned site
      → drop it (don't fabricate a domain).

   **Owned vs co-marketing decision rule (brand/footer pages).** A domain listed on the org's **own
   "our brands / family of companies / portfolio"** page = an **owned candidate** (verify, then
   classify). A domain that appears as a **partner / integration / "trusted by" / customer logo wall**
   = **NOT owned → `excluded`**. When unsure, demote to `possible` and leave it For-Review rather than
   confirming.

4. **Classify** each registrable domain: `confidence` (confirmed / likely / possible) + `type`
   (primary / subsidiary / brand / regional / microsite / other) + `evidence` + a real `source` URL.
   Put vendor/CDN/third-party domains in `excluded` — **observed ≠ owned**. Never invent a domain.

   **Redacted WHOIS is the GDPR norm — redaction ≠ not-owned.** A privacy-proxied / "REDACTED FOR
   PRIVACY" registrant means the WHOIS "confirm" signal simply won't fire; do not exile a legitimately
   owned domain to For-Review just for that. When the registrant is redacted, a **strong web-evidence
   match is sufficient to mark `confirmed`** — e.g. the domain is a named SEC Exhibit-21 subsidiary, or
   it's listed on the org's own brand/footer/family-of-companies page. (This is how the ObservePoint
   test case itself was handled.) Record that web evidence (with its source URL) as the `evidence`.

5. **Assemble the candidates JSON** (`/tmp/<org>-candidates.json`): `org`, `prepared_by`, `date`,
   `properties[]` (each: `registrable`, `type`, `confidence`, `evidence`, `source`, `host_count`,
   `sample_hosts`, and `all_hosts_file` from step 2 when available), and `excluded[]`.

6. **Render:**
   ```bash
   python3 "$SKILL/scripts/build_inventory.py" /tmp/<org>-candidates.json "<out>.xlsx"
   ```
   The `.xlsx` is the only file written; the script also **prints the confirmed registrable domains**
   to stdout (copy-pasteable into scope-calculator) — capture them for the summary. The workbook's
   **Methodology sheet auto-carries the coverage-ceiling one-liner** (floor-not-exhaustive; un-certed
   apexes invisible; reverse-WHOIS/passive-DNS not in v1).
   **Watch stderr for `WARNING: dropping property ...`** — the script validates every candidate and
   loudly drops any with a missing/empty `registrable`, a missing `source`, or a confidence that's
   missing (a `confidense`-style typo) or off-enum. A dropped **confirmed** row means a real owned
   domain just fell out of the feed: fix the candidates JSON and re-run rather than shipping short.
   **Output location (uniform across the plugin) — one folder per account:** default to
   `~/Documents/ObservePoint Revenue/Owned Properties/<Org>/` (rep override honored; `mkdir -p` first).
   Name the file `<Org> - owned properties.xlsx`.

7. **Summarize in chat:** # confirmed properties, # for-review, total hostnames under confirmed apexes,
   the `.xlsx` path, and the **confirmed domains list** (from the script's stdout) — note it's ready to
   paste into scope-calculator. **Also state the coverage caveat** (this is a floor, not exhaustive — a
   starting inventory for the customer to confirm and extend), **call out any apex flagged
   "enumeration incomplete — re-run"** (`crt_status: unreachable`), and **mention any dropped-property
   WARNINGs** the render emitted.

## Red flags — stop and fix

| Rationalization | Reality |
|---|---|
| "This domain is probably theirs, mark it confirmed." | Confirmed needs registrant / SEC / brand-page evidence. Else it's likely/possible → For Review sheet. |
| "Their site loads cdn.vendor.com, add it." | Observed ≠ owned. Vendor/CDN domains go in `excluded`. |
| "I'll add the likely ones to the confirmed feed too." | No. Only confirmed domains feed scoping; we don't scope on guesses. |
| "I'll list a domain I assume exists." | Never fabricate a domain. Every entry needs a real source. |
| "WHOIS is redacted, so I can't confirm it — For Review." | Redaction ≠ not-owned (it's the GDPR norm). A strong web match (SEC Exhibit-21, the org's own brand/footer page) confirms it. |
| "host_count is 0, so this apex has no subdomains." | Only if `crt_status` is `ok`. If `unreachable`, that's a LOST enumeration — flag "enumeration incomplete — re-run", don't report it as a complete 0. |
| "A partner/customer logo on their site means they own it." | A logo wall / integration / "trusted by" list is co-marketing, not ownership → `excluded`. Owned = on the org's own "our brands" page. |

## What this skill does not do (v1)
Auto-running Site Census/audits on the discovered domains (instead, hand the **confirmed-domains
list** — printed to stdout and carried on the Confirmed Properties sheet — to scope-calculator),
per-page analysis, reverse-WHOIS / passive-DNS enumeration, and continuous re-discovery.
