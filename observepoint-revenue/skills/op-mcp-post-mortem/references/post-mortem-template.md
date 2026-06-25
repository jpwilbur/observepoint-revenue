# Post-mortem template & facts-JSON reference

The post-mortem is rendered deterministically by `scripts/render_post_mortem.py` from a **facts
JSON** that Claude assembles in submitter mode. This file documents that JSON, what each field is
for, and what the rendered document looks like. The renderer validates the JSON and **fails loudly**
on a missing/empty required field, an unknown severity, or an incomplete reproduction with no notes.

## Facts JSON

```json
{
  "title": "OP MCP: get_audit_runs returns a stale run as latest",
  "date": "2026-06-25",
  "mcp_version": "0.6.40",
  "reporter": "Jarrod Wilbur <jarrod.wilbur@observepoint.com>",
  "severity": "Medium",
  "summary": "Two or three sentences: what broke, while doing what.",
  "impact": "What it blocked or what wrong decision it risked.",
  "client": "Claude Desktop",
  "account_context": "Redaction-safe description of the account, e.g. 'enterprise account [redacted]'.",
  "tools": [
    {"name": "mcp__ObservePoint__get_audit_runs", "params": {"auditId": 90233, "limit": 5}}
  ],
  "observed": "What actually happened — the error, the wrong output, the hang.",
  "expected": "What should have happened.",
  "reproduction": {
    "complete": false,
    "account_id": "[redacted — shareable on request]",
    "resources": [{"type": "audit", "id": "90233"}],
    "config_snapshot": "Optional: exported config of the resources, redaction-safe.",
    "notes": "Required when complete=false: say exactly what's missing for a clean repro."
  },
  "evidence": "Minimal, REDACTED tool-call / response excerpts that show the failure.",
  "redaction_notes": "What was redacted and the user's share / no-share decision.",
  "status": "Submitted"
}
```

### Field notes

| Field | Required | Notes |
|---|---|---|
| `date`, `mcp_version`, `reporter` | yes | Facts. `mcp_version` from `manifest.json`/`whoami`; `"unknown"` if truly not visible. |
| `severity` | yes | One of `Low` / `Medium` / `High` / `Critical`. **Confirm with the user — never assign it yourself.** |
| `summary`, `impact` | yes | Plain language; no fabricated root cause. |
| `client`, `account_context` | yes | `account_context` must be redaction-safe. |
| `tools` | yes | Non-empty list; each needs a real `name`. `params` is rendered as a JSON block; redact secrets inside it. |
| `observed`, `expected` | yes | Keep observed (fact) separate from any hypothesis. Hypotheses, if any, belong in `summary`/`evidence`, clearly labelled as such. |
| `reproduction` | yes | `complete` must be a boolean. If `false`, `notes` must say what's missing — an incomplete repro is flagged, never silent. |
| `evidence` | yes | Already redacted. Run `scan_secrets.py --redact` over the raw excerpts first. |
| `redaction_notes` | yes | What you removed + the share decision. |
| `title`, `status` | no | Default `"OP MCP post-mortem"` and `"Submitted"`. |

## Rendered document structure

1. **Title + metadata table** — date, MCP version, reporter, severity, status.
2. **Summary**
3. **Severity & impact**
4. **Environment** — client, account context, MCP version.
5. **Tools involved** — tool name(s) + parameters.
6. **What happened vs. expected**
7. **Reproduction config** — status (flagged INCOMPLETE if so), account, resources to recreate,
   config snapshot, notes.
8. **Conversation evidence** — redacted excerpts.
9. **Sharing & redaction notes**
10. **Maintainer section** — a fixed blank skeleton, filled in maintainer mode:
    - Classification (real MCP bug / misleading tool description / ObservePoint API issue / not a defect)
    - Reproduction result (recreated in test account & confirmed / could not reproduce / …)
    - Root cause
    - Fix (commit / PR)
    - Verification evidence (`npm run build` + smoke output)
    - Resolution & version (Fixed in `observepoint-mcp` vX.Y.Z / Rejected / Escalated)
