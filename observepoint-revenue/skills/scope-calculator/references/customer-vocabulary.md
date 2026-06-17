# Customer-facing vocabulary (scrub map)

Internal Site Census and pricing jargon must never appear in any customer-facing file — the
`<Customer> - Scope of Work.xlsx` workbook (tabs: Scope Detail / Scope of Work / Pricing / Sample
pages) that ships to the customer folder, or the `<Customer> - Proposal.docx` recompiled from the
AE-edited Scope of Work on request.
`scripts/customer_clean.py` enforces the forbidden list below; this doc is the human-readable map.
Anything internal lives in the separate internal-evidence workbook, which is pre-built into the
hidden `<customer>/.work/` subfolder (alongside the working scope_inputs / model / proposal /
internal JSONs) and is moved up to the customer folder only on explicit request — never auto-forwarded.

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
| budget / recommended contract / purchased scans | retired clean-$1000 back-solve pricing | (omit) — pricing now = exact graduated price of predicted scans |

## Approved Scope-of-Work vocabulary (cleared against FORBIDDEN)

These current labels are customer-safe — none contain a forbidden substring, so the
`customer_clean.py` guard passes them. Keep this list in sync with `customer_clean.FORBIDDEN`;
if you add or rename a label, re-check it against the forbidden list above.

| Label | Where it appears | Status |
|---|---|---|
| Baseline inventory | Recommended Cadence layer 1 (Yearly, 100%) | OK |
| High Priority | Recommended Cadence layer 2 (Weekly, 1.5%) | OK |
| Moderate Priority Pages | Recommended Cadence layer 3 (Monthly, 7.5%) | OK |
| Low Priority Pages | Recommended Cadence layer 4 (Quarterly, 20%) | OK |
| Buffer % | additive buffer line (combined x 15%, one pass) | OK |
| Recommended Cadence | cadence-ladder section heading | OK |
| Total Pages Found | Scope Detail SUMPRODUCT(Include?, Pages, Sample Size) | OK |
| Combined Page Total | combined-pages figure (formerly "use case pages") | OK |
| Scope of Work | workbook tab (formerly "Investment Model") | OK |
| Scope Detail | workbook tab (per-domain Include?/Sample Size levers) | OK |

Note: "Baseline inventory" contains the word "inventory" — this is NOT forbidden and is fine.
Nothing in the list collides with the banned substrings (census, spiral, raw url, defensible,
reduced/discount, query-param/string, crawl/recursion/collapsed, anchor, fallback).

**Caller contract:** the guard checks only agent-composed customer-facing strings (narrative,
cadence-layer names, "why" lines, property notes). Identity/factual fields (customer name, domains,
prepared_by, regulations) are never passed to it. The current cadence-layer names (Baseline
inventory, High Priority, Moderate Priority Pages, Low Priority Pages, Buffer %) and the workbook
labels (Scope of Work, Scope Detail, Total Pages Found, Combined Page Total, Recommended Cadence)
all clear the forbidden list — see the approved-vocabulary table above.
