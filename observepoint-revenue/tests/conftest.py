"""Put the hyphenated skill script dirs on sys.path so tests can `import` the
script modules directly (compute_scope, fetch_pricing, build_proposal, build_model
all live under scope-calculator/scripts)."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent  # observepoint-revenue/
for rel in (
    "lib/salesforce",
    "lib/domo",
    "skills/scope-calculator/scripts",
    "skills/research-account/scripts",
    "skills/owned-properties/scripts",
    "skills/find-accounts/scripts",
    "skills/branding-guide/scripts",
    "skills/op-mcp-post-mortem/scripts",
):
    sys.path.insert(0, str(ROOT / rel))
