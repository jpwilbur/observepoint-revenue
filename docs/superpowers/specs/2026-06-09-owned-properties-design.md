# Spec: `owned-properties` skill (domain-footprint discovery)

**Plugin:** `observepoint-revenue` (sibling of `scope-calculator`, `derive-page-count`,
`size-and-price`, `research-account`).
**Status:** approved design (built, v0.8.0). **Date:** 2026-06-09.

> **Amendment (v0.8.1):** the standalone `<Org> - domains.txt` file was dropped for output-folder
> cleanliness. The confirmed registrable domains now live only on the workbook's **Confirmed
> Properties** sheet and are **printed to stdout** by `build_inventory.py` (copy-pasteable into
> scope-calculator). Wherever this spec says a `domains.txt` file is written, read it as "the
> confirmed-domains list is printed." The CLI signature is `build_inventory.py <candidates.json>
> <out.xlsx>` (no third arg).

---

## 1. Goal & intent

Organizations routinely don't know every web property they own — subsidiaries, acquired brands,
regional ccTLD sites, campaign microsites. ObservePoint's tooling is URL-based (Site Census, audits,
scope-calculator, research-account all start from a domain), so an incomplete footprint means
under-scoping. `owned-properties` discovers the **complete owned-domain inventory** for an org and
produces a confirmable worksheet that (a) the rep walks the customer through ("is this everything?")
and (b) feeds straight into scope-calculator / derive-page-count.

**Inputs:** an org name and/or one or more seed domains; optional rep-supplied known domains (extra
seeds); optional paid-API key via environment (SecurityTrails / WhoisXML / DomainTools) — used only
if present.

**Success:** a deduped, categorized, evidence-tagged inventory of owned registrable domains (+ their
notable subdomains), each with an ownership-confidence tier and a real source, plus a plain domain
list ready for downstream scoping. No fabricated domains; observed ≠ owned.

---

## 2. Architecture & data flow

Mirrors the plugin's pattern — **Claude gathers judgment-level evidence → deterministic scripts do
the bulky/network work and rendering.** The heavy, voluminous data (Certificate-Transparency dumps,
passive-DNS, thousands of subdomains) stays inside scripts; Claude reasons at the **registrable-domain
/ brand** granularity (dozens of items), never shuttling thousands of subdomain rows through context
(the "agent-as-pipe" waste we avoid elsewhere).

The flow is **iterative** (discovery feeds research feeds discovery):

1. **Seed enumeration — `discover_domains.py`** (deterministic; network; no LLM). For each seed apex:
   - **crt.sh** (free Certificate Transparency): `https://crt.sh/?q=%25.<domain>&output=json` → all
     hostnames seen on certs for that domain. Reveals subdomains and sibling hosts.
   - **WHOIS** on the seed apex (`whois` CLI if available) → registrant org/email (a pivot + evidence).
   - **Optional paid** reverse-WHOIS / passive-DNS (only if an API key env var is set): registrant-level
     owned domains + historical DNS. Falls back silently to free when absent.
   - Output: dedup + normalize → group by **registrable domain** (eTLD+1) → **auto-classify every
     subdomain of a confirmed apex as owned (Confirmed)**. Returns a COMPACT apex-level summary
     (per registrable domain: host count, sample hosts, sources) written to a JSON file; the full
     hostname list is written to a sidecar the builder reads — it does not all flow through Claude.

2. **Brand/subsidiary research — Claude (SKILL body)** using `WebSearch`/`WebFetch`, for the
   registrable domains crt.sh can't infer (different eTLD+1s):
   - SEC **10-K Exhibit 21** "Subsidiaries of the Registrant" (EDGAR full-text search) for public orgs.
   - The org's own **"our brands" / "family of companies" / footer / regional-site** pages.
   - Acquisition press, Wikipedia "subsidiaries", Crunchbase parent/child.
   - For each newly-found brand/subsidiary, find its primary domain and **feed that apex back through
     `discover_domains.py`** (step 1) to enumerate its subdomains.
   - Claude assigns each registrable domain an **ownership-confidence tier + evidence + source URL**.

