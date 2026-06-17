# owned-properties crt.sh Portability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `discover_domains.py` work in a restricted-egress runtime (Cowork sandbox) by (a) letting the agent supply a crt.sh payload it fetched through its own sanctioned egress, and (b) reporting a distinct `blocked` status — with a remediation hint — instead of a silent, misleading `host_count: 0`.

**Architecture:** Keep the script's existing dependency-injection seam (`fetcher`) and add a thin CLI surface around it. Two new flags — `--print-crt-url` (emit the URL the agent should fetch) and `--crt-json FILE` (parse a pre-fetched payload, no network) — turn the script into the "compute" half of the plugin's *Claude gathers → scripts compute* principle. A pure `_classify_fetch_error()` splits permanent egress blocks (403/proxy-CONNECT/DNS-blackhole → fail fast, status `blocked`) from transient flakiness (503/timeout → retry, status `unreachable`). No new network providers, no RDAP, no EDGAR scripting — those were considered and deferred (see "Out of scope").

**Tech Stack:** Python 3 (stdlib only: `argparse`, `socket`, `urllib.error`), pytest. Interpreter: `/opt/homebrew/bin/python3` (the bare `python3`/`/usr/bin/python3` lacks pytest).

---

## Context for the implementer (read before starting)

- **The bug is not a logic defect.** The script already refuses to fabricate and already signals failure via `crt_status`. This work is *portability hardening*: it makes the tool usable when the process has no direct outbound HTTPS (an allowlisting egress proxy returns `HTTP 403` at `CONNECT`).
- **Single file of production code:** `skills/owned-properties/scripts/discover_domains.py`. Single test file: `tests/test_discover_domains.py`. One docs file: `skills/owned-properties/SKILL.md`.
- **Baseline:** the full suite is green at **244 passing** before you start (`/opt/homebrew/bin/python3 -m pytest tests -q`). Every task below must keep it green and add new tests.
- **Backward-compat contracts you MUST NOT break:**
  - `enumerate_crt_with_status(apex, fetcher=None)` returns a **2-tuple** `(set, str)`. `enumerate_crt()` unpacks exactly two values from it — do not change the arity.
  - `crt_status` stays a **simple enum string**. Today: `"ok"` / `"unreachable"`. After this work: `"ok"` / `"unreachable"` / `"blocked"`. Do not embed HTTP codes into the status value — SKILL.md and existing tests key on the bare enum.
  - The existing CLI call shape `main(["discover_domains.py", "<apex>", "<out.json>"])` must keep working (a test depends on it).
  - A transient failure (`RuntimeError("503 ...")`, empty body) must still retry `CRT_ATTEMPTS` times and end as `"unreachable"` — three existing tests assert this.
- **Run tests from the repo root** `observepoint-revenue/`. Tests import the script by module name (`import discover_domains as dd`) because `tests/conftest.py` puts the script dir on `sys.path`.

## File Structure

- **Modify:** `skills/owned-properties/scripts/discover_domains.py`
  - New imports: `argparse`, `socket`, `urllib.error`.
  - New pure helper `crt_url(apex)` — builds the crt.sh URL or returns `None` for a refused bare suffix (DRYs the URL string + the refusal that currently live inline in `enumerate_crt_with_status`).
  - New pure helper `_classify_fetch_error(exc)` + module constants `_BLOCK_HTTP_CODES`, `_BLOCK_PHRASES`.
  - Modify `enumerate_crt_with_status()` — use `crt_url()`, classify exceptions, add fail-fast `blocked`.
  - Modify `discover()` — only the explanatory comment (it already passes `crt_status` through unchanged).
  - Rewrite `main()` — argparse; `--print-crt-url`; `--crt-json`; blocked remediation line to stderr.
- **Modify:** `tests/test_discover_domains.py` — add tests for each new behavior.
- **Modify:** `skills/owned-properties/SKILL.md` — document the three states + the two-step recovery.

## Out of scope (deliberately deferred — do NOT build these here)

These were in the postmortem's P1–P3 but are excluded from this plan by decision:
- Pluggable CT-provider chain (certspotter etc.). *Reason: in a fully egress-blocked sandbox a direct-fetch provider is blocked too; value is real but separate. → ROADMAP.*
- RDAP-over-HTTPS WHOIS replacement. *Reason: WHOIS registrant is a secondary signal the skill already handles when absent; separate concern. → ROADMAP.*
- Scripting the EDGAR Exhibit-21 path and JS-rendered-site flagging. *Reason: these are new features (the EDGAR recipe is already a documented manual step in SKILL.md and only applies to SEC filers). → ROADMAP.*

