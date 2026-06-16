# skills/scope-calculator/scripts/customer_clean.py
"""Shared customer-facing-language guard for scope-calculator deliverables.

Internal Site Census / pricing jargon must never reach a customer .docx or .xlsx. This module is
the single source of the forbidden-term list (kept in sync with references/customer-vocabulary.md)
and the guard both generators call.

CALLER CONTRACT: pass only AGENT-COMPOSED, customer-facing strings (narrative, cadence names,
"why" lines, properties notes). NEVER pass identity/factual fields (customer name, domains,
prepared_by) — a customer named "Discount Tire" or a domain "spiral-galaxy.com" would false-trip.
The guard intentionally has no identity special-casing; scoping is the caller's job.
"""

# Internal-only terms that must not appear in customer-facing prose or labels.
# MIRRORS references/customer-vocabulary.md (test_every_forbidden_term_is_documented_in_vocab).
FORBIDDEN = (
    "site census", "census", "spiral", "raw url", "defensible", "indefensible",
    "reduced", "discount", "query-param", "query-string", "crawl", "recursion",
    "collapsed", "anchor", "fallback",
)


def find_forbidden(strings):
    """Return the forbidden terms present (substring, case-insensitive) across the given strings."""
    blob = " ".join(s for s in strings if s).lower()
    return [t for t in FORBIDDEN if t in blob]


def assert_clean(strings, where="customer deliverable"):
    leaked = find_forbidden(strings)
    if leaked:
        raise ValueError(f"{where} contains internal-only term(s): {sorted(set(leaked))}")
