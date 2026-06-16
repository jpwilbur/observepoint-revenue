# Customer-facing vocabulary (scrub map)

Internal Site Census and pricing jargon must never appear in a customer-facing `.docx` or `.xlsx`.
`scripts/customer_clean.py` enforces the forbidden list below; this doc is the human-readable map.
Anything internal lives in the separate internal-evidence workbook, never forwarded.

| Internal term | Why it's internal | Customer-facing wording |
|---|---|---|
| site census / census | internal crawler + its IDs | (omit) "your website footprint" |
| spiral / spiral-adjusted | query-param de-duplication mechanic | (omit) — just report "pages" |
| raw url / raw URLs | pre-reduction crawl count | "pages" (the clean number) |
| defensible / indefensible | internal defensibility framing | "pages" |
| reduced / discount / discounted | the delta we removed | (omit) — show only the clean count |
| query-param / query-string | the duplication source | (omit) |
| crawl / recursion / collapsed | crawler internals + recursion-trap handling | (omit) — internal file only |
| anchor | internal point-estimate label | "estimated footprint" |
| fallback | pricing-source staleness flag | (omit) — internal file only |

**Caller contract:** the guard checks only agent-composed customer-facing strings (narrative,
cadence-layer names, "why" lines, property notes). Identity/factual fields (customer name, domains,
prepared_by, regulations) are never passed to it.