If you finish early, **stop** — do not pull these in. Note them in `docs/ROADMAP.md` instead (optional).

---

### Task 1: Extract the `crt_url()` helper (refactor + DRY)

**Files:**
- Modify: `skills/owned-properties/scripts/discover_domains.py`
- Test: `tests/test_discover_domains.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_discover_domains.py`:

```python
def test_crt_url_builds_query():
    assert dd.crt_url("ajg.com") == "https://crt.sh/?q=%25.ajg.com&output=json"
    assert dd.crt_url("postholdings.com") == "https://crt.sh/?q=%25.postholdings.com&output=json"


def test_crt_url_refuses_bare_suffix_or_tld():
    assert dd.crt_url("co.uk") is None     # bare multi-label public suffix
    assert dd.crt_url("com") is None       # bare TLD
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/opt/homebrew/bin/python3 -m pytest tests/test_discover_domains.py::test_crt_url_builds_query -v`
Expected: FAIL with `AttributeError: module 'discover_domains' has no attribute 'crt_url'`

- [ ] **Step 3: Add the helper**

In `discover_domains.py`, add this function immediately **after** `parse_crt_json()` (before `_default_fetcher`):

```python
def crt_url(apex):
    """The crt.sh JSON URL for an apex, or None if the seed is a bare public suffix / TLD — which we
    refuse, because "%.com" would over-match every unrelated domain under that suffix."""
    reg = registrable_domain(apex)
    if "." not in reg or reg in _MULTI_SUFFIXES:
        return None
    return "https://crt.sh/?q=" + urllib.parse.quote("%." + apex) + "&output=json"
```

Note: `urllib.parse.quote("%." + apex)` encodes `%` → `%25`, so `crt_url("ajg.com")` is `https://crt.sh/?q=%25.ajg.com&output=json`. This is byte-identical to the URL the current code builds inline at the old line 88 — you are only extracting it.

- [ ] **Step 4: Run test to verify it passes**

Run: `/opt/homebrew/bin/python3 -m pytest tests/test_discover_domains.py::test_crt_url_builds_query tests/test_discover_domains.py::test_crt_url_refuses_bare_suffix_or_tld -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Use the helper in `enumerate_crt_with_status` (no behavior change yet)**

Replace the head of `enumerate_crt_with_status` — the inline refusal + URL build:

```python
    fetcher = fetcher or _default_fetcher
    reg = registrable_domain(apex)
    # Refuse a bare public suffix / TLD as the seed (e.g. "co.uk", "com") — it would over-match every
    # unrelated domain under that suffix.
    if "." not in reg or reg in _MULTI_SUFFIXES:
        return set(), "unreachable"
    url = "https://crt.sh/?q=" + urllib.parse.quote("%." + apex) + "&output=json"
```

with:

```python
    fetcher = fetcher or _default_fetcher
    reg = registrable_domain(apex)
    url = crt_url(apex)
    if url is None:  # bare public suffix / TLD seed — refused, never queried
        return set(), "unreachable"
```

- [ ] **Step 6: Run the full discover_domains test file to verify nothing regressed**

Run: `/opt/homebrew/bin/python3 -m pytest tests/test_discover_domains.py -v`
Expected: PASS — all tests, including `test_enumerate_crt_refuses_bare_suffix_or_tld_apex` (still returns `set()` for `co.uk`/`com`).

- [ ] **Step 7: Commit**

```bash
git add skills/owned-properties/scripts/discover_domains.py tests/test_discover_domains.py
git commit -m "refactor(owned-properties): extract crt_url() helper, DRY the bare-suffix refusal"
```

---

### Task 2: `_classify_fetch_error()` — split permanent blocks from transient flakiness

**Files:**
- Modify: `skills/owned-properties/scripts/discover_domains.py`
- Test: `tests/test_discover_domains.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_discover_domains.py`. Put this import at the top of the file (next to `import json`):

```python
import socket
import urllib.error
```

Then add:

```python
def test_classify_fetch_error_blocked_signals():
    # Forbidden / proxy-auth-required / unavailable-for-legal-reasons HTTP codes are permanent here.
    for code in (403, 407, 451):
        err = urllib.error.HTTPError("https://crt.sh/", code, "blocked", {}, None)
        assert dd._classify_fetch_error(err) == "blocked"
    # Proxy rejects the CONNECT tunnel (the exact sandbox symptom), raw and URLError-wrapped:
    assert dd._classify_fetch_error(OSError("Tunnel connection failed: 403 Forbidden")) == "blocked"
    assert dd._classify_fetch_error(
        urllib.error.URLError(OSError("Tunnel connection failed: 403 Forbidden"))) == "blocked"
    # DNS blackholed at egress:
    assert dd._classify_fetch_error(
        urllib.error.URLError(socket.gaierror(8, "nodename nor servname provided, or not known"))) == "blocked"


