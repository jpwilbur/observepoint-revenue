"""Flag crawler-artifact URLs in a Site Census sample (deterministic, no network).

The unrendered GET crawler emits two classes of in-path junk that every `size_site_census` gate is
blind to, because both inflate the distinct-URL count and the distinct-PATH count EQUALLY (so the
query-param spiral gate, which compares URLs vs paths, never fires — ratio stays ~1):

  1. ESCAPED-QUOTE / DOUBLED-SLASH artifacts — mis-parsed hrefs like `/%22//news//x///%22`
     (TKO: 306 raw → ~80 real, ~4×).
  2. PATH-RECURSION traps — a relative-link loop that re-appends a nav segment onto the path over
     and over: `/contact/business-insurance/business-insurance/.../commercial-property-insurance`.
     These have NO %22, NO doubled-slash, NO query string, so they slip past BOTH the spiral gate AND
     the %22 check, and even the PATTERN backstop fails (each depth is a structurally distinct
     template, so `patterns` stays ~= `paths`). Post-mortem 2026-06-15: one such host
     (stevenson-insurance.com) reported 1.71M URLs for a ~150-page agency — a silent ~15× over-count
     that dominated 93% of the account total with NO warning from any gate.

Run this on the real sample pages pulled for a census (the Stage-1 raw `url_samples`) BEFORE quoting a
count. A high `junk_pct` means the raw URL total is parser junk, not real pages — quote the clean
count, not the raw total. For a recursion host, even the path count is junk: exclude it from the
anchor and re-crawl with recursion/param handling to measure it.

CLI:  check_artifacts.py <urls.json | urls.txt>
      JSON: a list of URL strings, or {"urls": [...]}. Text: one URL per line.
"""
import json
import pathlib
import sys
from collections import Counter

INFLATED_PCT = 20.0   # ≥ this share of junk → treat the raw total as inflated, not real pages
MAX_CONSEC = 3        # a segment repeated ≥ this many times CONSECUTIVELY (e.g. /x/x/x) = recursion
MAX_SEGMENT_TOTAL = 4  # any single segment appearing ≥ this many times anywhere in the path = recursion


def is_artifact(url):
    """An escaped/literal double-quote, or a doubled slash in the host/path, marks parser junk."""
    u = (url or "").strip()
    if not u:
        return False
    if "%22" in u or '"' in u:
        return True
    after = u.split("://", 1)[-1]   # drop the scheme; `//` in the host/path is not a real page
    return "//" in after


def _path_segments(url):
    """Real (non-empty) path segments, scheme/host/query/fragment stripped. Empty segments (from a
    doubled slash) are dropped — that junk is is_artifact()'s job, not recursion's."""
    u = (url or "").strip()
    if not u:
        return []
    after = u.split("://", 1)[-1]              # drop scheme
    after = after.split("?", 1)[0].split("#", 1)[0]  # drop query + fragment
    return [p for p in after.split("/")[1:] if p]    # drop host, keep non-empty segments


def is_recursion(url):
    """A path-recursion trap: the same segment repeated ≥MAX_CONSEC times in a row, OR any single
    segment appearing ≥MAX_SEGMENT_TOTAL times in the path. Both are vanishingly rare in real URLs
    (which is why this is high-precision); a deep-but-distinct path like /api/v2/reference/objects is
    NOT flagged."""
    segs = _path_segments(url)
    if len(segs) < MAX_CONSEC:
        return False
    run = 1
    for i in range(1, len(segs)):
        run = run + 1 if segs[i] == segs[i - 1] else 1
        if run >= MAX_CONSEC:
            return True
    return max(Counter(segs).values()) >= MAX_SEGMENT_TOTAL


def _collapsed_key(url):
    """Collapse consecutive repeated segments to a single instance — the trap's underlying real
    template (`/contact/biz/biz/biz/x` → `/contact/biz/x`). Distinct collapsed keys across the
    recursion sample is a FLOOR estimate of the host's real page count."""
    out = []
    for s in _path_segments(url):
        if not out or out[-1] != s:
            out.append(s)
    return "/".join(out)


def detect_artifacts(urls):
    urls = [u for u in (urls or []) if (u or "").strip()]
    total = len(urls)
    artifact = [u for u in urls if is_artifact(u)]
    recursion = [u for u in urls if is_recursion(u)]
    junk = [u for u in urls if is_artifact(u) or is_recursion(u)]  # union, counted per-URL
    pct = lambda n: round(100.0 * n / total, 1) if total else 0.0
    junk_pct = pct(len(junk))
    verdict = "inflated" if junk_pct >= INFLATED_PCT else ("trace" if junk else "clean")
    return {"total": total,
            "artifact_count": len(artifact), "artifact_pct": pct(len(artifact)),
            "artifact_samples": artifact[:10],
            "recursion_count": len(recursion), "recursion_pct": pct(len(recursion)),
            "recursion_samples": recursion[:10],
            "junk_count": len(junk), "junk_pct": junk_pct,
            "collapsed_distinct": len({_collapsed_key(u) for u in recursion}) if recursion else 0,
            "verdict": verdict}


def _load(path):
    raw = pathlib.Path(path).read_text()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data.get("urls", [])
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    return [ln for ln in raw.splitlines() if ln.strip()]


def main(argv):
    if len(argv) < 2:
        sys.exit("usage: check_artifacts.py <urls.json | urls.txt>")
    r = detect_artifacts(_load(argv[1]))
    print(f"Junk scan: {r['junk_count']}/{r['total']} URLs flagged "
          f"({r['junk_pct']}%) — verdict: {r['verdict'].upper()}")
    if r["recursion_count"]:
        print(f"  recursion-trap URLs: {r['recursion_count']} ({r['recursion_pct']}%) — repeated path "
              f"segments; sample collapses to ~{r['collapsed_distinct']} real template(s).")
    if r["artifact_count"]:
        print(f"  escaped-quote / doubled-slash artifacts: {r['artifact_count']} ({r['artifact_pct']}%).")
    if r["verdict"] == "inflated":
        if r["recursion_count"] >= r["artifact_count"]:
            print("  RECURSION TRAP: even the PATH count for this host is junk. Do NOT fold its "
                  "raw/path/pattern count into the anchor — EXCLUDE it, note it, and re-crawl with "
                  "recursion/param handling to measure the real (small) page count.")
        else:
            print("  Raw URL total is inflated by crawler junk (escaped-quote / doubled-slash paths). "
                  "Quote the CLEAN page count, not the raw total.")
    for s in r["recursion_samples"][:5]:
        print(f"  recursion: {s}")
    for s in r["artifact_samples"][:5]:
        print(f"  artifact: {s}")


if __name__ == "__main__":
    main(sys.argv)
