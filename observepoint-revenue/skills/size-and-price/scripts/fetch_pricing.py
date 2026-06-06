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
_GT_RE = re.compile(r"Gt=\[(\{limit:.*?\})\]")
_BAND_RE = re.compile(r"\{limit:([\deE.+-]+),pricePerPage:([\d.]+)\}")


def parse_tiers(js_text):
    """Extract the Gt=[...] tier array from bundle text → list of
    {limit, pricePerPage}, or None if not found."""
    m = _GT_RE.search(js_text)
    if not m:
        return None
    bands = [
        {"limit": int(float(limit_s)), "pricePerPage": float(rate_s)}
        for limit_s, rate_s in _BAND_RE.findall(m.group(1))
    ]
    return bands or None


def validate_tiers(tiers):
    """Sanity gate: >= 5 bands, strictly increasing limits, non-negative rates."""
    if not tiers or len(tiers) < 5:
        return False
    if any(b["pricePerPage"] < 0 for b in tiers):
        return False
    limits = [b["limit"] for b in tiers]
    return all(a < b for a, b in zip(limits, limits[1:]))


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
    return {"tiers": BAKED_TIERS, "source": f"fallback (baked {BAKED_AS_OF})"}


def main(argv):
    if "--offline" in argv:  # test/dev hook: skip the network, force fallback path
        out = fetch_pricing(fetcher=lambda url: "")
    else:
        out = fetch_pricing()
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main(sys.argv)