def test_classify_fetch_error_transient_signals():
    assert dd._classify_fetch_error(
        urllib.error.HTTPError("https://crt.sh/", 503, "Service Unavailable", {}, None)) == "transient"
    assert dd._classify_fetch_error(RuntimeError("503 Service Unavailable")) == "transient"
    assert dd._classify_fetch_error(socket.timeout("timed out")) == "transient"
    assert dd._classify_fetch_error(ConnectionResetError("connection reset by peer")) == "transient"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/opt/homebrew/bin/python3 -m pytest tests/test_discover_domains.py::test_classify_fetch_error_blocked_signals -v`
Expected: FAIL with `AttributeError: module 'discover_domains' has no attribute '_classify_fetch_error'`

- [ ] **Step 3: Add imports and the classifier**

At the top of `discover_domains.py`, add to the import block (keep alphabetical-ish with the existing `urllib.*` imports):

```python
import socket
import urllib.error
```

Add these constants right after the existing `CRT_BACKOFF = 2.0` line:

```python
# Fetch-failure signatures that mean a PERMANENT egress/policy block (retrying is futile) rather than
# crt.sh being flaky (503/timeout — worth a retry). Drives the "blocked" vs "unreachable" distinction.
_BLOCK_HTTP_CODES = {403, 407, 451}  # forbidden / proxy-auth-required / unavailable-for-legal-reasons
_BLOCK_PHRASES = (
    "tunnel connection failed", "after connect",       # proxy rejected the HTTPS CONNECT tunnel
    "name or service not known", "nodename nor servname",  # DNS blackholed at the egress allowlist
    "temporary failure in name resolution",
)
```

Add the function right after `parse_crt_json()`/`crt_url()` (before `_default_fetcher`):

```python
def _classify_fetch_error(exc):
    """'blocked' = a policy/egress block that will never clear on retry (403/407/451, a proxy CONNECT
    rejection, or a DNS blackhole); 'transient' = flaky/overloaded (503, timeout, reset) — retry.
    Unknown errors default to 'transient' so a retryable blip is never mistaken for a hard block."""
    if isinstance(exc, urllib.error.HTTPError) and exc.code in _BLOCK_HTTP_CODES:
        return "blocked"
    if isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, socket.gaierror):
        return "blocked"
    msg = str(getattr(exc, "reason", "") or exc).lower()
    if any(phrase in msg for phrase in _BLOCK_PHRASES):
        return "blocked"
    return "transient"
```

Why this is safe: `HTTPError` is a subclass of `URLError`, so the order matters — the code-based check runs first. A 503 `HTTPError` has a code not in `_BLOCK_HTTP_CODES` and a reason (`"Service Unavailable"`) with no block phrase → `transient`. `RuntimeError("503 ...")` is neither `HTTPError` nor `URLError`; its string has no block phrase → `transient`. This preserves the three existing transient/unreachable tests.

- [ ] **Step 4: Run tests to verify they pass**

Run: `/opt/homebrew/bin/python3 -m pytest tests/test_discover_domains.py::test_classify_fetch_error_blocked_signals tests/test_discover_domains.py::test_classify_fetch_error_transient_signals -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add skills/owned-properties/scripts/discover_domains.py tests/test_discover_domains.py
git commit -m "feat(owned-properties): classify fetch errors as blocked vs transient"
```

---

### Task 3: Wire the classifier into `enumerate_crt_with_status` — add `blocked`, fail fast

**Files:**
- Modify: `skills/owned-properties/scripts/discover_domains.py`
- Test: `tests/test_discover_domains.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_discover_domains.py`:

```python
def test_enumerate_crt_blocked_fails_fast(monkeypatch):
    # A policy block (e.g. 403 at the egress proxy) must NOT burn the retry budget: one call, then stop.
    monkeypatch.setattr(dd.time, "sleep", lambda s: (_ for _ in ()).throw(AssertionError("slept")))
    calls = {"n": 0}

    def blocked(url):
        calls["n"] += 1
        raise OSError("Tunnel connection failed: 403 Forbidden")

    hosts, status = dd.enumerate_crt_with_status("ajg.com", fetcher=blocked)
    assert hosts == set()
    assert status == "blocked"
    assert calls["n"] == 1                  # failed fast — did NOT retry CRT_ATTEMPTS times


