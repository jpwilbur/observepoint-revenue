---
name: scope-calculator
description: Use when a revenue or sales rep needs to size or price an ObservePoint contract for a prospect or customer — "scope this account", "how many pages do they need", "size a deal", "price out X", "build a usage proposal". Produces a usage + price breakdown plus a customer proposal and an evidence workbook.
---

# Scope Calculator

The single entry point reps use to scope an ObservePoint contract end to end. You **orchestrate two sub-skills** and assemble the deliverables — you do NOT do their work yourself.

## Flow

1. **Gather:** customer name, domain(s), use case (privacy / analytics / accessibility), and any regulations (CCPA, GDPR, …).
2. **Page count — invoke the `derive-page-count` skill.** It returns the `{rollup, per_domain}` object (defensible range + per-domain evidence). **Do NOT invent or estimate a page count yourself** — that skill owns it (spirals, cold starts, confidence).
3. **Usage + price — invoke the `size-and-price` skill**, feeding `page_count` = the SAME `rollup` low/anchor/high from step 2. **Do NOT improvise multipliers, cadence, or pricing yourself** — that skill owns them (regulation-based defaults, the cadence starting templates, the assumptions-to-verify list, and live pricing via the scripts). Let it run `fetch_pricing.py` + `compute_scope.py`.
4. **Assemble deliverables:**
   - **Evidence workbook:** `python3 ${CLAUDE_PLUGIN_ROOT}/skills/derive-page-count/scripts/build_evidence_appendix.py <perdomain.json> <customer>-evidence-appendix.xlsx` — fed the step-2 `{rollup, per_domain}`.
   - **Proposal:** `python3 ${CLAUDE_PLUGIN_ROOT}/skills/scope-calculator/scripts/build_proposal.py <proposal.json> <customer>-proposal.docx`. Assemble `proposal.json`: `page_universe` = the step-2 `rollup` (low/anchor/high/confidence); `scope` = a FLAT object you build from the step-3 `compute_scope` output — these are nested, so map explicitly: `predicted_scans`←`anchor.predicted_scans`, `purchased_scans`←`anchor.purchased_scans`, `buffer_pct`←`anchor.buffer_pct`, `tier`←`recommended_quote.tier`, `price_total`←`recommended_quote.price_total`; plus `customer`, `domains`, `regulations`, and a one-line `monitoring_summary`. (Keep internal terms out of `monitoring_summary` — the generator rejects them.)
   - Write both files to a **persistent, rep-accessible folder** (the current working directory or a clearly-named output folder — NOT a temp dir), and report their **absolute paths** alongside the rep-facing breakdown (from `size-and-price`, including the assumptions-to-verify list).

## The single-source consistency rule

There is **one** Part-1 object, and it feeds BOTH sides. The page-count anchor that goes into pricing (`page_count.anchor`), the anchor in the evidence appendix (`rollup.spiral_adjusted_anchor`), and the page-universe anchor in the proposal MUST be the **same number**. Never re-derive or re-state the anchor — pass the one object through.

Use the **precise** anchor everywhere (e.g. `95721`, not a rounded `96000`) — feeding a rounded anchor into pricing or the appendix breaks the sum-to-anchor invariant and the cross-deliverable match. Round **only** in customer-facing display text, never in the numbers you pass between steps.

## Red Flags — STOP

- About to estimate a page count yourself → invoke `derive-page-count` instead.
- About to pick multipliers / cadence / a price yourself → invoke `size-and-price` instead (its defaults, flags, and live pricing must apply; an improvised cadence or buffer is the failure).
- The proposal, the appendix, and the price show **different** anchor numbers → STOP; you re-derived instead of passing one object through.
- About to hand over only one deliverable → reps need the chat breakdown AND both files.
