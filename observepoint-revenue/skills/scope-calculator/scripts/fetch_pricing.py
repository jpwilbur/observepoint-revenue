"""Fetch ObservePoint's live graduated pricing tiers from the public pricing-app
JS bundle, validate them, and fall back to the baked table on any failure.

The math and the baked table live in compute_scope (single source of truth);
this module only does network + parsing.
"""
import json
import re
import sys
import urllib.request

from compute_scope import BAKED_TIERS, BAKED_AS_OF

BUNDLE_URL = "https://app.observepoint.com/www-pricing/main.js"
# Locate the graduated-tier array by its STABLE SHAPE, not the minified var name — that name churns
# every build (it was `Gt=` in June 2026, became `Yt=`, and will change again). Anchor on
# `=[{limit:N,pricePerPage:N},…]` and require >=5 bands so neither a 1-band sibling array nor a
# `[...Yt,{limit:Number.MAX_SAFE_INTEGER,pricePerPage:…}]` spread (non-numeric limit) can match.
# If the bundle is ever reformatted past this, fetch_pricing() degrades to the baked fallback
# (source reports "fallback") rather than crashing or serving wrong data.
_BAND = r"\{limit:[\deE.+-]+,pricePerPage:[\d.]+\}"
_TIERS_RE = re.compile(r"=\[(" + _BAND + r"(?:," + _BAND + r"){4,})\]")
_BAND_RE = re.compile(r"\{limit:([\deE.+-]+),pricePerPage:([\d.]+)\}")


def parse_tiers(js_text):
    """Extract the graduated-tier array (`<var>=[{limit,pricePerPage},…]`) from bundle text →
    list of {limit, pricePerPage}, or None if not found. Var-name-agnostic by design."""
    m = _TIERS_RE.search(js_text)
    if not m:
        return None
    bands = [
        {"limit": int(float(limit_s)), "pricePerPage": float(rate_s)}
        for limit_s, rate_s in _BAND_RE.findall(m.group(1))
    ]
    return bands or None


def validate_tiers(tiers):
    """Sanity gate that a parse produced a usable graduated table: >= 5 bands,
    every band WIDTH positive, every rate non-negative, and the paid rates
    non-increasing (graduated tiers get cheaper after the free first band).
    NOTE: 'limit' is a band WIDTH, not a cumulative cap, so widths need NOT
    increase across bands."""
    if not tiers or len(tiers) < 5:
        return False
    if any(b["limit"] <= 0 for b in tiers):
        return False
    rates = [b["pricePerPage"] for b in tiers]
    if any(r < 0 for r in rates):
        return False
    paid = [r for r in rates if r > 0]
    return all(a >= b for a, b in zip(paid, paid[1:]))


def _default_fetcher(url):
    with urllib.request.urlopen(url, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def fetch_pricing(fetcher=_default_fetcher, url=BUNDLE_URL):
    """Return {tiers, source}. Live tiers on success+valid; baked fallback otherwise."""
    try:
        tiers = parse_tiers(fetcher(url))
        if validate_tiers(tiers):
            return {"tiers": tiers, "source": f"live @ {url}"}
    except Exception:
        pass
    # LOUD, unmistakable canary: the only signal of a stale price is this string, so make it scream.
    return {"tiers": BAKED_TIERS,
            "source": f"FALLBACK — baked {BAKED_AS_OF}; LIVE PRICING UNAVAILABLE, verify before sending"}


def main(argv):
    if "--offline" in argv:  # test/dev hook: skip the network, force fallback path
        out = fetch_pricing(fetcher=lambda url: "")
    else:
        out = fetch_pricing()
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main(sys.argv)
