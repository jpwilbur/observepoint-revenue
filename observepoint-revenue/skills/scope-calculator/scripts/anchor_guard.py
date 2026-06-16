"""Stage-1 anchor plausibility guard (deterministic, no network, no LLM math).

Before a derived page-count anchor propagates into pricing, the rep must confirm it. This module
provides the deterministic signals the Stage-1 confirmation gate uses:
  - the ROLLUP-DOMINANCE flag: one host an outsized share of the anchor (the Gallagher
    recursion-trap signal — stevenson-insurance.com was 93% of the total), and
  - a CONFIDENCE-aware confirmation directive.
The recursion/%22 verdict itself comes from check_artifacts.py (run on URL samples, Stage-1 step 5);
this module covers the rollup-level + confidence signals and is the single home of the threshold.

Input: the same {rollup, per_domain} object Stage 1 emits. rollup has spiral_adjusted_anchor +
confidence; per_domain has hostname + defensible_pages.
"""
import json
import sys

DOMINANCE_THRESHOLD = 0.40        # one host > this share of the anchor → confirm it's not a trap
_CONFIRM_CONFIDENCE = {"LOW", "MEDIUM"}   # confidence levels that force a hard-stop confirmation


def dominant_host(data):
    """The per-domain row whose defensible_pages exceed DOMINANCE_THRESHOLD of the anchor, else None."""
    pd = data.get("per_domain") or []
    if not pd:
        return None
    anchor = (data.get("rollup") or {}).get("spiral_adjusted_anchor") or 0
    if anchor <= 0:
        return None
    top = max(pd, key=lambda d: d["defensible_pages"])
    return top if top["defensible_pages"] / anchor > DOMINANCE_THRESHOLD else None


def gate_report(data):
    """Deterministic anchor-gate signals. Returns
    {anchor, confidence, dominant:{hostname,pct}|None, requires_confirmation:bool, reasons:[...]}.
    requires_confirmation is True when a dominant host trips OR confidence is LOW/MEDIUM — the cases
    the rep MUST acknowledge before pricing. (Recursion is handled in SKILL.md step 5; the gate ties
    that verdict in too.)"""
    rollup = data.get("rollup") or {}
    anchor = rollup.get("spiral_adjusted_anchor")
    confidence = str(rollup.get("confidence", "")).upper()
    dom = dominant_host(data)
    dom_pct = round(100.0 * dom["defensible_pages"] / anchor, 1) if dom else None
    reasons = []
    if dom:
        reasons.append(f"one host ({dom['hostname']}) is {dom_pct}% of the anchor — verify it is not "
                       f"a recursion trap (sample it via check_artifacts) before pricing")
    if confidence in _CONFIRM_CONFIDENCE:
        reasons.append(f"confidence is {confidence} — confirm the range before pricing")
    return {"anchor": anchor, "confidence": confidence,
            "dominant": {"hostname": dom["hostname"], "pct": dom_pct} if dom else None,
            "requires_confirmation": bool(reasons), "reasons": reasons}


def main(argv):
    if len(argv) > 1:
        with open(argv[1]) as fh:
            raw = fh.read()
    else:
        raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f"scope-calculator: anchor-guard inputs are not valid JSON ({e}); "
                 f"see references/site-census-methodology.md")
    r = gate_report(data)
    anchor_s = f"{r['anchor']:,}" if isinstance(r["anchor"], (int, float)) else "—"
    print(f"ANCHOR GATE — anchor {anchor_s}, confidence {r['confidence'] or '—'}")
    if r["dominant"]:
        print(f"  ! dominant host: {r['dominant']['hostname']} = {r['dominant']['pct']}% of anchor")
    if r["requires_confirmation"]:
        print("  CONFIRM REQUIRED before pricing:")
        for reason in r["reasons"]:
            print(f"   - {reason}")
    else:
        print("  clean (HIGH confidence, no dominant host) — confirm the anchor to proceed.")


if __name__ == "__main__":
    main(sys.argv)
