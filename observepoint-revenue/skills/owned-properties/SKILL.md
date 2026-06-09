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
   python3 "$SKILL/scripts/build_inventory.py" /tmp/<org>-candidates.json "<out>.xlsx"
   ```
   The `.xlsx` is the only file written; the script also **prints the confirmed registrable domains**
   to stdout (copy-pasteable into scope-calculator) — capture them for the summary.
   **Output location (uniform across the plugin) — one folder per account:** default to
   `~/Documents/ObservePoint Revenue/Owned Properties/<Org>/` (rep override honored; `mkdir -p` first).
   Name the file `<Org> - owned properties.xlsx`.

7. **Summarize in chat:** # confirmed properties, # for-review, total hostnames under confirmed apexes,
   the `.xlsx` path, and the **confirmed domains list** (from the script's stdout) — note it's ready to
   paste into scope-calculator.

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