3. **Render — `build_inventory.py`** (deterministic). Takes the assembled candidates JSON →
   - an **editable `.xlsx`** (§5),
   - a plain **`<Org> - domains.txt`** of the **confirmed** apexes only, for scope-calculator.

---

## 3. Components & boundaries

| Component | Responsibility | Depends on |
|---|---|---|
| `SKILL.md` | Orchestrates: run `discover_domains.py` on seeds → brand/subsidiary web research → feed new apexes back → assemble candidates JSON → `build_inventory.py` → summarize. Owns the ownership-confidence judgment. | `WebSearch`, `WebFetch`, the two scripts |
| `scripts/discover_domains.py` | Per-apex enumeration: crt.sh + WHOIS + optional paid; dedup/normalize/group by eTLD+1; auto-classify subdomains of confirmed apexes. No LLM. | `urllib`/`requests`, `whois` CLI (optional), optional paid API key (env) |
| `scripts/build_inventory.py` | Render candidates JSON → editable `.xlsx` + `domains.txt`. No LLM, no network. | `openpyxl` |
| `references/discovery-methodology.md` | The source playbook (crt.sh query, SEC Exhibit-21 recipe, brand-page heuristics, the owned-vs-observed guardrail, paid-API env var names). | — |

Each script is independently testable (pure function of inputs; network mocked in tests).

---

## 4. Data contracts

### `discover_domains.py`
```
discover_domains.py <apex-domain> [--out <hosts.json>]   # prints a compact JSON summary to stdout
```
Returns / writes:
```json
{
  "seed": "ajg.com",
  "registrable": "ajg.com",
  "registrant": {"org": "Arthur J. Gallagher & Co.", "source": "whois"},   // null if unavailable
  "host_count": 412,
  "sample_hosts": ["www.ajg.com", "jobs.ajg.com", "..."],   // capped sample for the summary
  "all_hosts_file": "/tmp/ajg.com-hosts.json",              // full deduped list for the builder
  "sources": ["crt.sh", "whois"]                            // + "securitytrails" etc. when keyed
}
```

### Candidates JSON (Claude assembles → `build_inventory.py` input)
```json
{
  "org": "Arthur J. Gallagher & Co.",
  "prepared_by": "Jarrod Wilbur",
  "date": "2026-06-09",
  "properties": [
    {"registrable": "ajg.com", "type": "primary", "confidence": "confirmed",
     "evidence": "Corporate primary domain; WHOIS registrant 'Arthur J. Gallagher & Co.'",
     "source": "https://...", "host_count": 412,
     "sample_hosts": ["www.ajg.com", "jobs.ajg.com"]},
    {"registrable": "gallagherbassett.com", "type": "subsidiary", "confidence": "confirmed",
     "evidence": "Gallagher Bassett, wholly-owned subsidiary (SEC 10-K Exhibit 21).",
     "source": "https://www.sec.gov/...", "host_count": 88, "sample_hosts": ["..."]},
    {"registrable": "ajginternational.com", "type": "regional", "confidence": "likely",
     "evidence": "AJG International brand; linked from ajg.com footer.", "source": "https://ajg.com/", "host_count": 0}
  ],
  "excluded": [
    {"domain": "cdn.cookielaw.org", "why": "OneTrust CMP vendor — third-party, not owned"}
  ]
}
```
`type` ∈ {primary, subsidiary, brand, regional, microsite, other}. `confidence` ∈ {confirmed, likely,
possible}. `host_count`/`sample_hosts` come from `discover_domains.py` (0 when not enumerated).

**All-hostnames sheet source:** the builder reads each property's optional `all_hosts_file` (produced
by `discover_domains.py`) to populate the *All hostnames* sheet; if absent it falls back to that
property's `sample_hosts`.

---

## 5. Output `.xlsx` (editable; customer-confirmable)

Sheet **Confirmed Properties** — ONLY `confidence = confirmed` domains (the real owned set; these are
what feed downstream). One row per registrable domain:

| Domain | Type | Evidence | Source | Subdomains found | In scope? | Notes |

- "In scope?" is **empty/fillable** — the customer confirms.
- "Source" is a clickable hyperlink.

