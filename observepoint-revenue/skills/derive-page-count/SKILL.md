---
name: derive-page-count
description: Use when determining how many real web pages a customer's domains have for ObservePoint contract scoping — driving the internal Site Census crawler to a defensible page-count range with a confidence level. Handles query-param spiral inflation, incomplete crawls, and cold starts. For multipliers and pricing use size-and-price; for the full end-to-end scope use scope-calculator.
---

# Derive Page Count

Produce a **narrow, defensible page-count range + anchor + confidence** for a customer's domains from the internal Site Census crawler. The number drives contract sizing: as large as is legitimately defensible, never inflated past what survives customer scrutiny — and **never fabricated.**

**REQUIRED READING before you produce a number:** `references/site-census-methodology.md` — the failure modes, the MCP tools, the range methodology (threshold sweep, incompleteness uplift, sanity ceiling), the output contract, and the Gallagher calibration. Do not derive a number without it.

## Procedure

1. **Admin safety.** `whoami` → if not in the central census account (default id 32527, configurable) `login_as_account` into it. Reads are immediate. For ANY write (create/start/update/delete): state the account + plan, get explicit go-ahead, `confirm_account_plan`, act, then `stop_impersonation` when done.
2. **Find the census.** `list_site_censuses({search:<customer surname/brand>})` (names are `[Rep][Rep] Customer`). One → proceed. Multiple → disambiguate with the user. None → **cold start** (step 3).
3. **Cold start (no usable census).** Do NOT invent a number. Report that none exists; offer to create + start one from the customer's domains (behind the write gate); tell the rep a fresh crawl takes hours-to-days and to return when it completes. Never block waiting.
4. **Size it.** `size_site_census({censusId})` at the default thresholds, then sweep (tighter 5000/1.3, default 10000/1.5, looser 20000/2.0). Read per-hostname URLs / paths / spiral flags and the three totals.
5. **Derive the range** per the reference: anchor = spiral-adjusted total; band from the sweep spread; HIGH gets the incompleteness uplift `urlsToVisit × pathFloor/visitedUrls`; clamp to the proportional sanity ceiling; round to ~2 sig figs; assign confidence.
6. **Emit the output contract** (`{rollup, per_domain[]}`) + the transparency line on discounted spirals. `size_site_census` only itemizes the top ~40 hostnames — on bigger accounts, add a single labeled **tail-aggregate row** so `per_domain` still sums to the anchor (see the reference; `url_samples` is best-effort and usually empty). Then offer to build the evidence workbook: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/derive-page-count/scripts/build_evidence_appendix.py <perdomain.json> <out.xlsx>`.

## The spiral-adjusted rule (do NOT improvise around it)

`defensible_pages` per domain = **paths for spiral-flagged domains, distinct URLs otherwise.** A domain is a spiral only when BOTH gates trip (overage > threshold AND ratio > threshold). You **substitute paths** for a spiral domain — you do **not** drop it, and you do **not** apply paths to non-spiral domains. The per-domain `defensible_pages` MUST sum to the rollup anchor.

## Red Flags — STOP

- About to quote the **raw URL total** as "the number" → never. Quote the spiral-adjusted anchor.
- No census exists and you're about to **estimate/placeholder a count** ("~10k mid-market") → STOP. Cold-start hand-off. Never fabricate.
- About to **exclude** a spiral domain entirely → no: substitute its paths (it still has real pages).
- About to add an **arbitrary headroom/buffer %** ("+20%", "+15% because incomplete") → no: the range comes from the threshold sweep + the incompleteness-uplift formula, not a made-up percentage.
- Crawl paused / under-crawled / suspect-zero and you're about to report a **final HIGH-confidence** number → it's a FLOOR; lower confidence and apply the uplift.

## Rationalizations — and the reality

| Rationalization | Reality |
|---|---|
| "No census yet, but the rep needs a number — I'll estimate ~10k." | A fabricated count is the failure this skill exists to prevent. Cold-start hand-off; come back when the crawl completes. |
| "That spiral domain isn't real pages — exclude it." | It has 761 real pages (its paths). Spiral-ADJUST (substitute paths), don't exclude. |
| "I'll add 20% headroom for safety / growth." | The range is data-driven (sweep + uplift + ceiling). Invented headroom is not defensible. |
| "Crawl's 96% done, I'll just buffer it up 15%." | Use `urlsToVisit × pathFloor/visitedUrls` for the uplift and lower confidence — not a guessed percent. |
| "The URL total is the biggest, most generous number." | It's query-param inflation. Quoting it dies under customer scrutiny. Anchor = spiral-adjusted. |
