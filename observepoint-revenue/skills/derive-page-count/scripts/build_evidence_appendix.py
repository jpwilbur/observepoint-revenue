"""Render the customer-facing evidence appendix .xlsx from Site Census per-domain
data. Enforces the spec §4.6 invariant: per-domain defensible_pages must sum to
the rolled-up anchor."""
import json
import sys

from openpyxl import Workbook
from openpyxl.styles import Font

FILL_COLS = ["Include in scope?", "Priority", "Notes"]  # customer-fillable, left empty


def _check_invariant(data):
    total = sum(d["defensible_pages"] for d in data["per_domain"])
    anchor = data["rollup"]["spiral_adjusted_anchor"]
    if total != anchor:
        breakdown = ", ".join(
            f"{d['hostname']}={d['defensible_pages']}" for d in data["per_domain"])
        raise ValueError(
            f"per-domain defensible_pages sum {total} != rollup anchor {anchor} "
            f"(per domain: {breakdown})")


def _bold_header(ws):
    for c in ws[1]:
        c.font = Font(bold=True)


def build_workbook(data):
    _check_invariant(data)
    domains = data["per_domain"]
    r = data["rollup"]
    raw_total = sum(d["raw_urls"] for d in domains)
    def_total = sum(d["defensible_pages"] for d in domains)

    wb = Workbook()

    ss = wb.active
    ss.title = "Scope Summary"
    for row in [
        ["ObservePoint — Page-Count Evidence", ""],
        ["Customer", data.get("customer", "")],
        ["Census ID(s)", ", ".join(str(c) for c in r.get("census_ids", []))],
        ["Crawl status", r.get("crawl_status", "")],
        ["Confidence", r.get("confidence", "")],
        ["", ""],
        ["Defensible pages — low", r.get("low", "")],
        ["Defensible pages — anchor (recommended)", r.get("spiral_adjusted_anchor", "")],
        ["Defensible pages — high", r.get("high", "")],
        ["", ""],
        ["Total raw URLs crawled", raw_total],
        ["Total defensible pages", def_total],
        ["Discounted (raw - defensible)", raw_total - def_total],
        ["", ""],
        ["How to use", "Review the 'Pages by Domain' tab and confirm these are the "
                       "right properties. Fill Include/Priority to validate scope. "
                       "'Raw Evidence' shows why query-param spirals were discounted."],
    ]:
        ss.append(row)
    ss["A1"].font = Font(bold=True, size=14)

    pbd = wb.create_sheet("Pages by Domain")
    pbd.append(["Domain", "Defensible pages", "Spiral?"] + FILL_COLS)
    _bold_header(pbd)
    for d in domains:
        pbd.append([d["hostname"], d["defensible_pages"],
                    "Yes" if d.get("spiral_flag") else "No", None, None, None])

    raw = wb.create_sheet("Raw Evidence")
    raw.append(["Domain", "Raw distinct URLs", "Distinct paths", "Spiral ratio",
                "Discounted", "Why"])
    _bold_header(raw)
    for d in domains:
        raw.append([d["hostname"], d["raw_urls"], d.get("paths", ""),
                    d.get("spiral_ratio", ""), d.get("discounted", ""), d.get("why", "")])

    samples = wb.create_sheet("URL Samples")
    samples.append(["Domain", "Sample URL"])
    _bold_header(samples)
    any_samples = False
    for d in domains:
        for url in d.get("url_samples", []):
            samples.append([d["hostname"], url])
            any_samples = True
    if not any_samples:
        samples.append(["(no per-URL samples available from this census summary)", ""])

    return wb


def main(argv):
    if len(argv) > 1:
        with open(argv[1]) as fh:
            raw = fh.read()
    else:
        raw = sys.stdin.read()
    out = argv[2] if len(argv) > 2 else "evidence-appendix.xlsx"
    build_workbook(json.loads(raw)).save(out)
    print(out)


if __name__ == "__main__":
    main(sys.argv)
