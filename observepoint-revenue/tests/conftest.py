"""Put the hyphenated skill script dirs on sys.path so tests can `import` the
script modules directly (compute_scope, fetch_pricing, build_evidence_appendix)."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent  # observepoint-revenue/
for rel in (
    "skills/size-and-price/scripts",
    "skills/derive-page-count/scripts",
    "skills/scope-calculator/scripts",
    "skills/research-account/scripts",
    "skills/owned-properties/scripts",
):
    sys.path.insert(0, str(ROOT / rel))
