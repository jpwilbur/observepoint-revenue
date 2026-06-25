---
name: op-mcp-post-mortem
description: Use when the ObservePoint MCP server itself misbehaves in a conversation — a tool errors, returns wrong or misleading data, hangs, or a tool description led Claude to use it incorrectly — and you want to report it; or when remediating a received OP MCP post-mortem (triage, reproduce, fix, verify). Keywords ObservePoint MCP, MCP tool failed, wrong/misleading output, bug report, post-mortem, remediate. NOT for ObservePoint sales/scoping/research work (the other observepoint-revenue skills) and NOT for issues with the ObservePoint web app itself.
---

# OP MCP Post-Mortem

Turn a rough ObservePoint-MCP session into a record the MCP maintainer can act on — and then act on
it. Two modes share one artifact: a standardized post-mortem markdown file.

- **Submitter mode** (default) — a power user, right after the MCP misbehaved, produces the
  post-mortem file and sends it to whoever maintains the MCP.
- **Maintainer mode** (`remediate <path>`) — the maintainer triages, reproduces, fixes, verifies,
  and closes the loop on a received post-mortem.

This skill is about **the MCP server being broken**, not about selling. If the issue is with the
ObservePoint web app (not the MCP tools), or it's a sales/scoping/research task, this is the wrong
skill.

Set `SKILL=${CLAUDE_PLUGIN_ROOT}/skills/op-mcp-post-mortem`. Scripts are stdlib-only; prefer
`/opt/homebrew/bin/python3`.

## Choose the mode

- Invoked with a post-mortem file path, or `remediate <path>` → **Maintainer mode**.
- Otherwise → **Submitter mode**.
- Genuinely unsure which? Ask once, then proceed.

---

## Submitter mode

You have the live conversation in context — that is the asset. Build the post-mortem *from it*, then
let the script render and the scanner guard. **Do not hand-write the document** — assemble a facts
JSON and run the renderer, so every post-mortem has the same shape and no section is missed.

1. **Auto-extract from the conversation** (no questions yet). Pull the real values — never invent:
   - The exact MCP tool name(s) (e.g. `mcp__ObservePoint__get_audit_runs`) and the parameters passed.
   - The failure: error text, wrong/misleading output, hang/timeout, or "the tool description led me
     to call it wrong."
   - What Claude did vs. what the user was trying to do.
   - MCP version (from `manifest.json`/`whoami` if visible) and client (Desktop / Code).
   - Anything you can't determine → record it as `"unknown / not captured"`. Never guess a tool
     name, parameter, error string, ID, or version.

2. **Capture reproduction config.** The maintainer's preferred fix path is to recreate your setup in
   a *separate test account*, so capture what makes that possible:
   - The account ID and the specific resource IDs involved (audit / journey / rule / report /
     consent-category).
   - A config snapshot of those resources via the MCP's own read tools where available
     (`get_audit`, `get_journey`, `get_rule`, `bulk_describe`, `query_audit_configs`, …).
   - If you can only get IDs and not a full snapshot, set `reproduction.complete = false` and say so
     in `notes`. An incomplete repro is fine — a *silently* incomplete one is not.

3. **Confirm only the gaps with the user** (one short batch — don't make them re-state what you
   already extracted):
   - **Expected behavior** — what should have happened.
   - **Severity** — `Low / Medium / High / Critical`. Ask; don't assign it yourself.
   - **Sharing** — "OK to include these account/resource IDs and the config snapshot in the file?"

4. **Redaction gate (mandatory before writing).** Run the scanner over every piece of text headed
   into the file:
   ```bash
   python3 "$SKILL/scripts/scan_secrets.py" /tmp/pm-evidence.txt        # flags items to review
   python3 "$SKILL/scripts/scan_secrets.py" /tmp/pm-evidence.txt --redact > /tmp/pm-evidence.clean.txt
   ```
   Redact every live credential (API key, bearer/JWT, cookie, session id) **and customer PII**
   (customer email addresses, account-owner names, URLs with tokens). The reporter's own contact may
   stay. The file gets forwarded and archived — a credential or a customer's email in it is a real
   leak, so when in doubt, redact.

