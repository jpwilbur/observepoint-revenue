"""Flag crawler-artifact URLs in a Site Census sample (deterministic, no network).

The unrendered GET crawler can mis-parse escaped-quote hrefs and emit junk URLs like
`/%22//news//x///%22`. Because the junk lives in the PATH, it inflates the URL count and the path
count EQUALLY — so `size_site_census`'s query-param spiral gate (which compares URLs vs paths) does
NOT fire, even though the raw total can be several times the real page count (TKO: 306 raw → ~80
real, ~4×, which would over-scope the deal).

Run this on the real sample pages pulled for a census (the Stage-1 `url_samples`) BEFORE quoting a
count. A high `artifact_pct` means the raw URL total is parser junk, not real pages — quote the clean
count, not the raw total.

CLI:  check_artifacts.py <urls.json | urls.txt>
      JSON: a list of URL strings, or {"urls": [...]}. Text: one URL per line.
"""
import json
import pathlib
import sys

INFLATED_PCT = 20.0  # ≥ this share of junk → treat the raw total as inflated, not real pages


def is_artifact(url):
    """An escaped/literal double-quote, or a doubled slash in the host/path, marks parser junk."""
    u = (url or "").strip()
    if not u:
        return False
    if "%22" in u or '"' in u:
        return True
    after = u.split("://", 1)[-1]   # drop the scheme; `//` in the host/path is not a real page
    return "//" in after


def detect_artifacts(urls):
    urls = [u for u in (urls or []) if (u or "").strip()]
    total = len(urls)
    flagged = [u for u in urls if is_artifact(u)]
    pct = round(100.0 * len(flagged) / total, 1) if total else 0.0
    verdict = "inflated" if pct >= INFLATED_PCT else ("trace" if flagged else "clean")
    return {"total": total, "artifact_count": len(flagged), "artifact_pct": pct,
            "artifact_samples": flagged[:10], "verdict": verdict}


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
    print(f"Artifact scan: {r['artifact_count']}/{r['total']} URLs flagged "
          f"({r['artifact_pct']}%) — verdict: {r['verdict'].upper()}")
    if r["verdict"] == "inflated":
        print("  Raw URL total is inflated by crawler junk (escaped-quote / doubled-slash paths). "
              "Quote the CLEAN page count, not the raw total.")
    for s in r["artifact_samples"]:
        print(f"  artifact: {s}")


if __name__ == "__main__":
    main(sys.argv)
