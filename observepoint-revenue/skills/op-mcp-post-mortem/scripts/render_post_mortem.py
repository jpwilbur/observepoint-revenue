"""Render a standardized OP MCP post-mortem from a facts JSON (deterministic, no network, no LLM).

Claude gathers and judges the facts (assembling the JSON); this script owns the *document* — one
fixed structure for every submitter, with every required section present, plus a blank maintainer
skeleton for remediation. Keeping the layout here (not in the model) is why two post-mortems written
months apart look identical and a maintainer always finds the same headings.

It validates first and **fails loudly**: a missing or empty required field, an unknown severity, or
an incomplete reproduction that doesn't say what's missing all exit non-zero with the full list of
problems — a half-filled post-mortem never silently renders.

Facts JSON shape (see references/post-mortem-template.md for the annotated version):
  {
    "date": "2026-06-25", "mcp_version": "0.6.40", "reporter": "name <email>",
    "severity": "Low|Medium|High|Critical",          # must be confirmed with the user, not invented
    "summary": "...", "impact": "...",
    "client": "Claude Desktop|Claude Code|...", "account_context": "...",
    "tools": [{"name": "mcp__ObservePoint__get_audit_runs", "params": {...}}],
    "observed": "...", "expected": "...",
    "reproduction": {"complete": true|false, "account_id": "...",
                     "resources": [{"type": "audit", "id": "90233"}],
                     "config_snapshot": "...", "notes": "what's missing if complete=false"},
    "evidence": "redacted tool-call / response excerpts",
    "redaction_notes": "what was redacted; the user's share/no-share decision",
    "status": "Submitted"                              # optional; defaults to Submitted
  }

CLI:
  render_post_mortem.py facts.json                 print markdown to stdout
  render_post_mortem.py facts.json --out <path>    write to <path> (parent dirs created)
  cat facts.json | render_post_mortem.py           reads stdin when no file given
"""
import argparse
import json
import os
import sys

SEVERITIES = {"Low", "Medium", "High", "Critical"}
_REQUIRED = ["date", "mcp_version", "reporter", "severity", "summary", "impact",
             "client", "account_context", "tools", "observed", "expected",
             "reproduction", "evidence", "redaction_notes"]


def validate(facts):
    """Return a list of human-readable problems (empty list == valid)."""
    problems = []
    for key in _REQUIRED:
        val = facts.get(key)
        if val is None or (isinstance(val, str) and not val.strip()) or val == [] or val == {}:
            problems.append(f"missing/empty required field: {key!r}")

    sev = facts.get("severity")
    if sev is not None and sev not in SEVERITIES:
        problems.append(f"severity {sev!r} is not one of {sorted(SEVERITIES)}")

    tools = facts.get("tools")
    if isinstance(tools, list):
        for i, t in enumerate(tools):
            if not isinstance(t, dict) or not str(t.get("name", "")).strip():
                problems.append(f"tools[{i}] must be an object with a non-empty 'name'")
    elif tools is not None:
        problems.append("'tools' must be a list")

    repro = facts.get("reproduction")
    if isinstance(repro, dict):
        if "complete" not in repro or not isinstance(repro["complete"], bool):
            problems.append("reproduction.complete must be present and boolean")
        elif repro["complete"] is False and not str(repro.get("notes", "")).strip():
            problems.append("reproduction.complete is false — 'notes' must say what is missing "
                            "(an incomplete repro must be flagged, never left blank)")
    elif repro is not None:
        problems.append("'reproduction' must be an object")
    return problems


def _params_block(params):
    if params in (None, "", {}, []):
        return "_(none recorded)_"
    if isinstance(params, str):
        return f"`{params}`"
    return "```json\n" + json.dumps(params, indent=2) + "\n```"


def _repro_block(repro):
    lines = []
    flag = "complete" if repro.get("complete") else "INCOMPLETE — re-run / gather more before relying on it"
    lines.append(f"**Status:** {flag}")
    if repro.get("account_id"):
        lines.append(f"**Account:** {repro['account_id']}")
    resources = repro.get("resources") or []
    if resources:
        lines.append("**Resources to recreate:**")
        for r in resources:
            lines.append(f"- {r.get('type', 'resource')} `{r.get('id', '?')}`")
    if repro.get("config_snapshot"):
        lines.append("\n**Config snapshot:**\n```\n" + str(repro["config_snapshot"]).strip() + "\n```")
    if repro.get("notes"):
        lines.append(f"\n_Notes: {repro['notes']}_")
    return "\n".join(lines)


_MAINTAINER_SKELETON = """\
## Maintainer section

_Filled in by the maintainer (run `op-mcp-post-mortem remediate <this file>`). Leave blank until then._

- **Classification:** _real MCP bug / misleading tool description / ObservePoint API issue / not a defect_ —
- **Reproduction result:** _recreated in test account & confirmed / could not reproduce / …_ —
- **Root cause:** —
- **Fix (commit / PR):** —
- **Verification evidence:** _`npm run build` + smoke output_ —
- **Resolution & version:** _Fixed in observepoint-mcp vX.Y.Z / Rejected / Escalated_ —
"""


def render(facts):
    title = facts.get("title") or "OP MCP post-mortem"
    status = facts.get("status") or "Submitted"
    tools_md = "\n\n".join(
        f"**`{t['name']}`** — parameters:\n\n{_params_block(t.get('params'))}" for t in facts["tools"])
    return f"""\
# {title}

| | |
|---|---|
| **Date** | {facts['date']} |
| **MCP version** | {facts['mcp_version']} |
| **Reporter** | {facts['reporter']} |
| **Severity** | {facts['severity']} |
| **Status** | {status} |

## Summary

{facts['summary']}

## Severity & impact

**{facts['severity']}.** {facts['impact']}

## Environment

- **Client:** {facts['client']}
- **Account context:** {facts['account_context']}
- **MCP version:** {facts['mcp_version']}

## Tools involved

{tools_md}

## What happened vs. expected

**Observed:**

{facts['observed']}

**Expected:**

{facts['expected']}

## Reproduction config

{_repro_block(facts['reproduction'])}

## Conversation evidence

{facts['evidence']}

## Sharing & redaction notes

{facts['redaction_notes']}

---

{_MAINTAINER_SKELETON}"""


def main(argv):
    ap = argparse.ArgumentParser(description="Render a standardized OP MCP post-mortem.")
    ap.add_argument("file", nargs="?", help="facts JSON file; reads stdin if omitted")
    ap.add_argument("--out", help="write to this path (parent dirs created) instead of stdout")
    args = ap.parse_args(argv[1:])

    raw = open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read()
    try:
        facts = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f"render_post_mortem: facts are not valid JSON ({e})")

    problems = validate(facts)
    if problems:
        sys.exit("render_post_mortem: cannot render — fix these first:\n  - " + "\n  - ".join(problems))

    md = render(facts)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(md)
        print(f"render_post_mortem: wrote {args.out}")
    else:
        sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
