# Spec: `op-mcp-post-mortem` skill (report & remediate OP MCP defects)

**Plugin:** `observepoint-revenue` (sibling of `scope-calculator`, `research-account`,
`owned-properties`, `find-accounts`, `branding-guide`).
**Status:** approved design. **Date:** 2026-06-25.

---

## 1. Goal & intent

Power users of the ObservePoint MCP server (largely the SC/revenue team, who already run this
plugin) hit cases where the MCP misbehaves mid-conversation — a tool errors, returns wrong or
misleading data, hangs, or a tool description leads Claude to use it incorrectly. Today that
knowledge evaporates when the conversation ends. This skill captures it while the context is still
live, in a form the MCP maintainer can act on.

It is a deliberate **outlier** in a revenue plugin: it is about **the MCP server itself being
broken**, not about selling. Its description must route cleanly so it never false-triggers on sales
work.

The skill has **two modes** sharing one artifact — a standardized post-mortem markdown file:

- **Submitter mode** (default) — a power user runs it right after a rough session; it produces the
  post-mortem file, which they send to the maintainer however they already communicate.
- **Maintainer mode** (`remediate <file>`) — the maintainer runs it on a received post-mortem to
  triage, reproduce, fix, verify, and close the loop.

**Success:** an accurate, self-contained, redaction-safe post-mortem that a maintainer can act on
without the original conversation; and a disciplined remediation path that refuses to "fix"
anything not proven to be a real MCP defect.

**Non-goals (YAGNI):** no automatic transport (no Slack/Drive/GitHub integration — user sends the
file); no telemetry; no attempt to fix the live ObservePoint platform/API (out of MCP scope — that
is an escalation, not a code fix).

---

## 2. Architecture & data flow

Mirrors the plugin's principle — **Claude gathers and judges → deterministic Python scripts compute
and render.** No LLM-authored file structure, no LLM math.

**Submitter mode:**

1. **Claude judges** — mines the live conversation for facts, classifies the failure, decides
   severity, and makes redaction calls. These are judgment tasks only Claude (with the conversation
   in context) can do.
2. **`scan_secrets.py` (deterministic)** — regex scanner over the gathered text for secrets/PII
   (auth tokens, API keys/bearer tokens, cookie values, emails, anything that looks like an account
   credential). Returns structured findings so Claude can confirm redactions before anything is
   written. Runs again on the final rendered file as a backstop.
3. **`render_post_mortem.py` (deterministic)** — takes a structured **facts JSON** (assembled by
   Claude) → renders the standardized post-mortem markdown **and validates** that every required
   section is present and non-empty. Guarantees identical structure across every submitter and keeps
   the document format out of the model's hands. Exits non-zero with a clear message if a required
   field is missing.

**Maintainer mode** is orchestration + judgment with no math, so it needs no new scripts. It reads
the post-mortem and drives existing discipline skills and the MCP repo's own build/test tooling.

Scripts live in `skills/op-mcp-post-mortem/scripts/`, get pytest coverage in
`observepoint-revenue/tests/`, run via `/opt/homebrew/bin/python3`, and their dir is added to
`tests/conftest.py` sys.path (house convention). Scripts use **stdlib only** (regex + json) — no new
dependencies.

---

## 3. Entry & routing

- Invoked as `/observepoint-revenue:op-mcp-post-mortem`.
- **No argument / "report this / something went wrong with the MCP"** → submitter mode.
- **`remediate <path>` (or an existing post-mortem path is supplied)** → maintainer mode.
- If ambiguous, Claude asks once which mode is intended. The branching logic stays **out of the
  description** (so the model reads the body rather than following a workflow summary).

---

## 4. Submitter mode workflow

1. **Auto-extract from the conversation** (no questions yet):
   - Exact MCP tool name(s) involved (e.g. `mcp__ObservePoint__get_audit_runs`) and the parameters
     passed.
   - The observed failure: error text, wrong/misleading output, hang/timeout, or a
     used-the-tool-wrong-because-the-description-was-unclear pattern.
   - What Claude did vs. what the user was trying to accomplish.
   - Environment: MCP version (from `manifest.json`/`whoami` if visible), account context.
2. **Capture reproduction config** — the account ID and the specific resource IDs involved
   (audit / journey / rule / report / consent-category), plus a config snapshot of those resources
   pulled via the MCP's own describe/get tools where available (`get_audit`, `get_journey`,
   `get_rule`, `bulk_describe`, `query_audit_configs`, …). This is what lets the maintainer recreate
   the setup in a **test account** instead of touching the reporter's account. Capture IDs even when
   a full snapshot isn't possible.
3. **Confirm only the gaps** — ask the user (concise, batched):
   - Expected behavior (what should have happened).
   - Severity / impact (blocks work / wrong data risked a decision / annoyance).
   - "Can these specifics be shared?" — green-light for IDs and config in the file.
4. **Redaction gate** — run `scan_secrets.py`; surface every finding; redact or confirm-keep each
   before writing. The file leaves the user's machine, so default to redacting secrets and PII.
   Never present a flagged file as clean.
5. **Render & write** — assemble the facts JSON, run `render_post_mortem.py` to produce the file at
   `~/Documents/ObservePoint Revenue/MCP Post-Mortems/<YYYY-MM-DD-short-slug>/post-mortem.md`
   (rep override honored; `mkdir -p`; never a temp dir). Re-scan the rendered file.
