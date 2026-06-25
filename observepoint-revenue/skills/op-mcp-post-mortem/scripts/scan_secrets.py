"""Deterministic secret/PII scanner for OP MCP post-mortems (no network, no LLM).

A post-mortem file is forwarded, pasted into tickets, and archived, so any live credential or
customer PII in it is a real leak. Claude decides *what* a post-mortem should say; this script does
the deterministic part — finding the things that must not leave the machine unredacted.

It does two jobs:
  - scan(text)  -> a deduped list of findings [{category, match, line}], priority-ordered so an
                   overlapping hit (a JWT inside a Bearer header) is reported once, most-specific first.
  - redact(text) -> the same text with every match replaced by [REDACTED:<category>].

Emails are flagged (PII) but NOT special-cased: the reporter's own email is a legitimate part of a
post-mortem's metadata, so the scanner only *flags* — the human keeps the reporter line and redacts
customer addresses. (`--redact` is blunt and replaces every match; use it on raw evidence excerpts,
not on the metadata block.)

CLI:
  scan_secrets.py <file>            human-readable findings report (exit 2 if any found, else 0)
  scan_secrets.py <file> --json     findings as JSON
  scan_secrets.py <file> --redact   print the redacted text to stdout (exit 0)
  cat x | scan_secrets.py           reads stdin when no file given
"""
import argparse
import json
import re
import sys

# (category, compiled pattern). Order = priority: the first/most-specific match wins a span, so a
# JWT carried in a Bearer header is reported as a jwt, not also as a bearer_token.
_SPECS = [
    ("jwt", r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}(?:\.[A-Za-z0-9_\-]+)?"),
    ("op_api_key", r"\bop_(?:live|test)_[A-Za-z0-9_]{6,}\b"),
    ("api_key", r"\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{6,}\b"),
    ("bearer_token", r"(?i)bearer\s+[A-Za-z0-9._\-]{8,}"),
    ("authorization", r"(?im)authorization[\"']?\s*[:=]\s*[\"']?[^\s,\"'}]+"),
    ("secret_field",
     r"(?i)[\"']?(?:password|passwd|secret|client[_-]?secret|access[_-]?token|"
     r"refresh[_-]?token|auth[_-]?token|api[_-]?key|apikey|x-api-key|token)[\"']?"
     r"\s*[:=]\s*[\"']?[^\s,\"'}]{4,}[\"']?"),
    ("cookie_header", r"(?im)(?:set-)?cookie[\"']?\s*[:=]\s*[^\n]+"),
    ("known_cookie",
     r"(?i)\b(?:sessionid|jsessionid|optanonconsent|csrftoken|xsrf-token|datadome|_ga)=[^;\s\"']+"),
    ("email", r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
]
_PATTERNS = [(cat, re.compile(rx)) for cat, rx in _SPECS]


def _spans(text):
    """All (start, end, category) matches across every pattern, in priority then position order."""
    hits = []
    for cat, rx in _PATTERNS:
        for m in rx.finditer(text):
            hits.append((m.start(), m.end(), cat))
    return hits


def scan(text):
    """Deduped findings. Overlapping hits collapse to the highest-priority (earliest pattern) one."""
    taken = []  # (start, end) spans already claimed by a higher-priority pattern
    findings = []
    line_starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            line_starts.append(i + 1)
    for start, end, cat in _spans(text):
        if "REDACTED" in text[start:end].upper():
            continue  # already scrubbed (e.g. apiKey: "[REDACTED]") — not a live secret
        if any(start < t_end and end > t_start for t_start, t_end in taken):
            continue
        taken.append((start, end))
        line = sum(1 for ls in line_starts if ls <= start)
        findings.append({"category": cat, "match": text[start:end], "line": line})
    findings.sort(key=lambda f: (f["line"], f["match"]))
    return findings


def redact(text):
    """Replace every match with [REDACTED:<category>], most-specific patterns first."""
    for cat, rx in _PATTERNS:
        text = rx.sub(f"[REDACTED:{cat}]", text)
    return text


def main(argv):
    ap = argparse.ArgumentParser(description="Scan OP MCP post-mortem text for secrets/PII.")
    ap.add_argument("file", nargs="?", help="file to scan; reads stdin if omitted")
    ap.add_argument("--json", action="store_true", help="emit findings as JSON")
    ap.add_argument("--redact", action="store_true", help="print redacted text instead of findings")
    args = ap.parse_args(argv[1:])

    text = open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read()

    if args.redact:
        sys.stdout.write(redact(text))
        return 0

    findings = scan(text)
    if args.json:
        print(json.dumps({"count": len(findings), "findings": findings}, indent=2))
    elif not findings:
        print("scan_secrets: clean — no secrets or PII detected.")
    else:
        print(f"scan_secrets: {len(findings)} item(s) to review BEFORE this file is shared:")
        for f in findings:
            print(f"  line {f['line']:>4}  [{f['category']}]  {f['match']}")
        print("\nRedact live credentials and customer PII. The reporter's own email may stay.")
    return 2 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