Sheet **For Review (unconfirmed)** — domains we found but could NOT confirm ownership of (`likely` and
`possible`), surfaced so the customer can confirm or reject them. Same columns **plus** a
**Confidence** column (likely=amber / possible=gray chip) and a **Why flagged** note. These are
deliberately kept OUT of the downstream feed — *we do not scope on guesses.*

Sheet **All hostnames** — every discovered host under the **confirmed** apexes, its registrable
domain, and source (the bulk list for the thorough reviewer).

Sheet **Methodology & sources** — how the footprint was built (crt.sh, WHOIS, SEC Exhibit 21, brand
pages, optional paid APIs), the confidence definitions, and the owned-vs-observed guardrail.

Plus **`<Org> - domains.txt`** — **confirmed registrable domains only**, one per line, ready to paste
into scope-calculator / derive-page-count. Likely/possible domains are intentionally excluded — they
stay in the *For Review* sheet until the customer confirms them.

**Output location** (uniform, per-account): `~/Documents/ObservePoint Revenue/Owned Properties/<Org>/`
→ `<Org> - owned properties.xlsx` + `<Org> - domains.txt`. Rep override honored; `mkdir -p` first.

---

## 6. Confidence model & guardrails (non-negotiable)

- **Confirmed:** WHOIS registrant match; SEC Exhibit-21 subsidiary; listed on the org's own
  brand/footer page; or a subdomain of a confirmed apex.
- **Likely:** strong web evidence (acquisition press, Crunchbase/Wikipedia parent) but not
  registrant-confirmed.
- **Possible:** shared cert / similar branding, unconfirmed.
- **Every domain carries real evidence + a source URL. No fabricated domains.**
- **Observed ≠ owned:** vendor/CDN/martech/third-party domains a site merely *loads or links to* are
  NOT owned — they go in `excluded` with a reason, never in `properties`. When ownership can't be
  evidenced, it's `possible` (flagged) or excluded, never `confirmed`.

---

## 7. Out of scope (v1)

Auto-running Site Census / audits on discovered domains (the rep hands `domains.txt` to
scope-calculator), per-page analysis, and continuous re-discovery/monitoring. Favicon-hash / analytics-ID
pivots and BuiltWith-style relationship graphs are deferred (optional future sources).

---

## 8. Cost control

- crt.sh / passive-DNS / subdomain volume is handled **inside `discover_domains.py`** — it returns an
  apex-level summary + a capped `sample_hosts`; the full list goes to a sidecar file the builder reads.
  Claude reasons over registrable domains/brands (dozens), not raw hostnames (thousands).
- crt.sh is queried once per apex with a timeout + a bounded result cap; failures degrade gracefully
  (apex still listed from web evidence, `host_count: 0`).
- Bound the brand-research breadth to a sensible cap (e.g. top subsidiaries/brands), logging anything
  intentionally skipped (no silent truncation).

---

## 9. Testing & housekeeping

- **`test_discover_domains.py`** — mock the crt.sh HTTP response + `whois`; assert dedup, normalization
  (lowercase, strip ports/wildcards), eTLD+1 grouping, subdomain→apex auto-classification, the compact
  summary shape, and graceful failure (network error → empty hosts, no crash). The optional-paid path
  is exercised only when a key is present (skipif).
- **`test_build_inventory.py`** — assert the four sheets (**Confirmed Properties**, **For Review
  (unconfirmed)**, **All hostnames**, **Methodology & sources**); that confirmed domains land ONLY on
  the Confirmed sheet and likely/possible land ONLY on the For Review sheet (with the Confidence
  chip); the empty "In scope?" column; clickable sources; `excluded` handling; and that `domains.txt`
  contains **confirmed apexes only** (no likely/possible).
- **`SKILL.md`** authored via the writing-skills TDD loop; trigger-only frontmatter (CSO-compliant),
  consistent with the other skills; red-flags table (no fabricated domains; observed≠owned; don't list
  vendor/CDN domains; classify confidence honestly).
- **Version:** bump `observepoint-revenue` `0.7.2 → 0.8.0` (new capability).
- **eTLD+1** grouping should use the Public Suffix List for correctness (e.g. `co.uk`). If a PSL lib
  isn't available, a bundled minimal suffix set + a documented fallback (last-two-labels) is acceptable
  for v1, noted in the methodology.
- No customer data committed (consistent with the gitignore).
