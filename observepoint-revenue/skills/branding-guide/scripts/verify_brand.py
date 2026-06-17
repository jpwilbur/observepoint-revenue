# observepoint-revenue/skills/branding-guide/scripts/verify_brand.py
"""Re-pull the live ObservePoint site and report drift against brand-spec.json.

Deterministic, stdlib-only (urllib). NEVER edits the spec — it prints a drift
report; a human/Claude updates brand-spec.json deliberately (reproducible, no
LLM-maintained state).

CLI:  python verify_brand.py            # human-readable report, exit 0 if no drift
      python verify_brand.py --json     # machine-readable report
"""
from __future__ import annotations
import json
import re
import sys
import urllib.request

import brand_kit

SITE = "https://www.observepoint.com/"
_YELLOW_RE = re.compile(r"\.logo\s*\{[^}]*color\s*:\s*(#[0-9a-fA-F]{6})", re.I)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "op-branding-guide/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def extract_site_yellow(html: str) -> str | None:
    m = _YELLOW_RE.search(html)
    return m.group(1) if m else None


def check_drift(html: str | None = None) -> dict:
    if html is None:
        html = fetch(SITE)
    site_yellow = extract_site_yellow(html)
    spec_yellow = brand_kit.brand_yellow()
    match = bool(site_yellow) and site_yellow.upper() == spec_yellow.upper()
    return {
        "yellow": {"site": site_yellow, "spec": spec_yellow, "match": match},
        "ok": match,
    }


def _main(argv) -> int:
    report = check_drift()
    if "--json" in argv:
        print(json.dumps(report, indent=2))
    else:
        y = report["yellow"]
        flag = "OK" if y["match"] else "DRIFT"
        print(f"[{flag}] brand yellow — site={y['site']} spec={y['spec']}")
        if not report["ok"]:
            print("Review and update brand-spec.json deliberately, then bump meta.last_verified.")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
