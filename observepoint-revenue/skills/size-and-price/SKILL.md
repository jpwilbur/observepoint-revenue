---
name: size-and-price
description: Use when sizing ObservePoint annual page-scan usage and price from a known page count — applying geography, consent-scenario, and environment multipliers plus test-cadence layers, then pricing it. For the page count itself use derive-page-count; for the full end-to-end scope use scope-calculator.
---

# Size & Price

Turn a defensible page count into an **annual page-scan usage number and price**. You do NOT invent numbers and you do NOT do the arithmetic yourself — two scripts do the math, and ObservePoint's live pricing is the only source of truth.

**REQUIRED READING before you produce anything:**
- `references/usage-methodology.md` — multipliers, defaults, layered cadence, use-case profiles, the ask-the-customer map.
- `references/pricing-model.md` — graduated tiers, buffer, live fetch + fallback, the no-override rule.

## The one rule that matters

**Never invent a value, never block, never do the math in your head.** For any input you don't have, apply the labeled default from `usage-methodology.md` and add a line to an **"Assumptions to verify with the customer"** list. For pricing, run the script — never quote a $/page or $/scan rate from memory or from any old spreadsheet.

## Procedure

1. **Pick the use case** (privacy / analytics / accessibility) — seeds the multiplier + cadence defaults (`usage-methodology.md` §4).
2. **Set multipliers** — geographies, scenarios, environments — using the regulation-based defaults (CCPA→3, GDPR→2, else 1; prod+staging→1.5). Flag every defaulted one.
3. **Set cadence layers** — risk-framed ("how long can you tolerate an undetected issue?"), additive (`usage-methodology.md` §3–4).
4. **Fetch live pricing:** run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/size-and-price/scripts/fetch_pricing.py` → `{tiers, source}`.
5. **Compute:** assemble the inputs JSON (`page_count` low/anchor/high from derive-page-count, `multipliers`, `cadence_layers`, `buffer_pct`, plus the fetched `tiers` and `source`) and run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/size-and-price/scripts/compute_scope.py <inputs.json>`. The script returns the full breakdown — use its numbers verbatim.
6. **Present** the rep-facing breakdown (below).

## Output (rep-facing)

Report: each multiplier with its rationale (and whether it was defaulted); the cadence table; annual_scans range; **predicted vs purchased** (if a buffer); tier (starter/professional/enterprise); the live price-by-band breakdown + total range; the recommended quote (anchor); the implied-blended-frequency reconciliation note; the pricing **`source`** stamp; and the **"Assumptions to verify with the customer"** checklist. If `source` starts with `"fallback"`, add a visible "pricing may be stale — verify/refresh" warning.

## Red Flags — STOP

- About to state a $/page or $/scan rate, or a total price, that didn't come out of `compute_scope.py` → **STOP. Run the script.**
- About to apply a flat rate (e.g. the old $0.135) because the rep is "in a hurry" → **the live graduated price IS the quote.** Hand them the output to adjust themselves; there is no in-skill override.
- About to fill in geographies / scenarios / environments / cadence with a guess and move on → apply the labeled default and ADD IT to the assumptions-to-verify list instead.
- About to compute scans or price arithmetic yourself → the scripts do the math. You orchestrate.

## Rationalizations — and the reality

| Rationalization | Reality |
|---|---|
| "I'll estimate the rate; I know roughly what these tools cost." | Wrong every time. Run `fetch_pricing.py` + `compute_scope.py`. Live graduated tiers are the only truth. |
| "The rep's in a hurry — just use the flat $0.135." | That rate is dead. Quote the live graduated price; if they want bespoke pricing they edit the output. |
| "I don't know their geos/cadence, so I'll pick sensible numbers and bake them in." | Apply the labeled default AND flag it for verification. A baked-in guess presented as fact is the failure. |
| "CCPA is one state, so scenarios = 1." | No. CCPA → 3 consent-state scenarios (Default + Opt-Out + GPC). Use the regulation default. |
| "I'll just multiply pages × frequency in my head." | Use the layered cadence model via the script. No mental math. |