def test_enumerate_crt_transient_still_retries_to_unreachable(monkeypatch):
    # A transient error keeps the existing behavior: retry CRT_ATTEMPTS times, end "unreachable".
    monkeypatch.setattr(dd.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def flaky(url):
        calls["n"] += 1
        raise RuntimeError("503 Service Unavailable")

    hosts, status = dd.enumerate_crt_with_status("ajg.com", fetcher=flaky)
    assert hosts == set()
    assert status == "unreachable"
    assert calls["n"] == dd.CRT_ATTEMPTS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/opt/homebrew/bin/python3 -m pytest tests/test_discover_domains.py::test_enumerate_crt_blocked_fails_fast -v`
Expected: FAIL — `assert 'unreachable' == 'blocked'` (today every failure is `unreachable`, and it retries 3×, which also trips the `sleep` AssertionError).

- [ ] **Step 3: Add the fail-fast block path to the retry loop**

In `enumerate_crt_with_status`, replace the retry loop:

```python
    text = ""
    for attempt in range(CRT_ATTEMPTS):  # crt.sh is flaky (503/empty); retry transient failures
        try:
            text = fetcher(url)
        except Exception:
            text = ""
        if text:
            break
        if attempt < CRT_ATTEMPTS - 1:
            time.sleep(CRT_BACKOFF * (attempt + 1))
    if not text:  # raised or empty on every attempt -> fetch failed, NOT a genuine zero
        return set(), "unreachable"
```

with:

```python
    text = ""
    for attempt in range(CRT_ATTEMPTS):  # crt.sh is flaky (503/empty); retry transient failures
        try:
            text = fetcher(url)
        except Exception as exc:  # noqa: BLE001 - classify below: a policy block is permanent
            text = ""
            if _classify_fetch_error(exc) == "blocked":
                # Permanent egress/policy block (e.g. 403 at an allowlisting proxy). Retrying is
                # futile, so fail fast — and report "blocked" so host_count:0 isn't read as a real 0.
                return set(), "blocked"
        if text:
            break
        if attempt < CRT_ATTEMPTS - 1:
            time.sleep(CRT_BACKOFF * (attempt + 1))
    if not text:  # raised or empty on every attempt -> fetch failed, NOT a genuine zero
        return set(), "unreachable"
```

Also extend the function's docstring `Returns (...)` paragraph to list the third state:

```python
    Returns (hosts:set, crt_status:str) where crt_status is one of:
      - "ok"          a body came back (even if it parsed to 0 hosts — a genuine no-cert apex);
      - "blocked"     a PERMANENT egress/policy block (e.g. 403 at an allowlisting proxy); we fail
                      fast, so host_count:0 is a LOST enumeration, never a real zero;
      - "unreachable" every attempt raised/returned empty after all retries (crt.sh flaky/down).
    A refused seed (bare public suffix / TLD) is "unreachable" — we never queried crt.sh.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/opt/homebrew/bin/python3 -m pytest tests/test_discover_domains.py -v`
Expected: PASS — the two new tests plus all existing ones (`test_enumerate_crt_network_failure_is_empty`, `test_discover_crt_status_unreachable_after_retries`, etc. still pass: `RuntimeError` classifies as transient).

- [ ] **Step 5: Commit**

```bash
git add skills/owned-properties/scripts/discover_domains.py tests/test_discover_domains.py
git commit -m "feat(owned-properties): report crt_status 'blocked' and fail fast on egress blocks"
```

---

### Task 4: Surface `blocked` through `discover()` (comment + contract test)

**Files:**
- Modify: `skills/owned-properties/scripts/discover_domains.py`
- Test: `tests/test_discover_domains.py`

`discover()` already returns whatever `crt_status` `enumerate_crt_with_status` produces, so `"blocked"` flows through with no code change. This task locks that contract with a test and updates the stale explanatory comment.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_discover_domains.py`:

```python
def test_discover_surfaces_blocked_status(monkeypatch):
    # A blocked CT fetch must surface crt_status "blocked" in the summary (host_count 0, but NOT a real 0).
    monkeypatch.setattr(dd.time, "sleep", lambda s: None)

    def blocked(url):
        raise urllib.error.HTTPError("https://crt.sh/", 403, "Forbidden", {}, None)

    summary, hosts = dd.discover("ajg.com", fetcher=blocked, whois_fn=lambda d: WHOIS_SAMPLE)
    assert summary["crt_status"] == "blocked"
    assert summary["host_count"] == 0
    assert hosts == []
```

- [ ] **Step 2: Run test to verify it passes immediately (no production change yet)**

Run: `/opt/homebrew/bin/python3 -m pytest tests/test_discover_domains.py::test_discover_surfaces_blocked_status -v`
Expected: PASS (the wiring from Task 3 already makes this true). If it FAILS, Task 3 was implemented wrong — stop and fix Task 3 before continuing.

- [ ] **Step 3: Update the stale explanatory comment in `discover()`**

In `discover()`, replace the comment above `"crt_status": crt_status,`:

```python
        # "ok" = crt.sh answered (0 hosts means genuinely no certs); "unreachable" = fetch failed
        # after retries, so host_count:0 is a LOST enumeration, not a real zero — flag & re-run.
        "crt_status": crt_status,
```

with:

```python
        # "ok" = crt.sh answered (0 hosts = genuinely no certs). "blocked" = permanent egress/policy
        # block; "unreachable" = flaky/down after retries. For BOTH non-ok states host_count:0 is a
        # LOST enumeration, not a real zero — flag the apex & recover via the two-step --crt-json path.
        "crt_status": crt_status,
```

- [ ] **Step 4: Run the test file to verify nothing regressed**

Run: `/opt/homebrew/bin/python3 -m pytest tests/test_discover_domains.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add skills/owned-properties/scripts/discover_domains.py tests/test_discover_domains.py
git commit -m "test(owned-properties): lock discover() surfacing of blocked status; refresh comment"
```

---

### Task 5: CLI — migrate `main()` to argparse and add `--print-crt-url`

**Files:**
- Modify: `skills/owned-properties/scripts/discover_domains.py`
- Test: `tests/test_discover_domains.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_discover_domains.py`:

```python
def test_cli_print_crt_url(monkeypatch, capsys):
    # --print-crt-url emits the URL and exits WITHOUT touching the network or WHOIS.
    monkeypatch.setattr(dd, "_default_fetcher",
                        lambda url: (_ for _ in ()).throw(AssertionError("fetched")))
    monkeypatch.setattr(dd, "_default_whois",
                        lambda d: (_ for _ in ()).throw(AssertionError("whois ran")))
    dd.main(["discover_domains.py", "ajg.com", "--print-crt-url"])
    out = capsys.readouterr().out.strip()
    assert out == "https://crt.sh/?q=%25.ajg.com&output=json"


def test_cli_print_crt_url_refuses_bare_suffix():
    import pytest
    with pytest.raises(SystemExit):
        dd.main(["discover_domains.py", "com", "--print-crt-url"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/opt/homebrew/bin/python3 -m pytest tests/test_discover_domains.py::test_cli_print_crt_url -v`
Expected: FAIL — current `main()` requires 3 args and has no `--print-crt-url`; it will `sys.exit("usage: ...")` or mis-parse.

- [ ] **Step 3: Add the import and rewrite `main()`**

At the top of `discover_domains.py`, add to the import block:

```python
import argparse
```

Replace the entire `main()` function:

```python
def main(argv):
    if len(argv) < 3:
        sys.exit("usage: discover_domains.py <apex> <out_hosts.json>")
    summary, hosts = discover(argv[1])
    pathlib.Path(argv[2]).write_text(json.dumps(
        {"registrable": summary["registrable"], "all_hosts": hosts}, indent=2))
    summary["all_hosts_file"] = argv[2]
    print(json.dumps(summary, indent=2))
```

with:

```python
def main(argv):
    ap = argparse.ArgumentParser(
        prog="discover_domains.py",
        description="Enumerate an apex's hostnames via Certificate Transparency (crt.sh) + WHOIS.")
    ap.add_argument("apex", nargs="?", help="seed apex, e.g. example.com")
    ap.add_argument("out_hosts", nargs="?", help="path to write the full hostnames JSON sidecar")
    ap.add_argument("--print-crt-url", action="store_true",
                    help="print the crt.sh URL for <apex> and exit; fetch it via your own egress, "
                         "then feed the saved JSON back with --crt-json")
    ap.add_argument("--crt-json", metavar="FILE",
                    help="parse a pre-fetched crt.sh JSON payload from FILE instead of the network "
                         "(use when direct egress to crt.sh is blocked)")
    args = ap.parse_args(argv[1:])

    if args.print_crt_url:
        if not args.apex:
            ap.error("--print-crt-url requires <apex>")
        url = crt_url(args.apex)
        if url is None:
            sys.exit(f"refusing bare public suffix / TLD as seed: {args.apex!r}")
        print(url)
        return

    if not args.apex or not args.out_hosts:
        ap.error("the following arguments are required: apex, out_hosts")

    summary, hosts = discover(args.apex)
    pathlib.Path(args.out_hosts).write_text(json.dumps(
        {"registrable": summary["registrable"], "all_hosts": hosts}, indent=2))
    summary["all_hosts_file"] = args.out_hosts
    print(json.dumps(summary, indent=2))
```

Note: `args = ap.parse_args(argv[1:])` — slice off the program name, because callers (and the existing test) pass the full `argv` with `argv[0]` as the script name. `--crt-json` is declared here but wired in Task 6; declaring it now keeps the argparse surface in one place.

- [ ] **Step 4: Run tests to verify they pass**

Run: `/opt/homebrew/bin/python3 -m pytest tests/test_discover_domains.py::test_cli_print_crt_url tests/test_discover_domains.py::test_cli_print_crt_url_refuses_bare_suffix tests/test_discover_domains.py::test_cli_main_writes_hosts_and_compact_summary -v`
Expected: PASS (3 passed) — including the **pre-existing** `test_cli_main_writes_hosts_and_compact_summary`, which proves the positional `main(["...", "ajg.com", out])` shape still works.

- [ ] **Step 5: Commit**

```bash
git add skills/owned-properties/scripts/discover_domains.py tests/test_discover_domains.py
git commit -m "feat(owned-properties): argparse CLI + --print-crt-url for two-step fetch"
```

---

### Task 6: CLI — `--crt-json` parse-only mode (no network)

**Files:**
- Modify: `skills/owned-properties/scripts/discover_domains.py`
- Test: `tests/test_discover_domains.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_discover_domains.py`:

```python
def test_cli_crt_json_parses_without_network(tmp_path, monkeypatch, capsys):
    # --crt-json feeds a pre-fetched payload; the network fetcher must NOT be called.
    monkeypatch.setattr(dd, "_default_fetcher",
                        lambda url: (_ for _ in ()).throw(AssertionError("hit the network")))
    monkeypatch.setattr(dd, "_default_whois", lambda d: WHOIS_SAMPLE)
    crt = tmp_path / "crt.json"
    crt.write_text(CRT_SAMPLE)
    out = tmp_path / "hosts.json"
    dd.main(["discover_domains.py", "ajg.com", str(out), "--crt-json", str(crt)])
    summary = json.loads(capsys.readouterr().out)
    assert summary["host_count"] == 3
    assert summary["crt_status"] == "ok"
    saved = json.loads(out.read_text())
    assert len(saved["all_hosts"]) == 3


def test_cli_crt_json_empty_file_errors(tmp_path):
    import pytest
    empty = tmp_path / "empty.json"
    empty.write_text("   \n")
    out = tmp_path / "hosts.json"
    with pytest.raises(SystemExit):
        dd.main(["discover_domains.py", "ajg.com", str(out), "--crt-json", str(empty)])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/opt/homebrew/bin/python3 -m pytest tests/test_discover_domains.py::test_cli_crt_json_parses_without_network -v`
Expected: FAIL with `AssertionError: hit the network` (Task 5 declared `--crt-json` but `discover()` is still called with the default urllib fetcher).

- [ ] **Step 3: Wire `--crt-json` into `main()`**

In `main()`, replace the block:

```python
    if not args.apex or not args.out_hosts:
        ap.error("the following arguments are required: apex, out_hosts")

    summary, hosts = discover(args.apex)
```

with:

```python
    if not args.apex or not args.out_hosts:
        ap.error("the following arguments are required: apex, out_hosts")

    fetcher = None
    if args.crt_json:
        try:
            crt_text = pathlib.Path(args.crt_json).read_text()
        except OSError as e:
            sys.exit(f"could not read --crt-json file {args.crt_json!r}: {e}")
        if not crt_text.strip():
            sys.exit(f"--crt-json file is empty: {args.crt_json!r} — fetch the URL from "
                     "--print-crt-url first, then pass the saved JSON here")
        fetcher = lambda _url: crt_text  # noqa: E731 - parse-only: feed the pre-fetched body, no net

    summary, hosts = discover(args.apex, fetcher=fetcher)
```

Why this works: passing the body through the existing `fetcher` seam means `enumerate_crt_with_status` parses `crt_text` and returns `("ok", hosts)` for a non-empty valid payload — no network, no new code path. The empty-file guard prevents the injected fetcher from returning `""` (which would otherwise spin the retry loop and end as a misleading `unreachable`). WHOIS still runs as before; in a blocked environment it degrades to `None` gracefully (out of scope here).

- [ ] **Step 4: Run tests to verify they pass**

Run: `/opt/homebrew/bin/python3 -m pytest tests/test_discover_domains.py::test_cli_crt_json_parses_without_network tests/test_discover_domains.py::test_cli_crt_json_empty_file_errors -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add skills/owned-properties/scripts/discover_domains.py tests/test_discover_domains.py
git commit -m "feat(owned-properties): --crt-json parse-only mode (agent-supplied payload, no network)"
```

---

### Task 7: CLI — print a remediation hint to stderr when `blocked`

**Files:**
- Modify: `skills/owned-properties/scripts/discover_domains.py`
- Test: `tests/test_discover_domains.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_discover_domains.py`:

```python
def test_cli_blocked_prints_remediation(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(dd.time, "sleep", lambda s: None)
    monkeypatch.setattr(dd, "_default_whois", lambda d: WHOIS_SAMPLE)

    def blocked(url):
        raise OSError("Tunnel connection failed: 403 Forbidden")

    monkeypatch.setattr(dd, "_default_fetcher", blocked)
    out = tmp_path / "hosts.json"
    dd.main(["discover_domains.py", "ajg.com", str(out)])
    captured = capsys.readouterr()
    summary = json.loads(captured.out)
    assert summary["crt_status"] == "blocked"
    # The remediation hint goes to stderr and names the two-step recovery flags.
    assert "blocked" in captured.err
    assert "--print-crt-url" in captured.err
    assert "--crt-json" in captured.err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/opt/homebrew/bin/python3 -m pytest tests/test_discover_domains.py::test_cli_blocked_prints_remediation -v`
Expected: FAIL on `assert "blocked" in captured.err` — `main()` prints the summary but no stderr hint yet.

- [ ] **Step 3: Append the remediation hint to `main()`**

At the **end** of `main()`, after `print(json.dumps(summary, indent=2))`, add:

```python
    if summary["crt_status"] == "blocked":
        print(
            f"\ncrt_status: blocked — crt.sh egress is policy-blocked here (e.g. HTTP 403 at an "
            f"allowlisting proxy). host_count:0 is NOT a real zero. Recover subdomains two-step:\n"
            f"  1) discover_domains.py {args.apex} --print-crt-url            # prints the crt.sh URL\n"
            f"  2) fetch that URL with your web tool and save the JSON, then:\n"
            f"  3) discover_domains.py {args.apex} {args.out_hosts} --crt-json <saved.json>",
            file=sys.stderr)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/opt/homebrew/bin/python3 -m pytest tests/test_discover_domains.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add skills/owned-properties/scripts/discover_domains.py tests/test_discover_domains.py
git commit -m "feat(owned-properties): print blocked-status remediation hint to stderr"
```

---

### Task 8: Update SKILL.md — document the three states + the two-step recovery

**Files:**
- Modify: `skills/owned-properties/SKILL.md`

No automated test (docs). Verify by reading the diff and grepping for the new terms.

- [ ] **Step 1: Extend the coverage-ceiling callout**

In `SKILL.md`, find the blockquote line:

```
> it for re-run; don't present it as a complete 0-host apex.
```

(it currently begins `> If `crt_status` is `unreachable` for an apex, that apex's enumeration is incomplete — flag`). Replace `If \`crt_status\` is \`unreachable\` for an apex` with:

```
> If `crt_status` is `unreachable` **or `blocked`** for an apex
```

- [ ] **Step 2: Rewrite the Step-2 `crt_status` explanation**

Replace this paragraph in Step 2:

```
   It prints a compact summary (registrable domain, WHOIS registrant, host_count, sample_hosts,
   `all_hosts_file`, and **`crt_status`**). Note the registrant — it confirms ownership of that apex.
   **Check `crt_status`:** `"ok"` means crt.sh answered (so `host_count: 0` is a genuine no-cert
   apex); **`"unreachable"`** means the crt.sh fetch failed after all retries, so a `host_count: 0`
   here is a LOST enumeration, not a real zero. If `crt_status` is `unreachable` for an apex, FLAG
   that apex in the workbook (Notes) and in chat as **"enumeration incomplete — re-run"** — do NOT
   report it as a complete 0-host apex, and do NOT pass its (missing) subdomains downstream.
```

with:

```
   It prints a compact summary (registrable domain, WHOIS registrant, host_count, sample_hosts,
   `all_hosts_file`, and **`crt_status`**). Note the registrant — it confirms ownership of that apex.
   **Check `crt_status`** — one of three states:
   - `"ok"` — crt.sh answered, so `host_count: 0` is a genuine no-cert apex.
   - `"unreachable"` — the fetch failed after all retries (crt.sh flaky/down); `host_count: 0` is a
     LOST enumeration, not a real zero.
   - `"blocked"` — a permanent egress/policy block (e.g. HTTP 403 at an allowlisting proxy, common in
     sandboxed runtimes); the script fails fast. `host_count: 0` is a LOST enumeration, not a zero.

   For **`unreachable`** or **`blocked`**, FLAG that apex in the workbook (Notes) and in chat as
   **"enumeration incomplete — re-run"** — never report it as a complete 0-host apex, and never pass
   its (missing) subdomains downstream.

   **Two-step recovery when direct egress is blocked.** If your runtime blocks the script's own
   network but you have a sanctioned web-fetch tool, fetch crt.sh yourself and feed it back:
   ```bash
   python3 "$SKILL/scripts/discover_domains.py" <apex> --print-crt-url    # prints the crt.sh URL
   # fetch that URL with your web tool, save the JSON to /tmp/<apex>-crt.json, then:
   python3 "$SKILL/scripts/discover_domains.py" <apex> /tmp/<apex>-hosts.json --crt-json /tmp/<apex>-crt.json
   ```
   The second call parses your saved payload with no network access. (If crt.sh is off your web
   tool's allowlist too, fall back to EDGAR Exhibit-21 + brand-page research per Step 3.)
```

- [ ] **Step 3: Update the red-flag table row**

Replace the table row:

```
| "host_count is 0, so this apex has no subdomains." | Only if `crt_status` is `ok`. If `unreachable`, that's a LOST enumeration — flag "enumeration incomplete — re-run", don't report it as a complete 0. |
```

with:

```
| "host_count is 0, so this apex has no subdomains." | Only if `crt_status` is `ok`. If `unreachable` or `blocked`, that's a LOST enumeration — flag "enumeration incomplete — re-run" (and try the `--print-crt-url`/`--crt-json` two-step), don't report it as a complete 0. |
```

- [ ] **Step 4: Verify the doc edits landed**

Run: `grep -n "blocked\|--print-crt-url\|--crt-json" skills/owned-properties/SKILL.md`
Expected: matches in the coverage callout, Step 2 (three states + two-step block), and the red-flag row.

- [ ] **Step 5: Commit**

```bash
git add skills/owned-properties/SKILL.md
git commit -m "docs(owned-properties): document blocked status + --print-crt-url/--crt-json two-step recovery"
```

---

### Task 9: Full-suite verification + version bump

**Files:**
- Modify: `.claude-plugin/marketplace.json` and/or the plugin manifest carrying the version (find it — see Step 2).

- [ ] **Step 1: Run the entire test suite**

Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q`
Expected: PASS — **244 prior + 12 new = 256 passing** (Task 1: 2, Task 2: 2, Task 3: 2, Task 4: 1, Task 5: 2, Task 6: 2, Task 7: 1). If the count differs, reconcile before continuing. Do NOT pipe through `| tail` inside an `&&` chain (per CLAUDE.md — it masks a missing-pytest failure).

- [ ] **Step 2: Bump the plugin version**

Find the current version: `grep -rn "\"version\"" .claude-plugin/ plugin.json 2>/dev/null | head`. Bump the patch/minor per the repo's convention (recent history bumped `0.13.2 → 0.14.0` for a feature; this is a feature-level change → bump the minor, e.g. `0.14.0 → 0.15.0`). Edit the version string in the file that holds it.

- [ ] **Step 3: Commit the bump**

```bash
git add -A
git commit -m "chore: bump plugin to <new-version> (owned-properties crt.sh egress portability)"
```

---

## Self-Review (completed during planning)

- **Spec coverage** (scope = "Core portability"): two-step decoupled fetch → Tasks 5 (`--print-crt-url`) + 6 (`--crt-json`); distinct `blocked` status → Tasks 2 + 3; remediation line → Task 7; SKILL.md guidance → Task 8. The deferred provider-chain / RDAP / EDGAR items are explicitly listed under "Out of scope". ✓
- **Type/signature consistency:** `crt_url(apex)→str|None` used identically in `enumerate_crt_with_status` (Task 1) and `main()` (Task 5). `_classify_fetch_error(exc)→"blocked"|"transient"` defined in Task 2, consumed in Task 3. `crt_status` enum is `"ok"|"unreachable"|"blocked"` across Tasks 3, 4, 7, 8. `enumerate_crt_with_status` keeps its 2-tuple return throughout. ✓
- **Placeholder scan:** every code/doc step shows the literal before/after text; no TBD/“handle errors”/“similar to”. ✓
- **Backward-compat:** the pre-existing `test_cli_main_writes_hosts_and_compact_summary` and the three transient/unreachable tests are explicitly re-run in Tasks 5 and 3 to prove no regression. ✓
