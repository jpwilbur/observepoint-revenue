"""Deterministic ICP scoring for research-account.

The model CLASSIFIES (which fit criteria are met, which trigger events apply, with dates); this
computes the numbers from scoring-config.json. Keeping the math here (not in the model) makes scores
reproducible and tuning a config edit. Ported from NERD agents/src/scoring.ts.

`now` is passed explicitly (not the system clock) so a given classification always scores the same.

CLI:  score_account.py <classification.json> <out.json> [as_of YYYY-MM-DD]
      as_of (a bare date, e.g. 2026-06-07) defaults to the classification's "date" field.
      Prints the output path.
"""
import json
import math
import pathlib
import sys
from datetime import datetime, timezone

CONFIG = pathlib.Path(__file__).resolve().parent.parent / "references" / "scoring-config.json"
MONTH_MS = 30 * 86_400_000  # 30-day month approximation (mirrors the NERD TypeScript constant)


def load_config(path=None):
    return json.loads(pathlib.Path(path or CONFIG).read_text())


def _round_half_up(x):
    """Match JS Math.round (half rounds up), not Python's banker's rounding."""
    return int(math.floor(x + 0.5))


def _parse_ms(s):
    """Parse YYYY, YYYY-MM, YYYY-MM-DD, or full ISO to epoch ms (UTC). None if unparseable.

    Date-only formats are tried FIRST and anchored to UTC on purpose: parsing a bare date via
    fromisoformat would make it midnight LOCAL time, so the epoch ms (and thus recency) would differ
    across machines. A full ISO string with a time component is matched on its YYYY-MM-DD prefix and
    its time-of-day is intentionally ignored — recency is only ever measured in whole months."""
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            dt = datetime.strptime(s[:10] if fmt == "%Y-%m-%d" else s, fmt)
            return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


def recency_factor(date_str, recency, now_ms):
    """Full strength within fullStrengthMonths, linear decay to a 0.1 floor by zeroStrengthMonths.
    Undated/unparseable triggers get 0.6 (matched, but we can't time them)."""
    t = _parse_ms(date_str)
    if t is None:
        return 0.6
    months = (now_ms - t) / MONTH_MS
    if months <= recency["fullStrengthMonths"]:
        return 1.0
    if months >= recency["zeroStrengthMonths"]:
        return 0.1
    span = max(1, recency["zeroStrengthMonths"] - recency["fullStrengthMonths"])
    return max(0.1, 1 - (months - recency["fullStrengthMonths"]) / span)


def compute_fit(config, classification, now_ms):
    classified_fit = classification.get("fit", []) or []
    fit_breakdown = []
    for key, deff in config["fit"].items():
        m = next((f for f in classified_fit if f.get("key") == key), None)
        met = bool(m and m.get("met"))
        fit_breakdown.append({"key": key, "label": deff["label"],
                              "points": deff["points"] if met else 0,
                              "met": met, "evidence": (m or {}).get("evidence")})
    fit_score = min(100, sum(x["points"] for x in fit_breakdown))

    why_breakdown = []
    for t in classification.get("triggers", []) or []:
        sk = t.get("scoreKey")
        deff = config["whyNow"].get(sk) if sk else None
        if not deff:
            continue  # unscored trigger: stays in the raw list, no points
        pts = _round_half_up(deff["points"] * recency_factor(t.get("date"), config["recency"], now_ms))
        why_breakdown.append({"key": sk, "label": deff["label"], "basePoints": deff["points"],
                              "points": pts, "description": t.get("description"),
                              "date": t.get("date"), "sourceUrl": t.get("sourceUrl")})
    why_score = sum(x["points"] for x in why_breakdown)

    by_fit = fit_score >= config["fitGate"]
    by_trigger = why_score >= config["triggerOverride"]
    qualified = by_fit or by_trigger
    return {
        "fitScore": fit_score, "whyNowScore": why_score, "finalScore": fit_score + why_score,
        "qualified": qualified, "lowFitHighTrigger": qualified and not by_fit and by_trigger,
        "fitBreakdown": fit_breakdown, "whyNowBreakdown": why_breakdown,
    }


def score(classification, as_of=None, config=None):
    cfg = config or load_config()
    as_of = as_of or classification.get("date")
    now_ms = _parse_ms(as_of)
    if now_ms is None:
        raise ValueError("score() needs an as_of date (arg or classification['date']) in YYYY-MM-DD")
    out = dict(classification)  # shallow copy; compute_fit only reads nested fit/triggers, so the input is not mutated
    out["score"] = compute_fit(cfg, classification, now_ms)
    out["scoredAsOf"] = as_of
    return out


def main(argv):
    if len(argv) < 3:
        sys.exit("usage: score_account.py <classification.json> <out.json> [as_of YYYY-MM-DD]")
    data = json.loads(pathlib.Path(argv[1]).read_text())
    as_of = argv[3] if len(argv) > 3 else data.get("date")
    out = score(data, as_of)
    pathlib.Path(argv[2]).write_text(json.dumps(out, indent=2))
    print(argv[2])


if __name__ == "__main__":
    main(sys.argv)
