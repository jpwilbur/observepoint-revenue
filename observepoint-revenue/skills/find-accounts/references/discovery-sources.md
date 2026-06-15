# Discovery sweep — sources & rules

You are scouting NEW accounts for the rep's territory. You do not deep-research them here; you
surface qualified candidates that then go through research-account. Every judgment below is yours;
the script only ranks and de-duplicates what you give it.

## Territory is a hard boundary

Only surface companies inside the rep's stated territory (region and, if specified, verticals). A
great ICP fit outside the territory belongs to a different AE — leave it out. **When in doubt
whether a company is in-territory, leave it out.**

## What makes a strong candidate

ObservePoint's ideal customer is a large, regulated enterprise with a complex web presence and
active privacy/compliance pressure. The highest-signal candidates have a recent, specific trigger,
in roughly this order:

1. Named in a recent CIPA / state-wiretap class action, demand letter, or settlement (highest).
2. Recent FTC / HHS OCR / CPPA / state-AG privacy enforcement action or consent order.
3. A publicly reported privacy incident or client-side breach (Magecart, rogue tag).
4. New privacy/compliance leadership or a wave of privacy/analytics-governance hiring.

Tag each candidate with the single best `triggerKey` from
`../../research-account/references/scoring-config.json` (`whyNow` keys — the shared taxonomy; an
unknown key is a script error). Triggers need a genuine **web-tracking nexus** — no BIPA-only,
generic breach, antitrust, or product-safety stretches (same discipline as research-account).
Quick ICP sanity per candidate: enterprise scale, complex web estate, in a `targetVerticals`
vertical (same file).

## Source-priority order (sweep highest-signal first)

Spend your search budget top-down; a hit high on this list outranks several lower ones:

1. **Active pixel/wiretap litigation** — CIPA, state wiretap, VPPA video-pixel, session-replay
   suits filed or amended recently. Highest signal: a live tracking nexus, already public.
2. **Enforcement actions** — FTC / HHS OCR / CPPA / state-AG actions, consent orders, settlements
   on tracking, consent, or data sharing.
3. **Client-side breaches with a tracking nexus** — Magecart / web-skimming / rogue-tag / supply-
   chain-script incidents (not generic data breaches with no client-side angle).
4. **Leadership / hiring signals** — new CPO / GC / VP MarTech / VP Analytics; waves of privacy or
   analytics-governance job postings. Weakest of the four; corroborate with one of the above.

## Query templates (copyable — fill the <brackets>)

Use `WebSearch` for these; use `WebFetch` only to read a specific promising result. Swap `2026`
for the current/prior year and `<region>`/`<state>`/`<company>` for your territory. Date-range
operators (`2025..2026`) narrow to recent events.

**Pixel / wiretap litigation**
- `site:classaction.org "<region>" CIPA pixel 2026`
- `site:topclassactions.com CIPA "pen register" "<state>" 2025..2026`
- `"<state>" CIPA wiretap class action "Meta Pixel" OR "TikTok pixel" 2026`
- `VPPA "video privacy" class action "<region>" 2025..2026`
- `"session replay" OR "chat intercept" wiretap class action "<state>" 2026`

**Enforcement actions**
- `"<state> attorney general" privacy settlement 2026`
- `site:ftc.gov press release tracking OR pixel OR "data sharing" 2025..2026`
- `site:hhs.gov OCR "tracking technologies" hospital pixel 2025..2026`
- `"CPPA" enforcement OR "consent order" 2026`

**Healthcare patient-portal pixels (OCR / HHS)**
- `"<region>" hospital "patient portal" Meta Pixel disclosure 2025..2026`
- `health system "tracking technologies" HHS OCR breach 2026`

**Client-side breach / rogue tag**
- `"<company>" Magecart OR web-skimming OR "malicious script" 2025..2026`
- `"<region>" e-commerce "card skimming" client-side script 2026`

**Corporate / M&A / leadership (corroborating)**
- `"<company>" 8-K acquisition 2025..2026`
- `"<company>" hires "Chief Privacy Officer" OR "VP Marketing Technology" 2026`
- `"<region>" "<vertical>" hiring "privacy program" OR "analytics governance" 2026`

## Named sources to scan (public only)

- Litigation: ClassAction.org, Top Class Actions, Law360, Bloomberg Law, LawStreetMedia; the Duane
  Morris class-action review; DLA Piper / Davis Polk / Gibson Dunn / Baker McKenzie
  privacy-litigation reports; PACER coverage of CIPA (Cal. Penal Code 631), VPPA, state wiretap.
- Enforcement: FTC press releases, HHS OCR enforcement, CPPA actions, state-AG announcements.
- Incidents: breach/security press with a client-side or third-party-script angle.
- People signals: privacy/compliance leadership changes, privacy & analytics-governance job posts.

## Minimum-evidence bar (every candidate must clear this)

A name without a resolvable source and a dated event is not a candidate — drop it, don't pad with it:

- A **real, resolvable `sourceUrl`** for the trigger (a page you actually reached, not a guessed
  URL). If you can't open it, it doesn't count.
- A **dated event** (`triggerDate`, YYYY-MM-DD when known) — recency drives ranking. An undated
  trigger is matched but discounted; an *unsourced* one is rejected outright.
- A `triggerKey` that exists in scoring-config's `whyNow` and a genuine web-tracking nexus.
- **No source = not a candidate.** When the only "evidence" is a hunch or a likely-but-unverified
  URL, leave the name out.

## Hard rules

- Aim for ~2x the requested count of raw leads, then keep only strong ones. **Never pad with weak
  fits** — fewer than requested, stated plainly, is the correct result when the territory is quiet.
- Every candidate needs a **real source URL** for its trigger. No fabricated companies, triggers,
  or sources. No companies already in the pipeline/exclusion set, and no obvious duplicates or
  subsidiaries of them.
- Candidate `reason` is one line: what happened, when, and why it makes them reachable now.
