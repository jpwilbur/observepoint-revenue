"""Render the customer-facing proposal one-pager (.docx) from the scope/compute output.
Customer-facing: NO internal discounting, spiral, or pricing-source language.

Input JSON: {customer, use_case, domains[], regulations[], monitoring_summary,
page_universe:{low,anchor,high,confidence},
scope:{predicted_scans, purchased_scans, buffer_pct, tier, price_total, pricing_source?}}.
`pricing_source` is accepted but intentionally NOT rendered (internal only)."""
import json
import sys

from docx import Document
from docx.shared import Pt

# Free-text fields the AGENT composes (vs. customer-supplied identity like name/domains/regulations,
# which may legitimately contain these substrings — "Discount Tire", "spiral-galaxy.com").
_NARRATIVE_FIELDS = ("monitoring_summary",)
# Internal-only language that must never reach a customer-facing proposal via narrative text.
_FORBIDDEN = ("spiral", "discount", "query-param", "raw url", "indefensible", "fallback")


def _int(n):
    return f"{int(round(n)):,}"


def _usd(n):
    return f"${n:,.0f}"


def build_proposal(data):
    _assert_clean(data)
    s = data["scope"]
    pu = data["page_universe"]
    doc = Document()

    doc.add_heading("ObservePoint — Proposed Scope & Investment", level=0)
    doc.add_paragraph(data.get("customer", ""))

    doc.add_heading("Scope", level=1)
    doc.add_paragraph("Properties: " + ", ".join(data.get("domains", [])))
    doc.add_paragraph(
        f"Page universe: ~{_int(pu['low'])}–{_int(pu['high'])} pages "
        f"(planning anchor ~{_int(pu['anchor'])})."
    )
    if data.get("regulations"):
        doc.add_paragraph("Regulations covered: " + ", ".join(data["regulations"]))

    doc.add_heading("What ObservePoint will monitor", level=1)
    doc.add_paragraph(data.get("monitoring_summary", ""))

    doc.add_heading("Recommended annual usage", level=1)
    if s.get("buffer_pct"):
        doc.add_paragraph(
            f"{_int(s['purchased_scans'])} page-scans / year "
            f"({_int(s['predicted_scans'])} projected + {round(s['buffer_pct'] * 100)}% buffer)."
        )
    else:
        doc.add_paragraph(f"{_int(s['purchased_scans'])} page-scans / year.")

    doc.add_heading("Investment", level=1)
    doc.add_paragraph(f"{_usd(s['price_total'])} per year ({s.get('tier', '')} tier).")
    foot = doc.add_paragraph()
    run = foot.add_run("Pricing reflects ObservePoint's published usage-based rates.")
    run.italic = True
    run.font.size = Pt(8)

    return doc


def _assert_clean(data):
    """Guard the agent-composed narrative fields against internal-only language. Scoped to
    free-text narrative (`_NARRATIVE_FIELDS`) — NOT customer name / domains / regulations, which
    are customer-supplied identity and may legitimately contain these substrings."""
    blob = " ".join(str(data.get(f, "")) for f in _NARRATIVE_FIELDS).lower()
    leaked = [w for w in _FORBIDDEN if w in blob]
    if leaked:
        raise ValueError(f"proposal narrative contains internal-only term(s): {leaked}")


def main(argv):
    if len(argv) > 1:
        with open(argv[1]) as fh:
            raw = fh.read()
    else:
        raw = sys.stdin.read()
    out = argv[2] if len(argv) > 2 else "proposal.docx"
    doc = build_proposal(json.loads(raw))  # narrative guard runs inside build_proposal
    doc.save(out)
    print(out)


if __name__ == "__main__":
    main(sys.argv)
