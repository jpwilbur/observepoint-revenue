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

## Sources to scan (public only)

- Litigation: ClassAction.org, Top Class Actions, Law360, Bloomberg Law, LawStreetMedia; the Duane
  Morris class-action review; DLA Piper / Davis Polk / Gibson Dunn / Baker McKenzie
  privacy-litigation reports; PACER coverage of CIPA (Cal. Penal Code 631), VPPA, state wiretap.
- Enforcement: FTC press releases, HHS OCR enforcement, CPPA actions, state-AG announcements.
- Incidents: breach/security press with a client-side or third-party-script angle.
- People signals: privacy/compliance leadership changes, privacy & analytics-governance job posts.

## Hard rules

- Aim for ~2x the requested count of raw leads, then keep only strong ones. **Never pad with weak
  fits** — fewer than requested, stated plainly, is the correct result when the territory is quiet.
- Every candidate needs a **real source URL** for its trigger. No fabricated companies, triggers,
  or sources. No companies already in the pipeline/exclusion set, and no obvious duplicates or
  subsidiaries of them.
- Candidate `reason` is one line: what happened, when, and why it makes them reachable now.
