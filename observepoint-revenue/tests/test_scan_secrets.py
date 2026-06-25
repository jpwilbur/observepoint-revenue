# tests/test_scan_secrets.py
import json, subprocess, sys, pathlib
import scan_secrets as ss

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "op-mcp-post-mortem" / "scripts" / "scan_secrets.py"

JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4"


def cats(text):
    return {f["category"] for f in ss.scan(text)}


def test_detects_op_api_key():
    assert "op_api_key" in cats("apiKey: op_live_sk_8f34b9c2a1e7d6f5d0")


def test_detects_jwt():
    assert "jwt" in cats(f"token was {JWT} here")


def test_detects_bearer_non_jwt():
    assert "bearer_token" in cats("Bearer abc12345defghi")


def test_detects_cookie_header_and_known_cookie():
    assert "cookie_header" in cats("Cookie: sessionid=abc; OptanonConsent=isGpcEnabled=0")
    assert "known_cookie" in cats("some line with sessionid=abc123def here")


def test_detects_email_pii():
    assert "email" in cats("account owner dana.kim@acme-corp.com")


def test_detects_secret_field():
    assert "secret_field" in cats('"password": "hunter2value"')


def test_clean_text_has_no_findings():
    # IDs and dates are not secrets — must not false-positive (would over-redact real content).
    assert ss.scan("audit 90233 run #771 returned the wrong run on June 24 2026") == []


def test_redact_output_rescans_clean():
    # The render backstop re-scans a file whose secrets were already redacted; the [REDACTED] tokens
    # must not re-flag, or "comes back clean" is meaningless.
    raw = ('apiKey: "op_live_sk_abc123def456"\n'
           f'Authorization: Bearer {JWT}\n'
           'Cookie: sessionid=abc123; OptanonConsent=isGpcEnabled=0')
    assert ss.scan(ss.redact(raw)) == []


def test_dedup_prefers_jwt_over_bearer():
    c = cats(f"Authorization: Bearer {JWT}")
    assert "jwt" in c and "bearer_token" not in c


def test_redact_replaces_secrets_and_pii():
    red = ss.redact(f"Bearer {JWT} and dana.kim@acme-corp.com")
    assert JWT not in red and "dana.kim@acme-corp.com" not in red
    assert "[REDACTED:" in red


def test_findings_report_line_numbers():
    findings = ss.scan("clean line\napiKey op_live_sk_abc123def\n")
    assert findings and findings[0]["line"] == 2


def test_cli_exit_2_and_names_category_on_findings(tmp_path):
    f = tmp_path / "pm.md"
    f.write_text("key op_live_sk_abc123def456")
    r = subprocess.run([sys.executable, str(SCRIPT), str(f)], capture_output=True, text=True)
    assert r.returncode == 2 and "op_api_key" in r.stdout


def test_cli_exit_0_when_clean(tmp_path):
    f = tmp_path / "pm.md"
    f.write_text("just audit 90233 numbers and a date")
    r = subprocess.run([sys.executable, str(SCRIPT), str(f)], capture_output=True, text=True)
    assert r.returncode == 0 and "clean" in r.stdout


def test_cli_json_count(tmp_path):
    f = tmp_path / "pm.md"
    f.write_text("dana.kim@acme-corp.com")
    r = subprocess.run([sys.executable, str(SCRIPT), str(f), "--json"], capture_output=True, text=True)
    assert json.loads(r.stdout)["count"] == 1
