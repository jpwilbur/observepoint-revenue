# tests/test_customer_clean.py
import pathlib
import pytest
import customer_clean as cc

REFS = pathlib.Path(__file__).resolve().parent.parent / "skills" / "scope-calculator" / "references"
VOCAB = REFS / "customer-vocabulary.md"


def test_flags_internal_terms():
    leaked = cc.find_forbidden(["Annual full-site sweep", "we discounted the spiral URLs"])
    assert "spiral" in leaked and "discount" in leaked


def test_clean_text_passes():
    assert cc.find_forbidden(["Annual full-site monitoring", "weekly release checks"]) == []
    cc.assert_clean(["Annual full-site monitoring"])  # must not raise


def test_assert_clean_raises_with_context():
    with pytest.raises(ValueError, match="internal-only term"):
        cc.assert_clean(["raw URL total"], where="proposal")


def test_identity_values_are_not_passed_here():
    # The guard only sees strings the CALLER chooses to pass; callers must exclude identity fields.
    # A customer literally named "Discount Tire" only false-trips if a caller wrongly passes it —
    # this asserts the guard itself has no special-casing, documenting the caller contract.
    assert cc.find_forbidden(["Discount Tire Co"]) == ["discount"]


def test_every_forbidden_term_is_documented_in_vocab():
    doc = VOCAB.read_text().lower()
    missing = [t for t in cc.FORBIDDEN if t not in doc]
    assert missing == [], f"terms in FORBIDDEN but not in customer-vocabulary.md: {missing}"
