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
