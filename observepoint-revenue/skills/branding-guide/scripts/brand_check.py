# observepoint-revenue/skills/branding-guide/scripts/brand_check.py
"""Lint (and optionally auto-fix) a document or block of text against brand-spec.json.

Checks the deterministic, mechanical rules:
  - naming: disallowed spellings of the company name -> "ObservePoint"
  - color:  hex literals that are not in the approved palette
(Voice/tone is a judgment call Claude makes from references/voice-and-messaging.md;
this script only catches the mechanical violations.)

CLI:  python brand_check.py <file>            # list issues, exit 1 if any
      python brand_check.py <file> --fix      # rewrite the file with safe naming fixes
"""
from __future__ import annotations
import re
import sys

import brand_kit

_HEX_RE = re.compile(r"#[0-9a-fA-F]{6}")


def _approved_hexes() -> set[str]:
    c = brand_kit.colors()
    out: set[str] = set()
    for v in c.values():
        if isinstance(v, str) and v.startswith("#"):
            out.add(v.upper())
        elif isinstance(v, dict):
            out.update(x.upper() for x in v.values() if isinstance(x, str) and x.startswith("#"))
        elif isinstance(v, list):
            out.update(x.upper() for x in v if isinstance(x, str) and x.startswith("#"))
    return out


def check_text(text: str) -> list[dict]:
    """Return a list of brand violations found in *text*.

    Matching is case-sensitive by design — disallowed spellings like
    "Observepoint" and "Observe Point" are caught, but bare all-lowercase
    "observepoint" is intentionally NOT flagged to avoid false positives in
    domains, URLs, and code identifiers.

    The ``pos`` value in each returned dict is the character offset within the
    *text* argument passed to this call.  If you call fix_text() and want to
    re-check, call check_text() again on the fixed text rather than reusing
    the offsets from a previous call.
    """
    issues: list[dict] = []
    n = brand_kit.naming()
    for bad in n["disallowed"]:
        for m in re.finditer(re.escape(bad), text):
            issues.append({"kind": "naming", "found": bad, "pos": m.start(),
                           "fix": n["company"]})
    approved = _approved_hexes()
    for m in _HEX_RE.finditer(text):
        if m.group(0).upper() not in approved:
            issues.append({"kind": "color", "found": m.group(0), "pos": m.start(),
                           "fix": None})
    return issues


def fix_text(text: str) -> str:
    """Apply only the safe, unambiguous fixes (naming). Colors are reported, not auto-changed."""
    n = brand_kit.naming()
    # Safe with the current disallowed list (no entry is a substring of another). Review this if short-form entries (e.g. "OP") are ever added.
    for bad in n["disallowed"]:
        text = re.sub(re.escape(bad), n["company"], text)
    return text


def _main(argv) -> int:
    args = [a for a in argv if not a.startswith("--")]
    do_fix = "--fix" in argv
    if not args:
        sys.stderr.write("usage: brand_check.py <file> [--fix]\n")
        return 2
    path = args[0]
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if do_fix:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(fix_text(text))
        print(f"fixed naming in {path}")
        return 0
    issues = check_text(text)
    for i in issues:
        print(f"[{i['kind']}] {i['found']!r} at {i['pos']}"
              + (f" -> {i['fix']}" if i["fix"] else " (off-palette)"))
    print(f"{len(issues)} issue(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