6. **Hand-off** — tell the user the path and that they should send the file to the maintainer
   (whoever can push MCP code) however they normally communicate.

**Honesty discipline (house style):** never fabricate a tool name, parameter, ID, error string, or
version. Unknown → labeled "unknown / not captured", never invented. An incomplete repro is flagged
as incomplete, not presented as complete.

---

## 5. Post-mortem file format (the contract)

Rendered by `render_post_mortem.py` from the facts JSON. Required sections (validated):

1. **Title & metadata** — date, MCP version, reporter, severity, status (`Submitted`).
2. **Summary** — 2–3 sentences: what broke, doing what.
3. **Severity & impact** — severity tier + what it blocked/risked.
4. **Environment** — MCP version, client (Claude Desktop / Code), account context (redaction-safe).
5. **Tools involved** — tool name(s) + the parameters passed (redacted as needed).
6. **What happened vs. expected** — observed behavior (error/output) and expected behavior.
7. **Reproduction config** — account + resource IDs and the config snapshot needed to recreate the
   scenario in a test account; explicitly flagged if incomplete.
8. **Conversation evidence** — minimal redacted tool-call/response excerpts that show the failure.
9. **Sharing & redaction notes** — what was redacted, and the user's share/no-share decision.
10. **Maintainer section** — left blank with a fixed skeleton for maintainer mode to fill:
    Classification · Reproduction result · Root cause · Fix + commit/PR · Verification evidence ·
    Resolution & version.

---

## 6. Maintainer mode workflow (gated)

Operates on the **OP MCP server repo** (the `observepoint-mcp` project; path supplied by the
maintainer — not hardcoded). Reads the post-mortem, then enforces these gates in order:

1. **Triage & classify** — reproduce-or-reason the report into exactly one of:
   - real MCP bug (code defect),
   - misleading/insufficient tool description (still an MCP fix, different remedy),
   - ObservePoint API/platform issue (escalate — not an MCP code fix),
   - not-our-problem (user/model error, expected behavior).
   **Explicit reject path:** if it isn't an MCP defect, record the classification + reason in the
   maintainer section and stop. Do not fix non-defects.
2. **Reproduce before fixing** — required confirmed repro before any code change:
   - **Preferred:** recreate the captured config in a **clean/test ObservePoint account**, reproduce
     the failure there, and **tear the config down afterward**.
   - **Fallback only if recreation is impossible:** ask the reporter for permission to test in the
     account where it happened. Avoid this path when you can.
   - No reproduction → no fix (escalate back to the reporter for more detail).
3. **Fix** — `systematic-debugging` for root cause, then `test-driven-development`: write a failing
   test that captures the defect first, then the minimal fix.
4. **Verify** — `npm run build` + the `scripts/*-smoke.mjs` smoke tests; gated by
   `verification-before-completion`. No "fixed" claim without green output pasted into the post-mortem.
5. **Close the loop** — fill the maintainer section (classification, repro result, root cause, fix +
   commit/PR, verification evidence), set status to `Fixed`/`Rejected`/`Escalated`, and bump
   `observepoint-mcp/package.json` for a real fix.

---

## 7. Testing plan

- **Skill behavior (writing-skills TDD):** baseline-test both modes on fresh subagents **without**
  the skill, document failures, write the skill to fix them, re-test with it. Focus on judgment
  gates: submitter redaction + no-fabrication + repro-config capture; maintainer triage
  classification (esp. the reject path) and the recreate-in-test-account-then-clean-up discipline.
- **Scripts (pytest):** `scan_secrets.py` (detects tokens/keys/cookies/emails; no false "clean" on a
  planted secret; handles empty input) and `render_post_mortem.py` (renders all sections; **fails
  loudly on a missing required field**; deterministic output). Wire `scripts/` into
  `tests/conftest.py`; run `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q`.

---

## 8. Discovery (frontmatter)

- **Name:** `op-mcp-post-mortem`.
- **Description (draft, triggers only — no workflow summary, routes away from sales skills):**
  > Use when the ObservePoint MCP server itself misbehaves in a conversation — a tool errors, returns
  > wrong or misleading data, hangs, or a tool description led Claude to use it incorrectly — and you
  > want to report it; or when remediating a received OP MCP post-mortem (triage, reproduce, fix,
  > verify). Keywords: ObservePoint MCP, MCP tool failed, wrong/misleading output, bug report,
  > post-mortem, remediate. Not for ObservePoint sales/scoping/research work (see the other
  > observepoint-revenue skills) and not for issues with the ObservePoint web app itself.

---

## 9. Deployment (separate from runtime)

- Add the skill to the plugin description in `observepoint-revenue/.claude-plugin/plugin.json` and
  the root `.claude-plugin/marketplace.json`; add it to the CLAUDE.md skills list.
- Bump `observepoint-revenue/.claude-plugin/plugin.json` `version`; the Drive release runs via the
  `main` git hook per `RELEASE.md`.
- **Two distinct version bumps:** the plugin version (shipping this skill) vs.
  `observepoint-mcp/package.json` (maintainer mode fixing the MCP). Don't conflate them.