5. **Render & write.** Assemble the facts JSON (shape in
   `${CLAUDE_PLUGIN_ROOT}/skills/op-mcp-post-mortem/references/post-mortem-template.md`) and render:
   ```bash
   python3 "$SKILL/scripts/render_post_mortem.py" /tmp/pm-facts.json \
     --out "$HOME/Documents/ObservePoint Revenue/MCP Post-Mortems/<YYYY-MM-DD-short-slug>/post-mortem.md"
   ```
   Honor a rep-specified output location if given; otherwise use that path. Never a temp dir. Then
   **re-scan the rendered file** (`scan_secrets.py <file>`) as a backstop — it must come back clean
   (or every remaining hit must be an intentional keep, like the reporter's email).

6. **Hand off.** Tell the user the file path and that they should send it to whoever can push MCP
   code, however they normally communicate. The maintainer runs this skill's maintainer mode on it.

**Submitter red flags — stop:**
- Hand-writing the markdown instead of rendering it from the facts JSON.
- Saving anywhere other than `~/Documents/ObservePoint Revenue/MCP Post-Mortems/…`.
- Writing the file before `scan_secrets.py` comes back clean.
- Leaving a customer email / account-owner name / tokened URL in the body "for reference".
- Assigning a severity the user didn't confirm, or stating a root cause you didn't verify.

---

## Maintainer mode

You have a post-mortem and the ObservePoint MCP repo (the `observepoint-mcp` project — `cd` there;
build `npm run build`, smoke tests `scripts/*-smoke.mjs`). Work on a branch, not `main`.

> **A report is a claim, not a confirmed defect. You do not write a fix until you have reproduced
> the reported failure and classified it as a real MCP defect.** Time pressure does not change this —
> triage and reproduction are exactly what stops you fixing the wrong thing.

Run these gates **in order**:

1. **Triage & classify.** Decide which one it is:
   - **real MCP bug** — a code defect in the server,
   - **misleading/insufficient tool description** — the tool worked but its description led to misuse
     (still an MCP fix, but the remedy is wording, not logic),
   - **ObservePoint API/platform issue** — the MCP relayed what the API gave it → **escalate**, this
     is not an MCP code fix,
   - **not a defect** — expected behavior, or user/model error.

   **Reject path:** if it's not an MCP defect, write the classification + reason into the maintainer
   section, set status `Rejected`/`Escalated`, and **stop**. Don't fix non-defects. (Watch for the
   trap where the tool is "usually right" — that means you haven't found *this* failure's cause yet,
   not that there's nothing to fix.)

2. **Reproduce before fixing.** No code change until you've reproduced the reported failure:
   - **Preferred:** recreate the post-mortem's captured config in a **clean/test ObservePoint
     account**, reproduce the failure there, and **tear that config down afterward**.
   - **Fallback (only if recreation is impossible):** ask the reporter for permission to test in the
     account where it happened.
   - **Never** reproduce by poking an unrelated real account you happen to have access to — that is
     not a reproduction of *this* issue and it risks mutating data you don't own.
   - A synthetic unit test is **not** a reproduction. It proves your hypothesis is self-consistent,
     not that it's the real cause. Reproduce first; write the regression test in step 3.
   - Can't reproduce at all? Say so in the maintainer section and go back to the reporter for detail.

3. **Fix.** Use **superpowers:systematic-debugging** to find the root cause, then
   **superpowers:test-driven-development**: write a failing test that captures the reproduced defect
   first, then the minimal fix. Scope the change to the confirmed root cause — don't rewrite call
   sites you haven't shown are broken.

4. **Verify.** `npm run build` and the `scripts/*-smoke.mjs` smoke tests, gated by
   **superpowers:verification-before-completion**. No "fixed" claim without green output — paste it
   into the maintainer section.

5. **Close the loop.** Fill the maintainer section (classification, repro result, root cause, fix +
   commit/PR, verification evidence), set status `Fixed`, and bump `observepoint-mcp/package.json`
   (and `manifest.json`) for a real fix. Commit/push only when the maintainer asks.

### Maintainer rationalization table

| Excuse | Reality |
|--------|---------|
| "The tool is usually right, so this is obviously the bug — just patch it." | "Usually right" means you haven't found *this* failure's cause. Classify and reproduce first. |
| "I couldn't reach their audit, but I have another account with similar data — I'll verify there." | A different real account is not a reproduction of this issue, and you may mutate data you don't own. Recreate in a test account or ask the reporter. |
| "A unit test in the reported shape proves the bug." | It proves your hypothesis is consistent, not real. Reproduce against an actual setup, then add the regression test. |
| "Teammate's waiting / customer's asking / it's late — ship it." | Pressure doesn't turn an unreproduced report into a confirmed defect. Triage + repro are fast and prevent fixing the wrong thing. |
| "It's clearly a sort bug — fix every call site that looks similar." | Scope to the reproduced root cause. Unverified call sites are speculation. |
| "It built fine, I'll call it fixed." | Build ≠ verified. Run the smoke tests and reproduce-now-passes before claiming fixed. |

### Maintainer red flags — stop and restart the gate:
- About to edit code before you've reproduced the failure.
- Reproducing in any account other than a clean test account (or the reporter's, with permission).
- Substituting a synthetic/unit test for an actual reproduction.
- Skipping classification because the report "looks obviously real."
- Committing, pushing, or bumping the version before green build + smoke output.
- Working on `main` instead of a branch.

---

## Quick reference

| | Submitter mode | Maintainer mode |
|---|---|---|
| **Trigger** | MCP misbehaved; want to report it | `remediate <post-mortem path>` |
| **Core discipline** | No fabrication; redact secrets + customer PII; render via script | Classify → reproduce (test account) → TDD fix → verify → close loop |
| **Scripts** | `scan_secrets.py`, `render_post_mortem.py` | none (orchestrates superpowers skills + repo build/test) |
| **Output** | `~/Documents/ObservePoint Revenue/MCP Post-Mortems/<date-slug>/post-mortem.md` | filled maintainer section + `observepoint-mcp` version bump |
| **Never** | invent a tool name/severity; leak a credential or customer email | fix without reproducing; touch an unrelated real account; claim fixed without green output |
