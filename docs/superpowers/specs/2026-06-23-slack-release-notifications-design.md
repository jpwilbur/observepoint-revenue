# Slack release notifications — design

**Date:** 2026-06-23
**Status:** approved (pending spec review)
**Applies to:** all three release pipelines — `observepoint-revenue`, `observepoint-consultant`,
and the MCP tooling at `~/Documents/OP_MCP/release/`.

## Goal

When a pipeline publishes a **new** version to its Google shared-drive folder, post one message to a
shared Slack channel announcing the new version with a link to that folder, so teammates know to update.
All three post to the same channel; only the display name, version, and folder link differ.

## Decisions (locked during brainstorming)

1. **Slack Incoming Webhook** (not a bot token). One webhook → one channel. The publish step POSTs JSON.
   The client id/secret of the Slack app are **not** needed — only the webhook URL.
2. **One shared secret**, since all three post to the same channel: the webhook URL is read from env
   `OP_RELEASE_SLACK_WEBHOOK` (precedence), then a local file `~/.config/op-release/slack-webhook`.
   Never committed.
3. **Fires only on a real new publish** — not on a no-op (same version already current) or `--dry-run`.
4. **Non-fatal & gated:** if no webhook is configured, the publish still succeeds and the post is skipped
   with a warning. A Slack failure logs a warning (the artifact is already on the Drive). Notifications
   never block a release or a git operation.
5. **Build now, wire the URL later.** The webhook is pending admin approval; with the secret unset the
   system is a safe no-op until the URL is added.

## Components (per pipeline)

### `notify_slack.py` (new; stdlib only; unit-tested)
- `build_message(name, version, folder_url)` → the message text (Slack mrkdwn).
- `resolve_webhook(env=None, home=None)` → URL from `OP_RELEASE_SLACK_WEBHOOK`, else
  `~/.config/op-release/slack-webhook`, else `None`. (`env`/`home` injectable for tests.)
- `post(webhook, text, *, _opener=urllib.request.urlopen)` → POST `{"text": ...}` as JSON with a short
  timeout; return `True` on 2xx, `False` on any error (never raises). (`_opener` injectable for tests.)

### `publish_to_drive.py` (extended)
Add `--notify`, `--name "<display name>"`, `--folder-url "<url>"`. After computing the publish result:
- skipped (no-op) → do nothing;
- `--dry-run` → print `[dry-run] would notify: <text>` (no post);
- real publish → resolve the webhook; if set, `post(...)` and print `Notified Slack.` (or a WARN on
  failure); if unset, print a NOTE that no webhook is configured.
- Version for the message is parsed from the artifact filename via the module's existing `VERSION_RE`.

### `release.sh` (extended, per repo)
Pass the repo's own `--notify --name "<display name>" --folder-url "<url>"` through to
`publish_to_drive.py`. Everything else is shared.

## Per-pipeline configuration

| Pipeline | Display name | Folder share link |
|----------|--------------|-------------------|
| revenue | `ObservePoint Revenue` | https://drive.google.com/drive/folders/1qGbunM8j3CBEex1oBiZ2cq7GR5C7Bpro |
| consultant | `ObservePoint Consultant` | https://drive.google.com/drive/folders/1dxAAaaqFaQK2JCfZ_AMMsXPlmMeF65-e |
| MCP | `ObservePoint MCP` | https://drive.google.com/drive/folders/111Xqpi2jd_d5_394ervj4Jc2JK2wnXeE |

The folder links are non-secret internal share URLs; they are committed in the two private plugin repos
and live locally for the MCP (its tooling is never pushed to the org repo). The webhook URL is the only
secret and is never committed.

## Message format

Slack mrkdwn (`build_message`):

```
🟢 *<name>* `v<version>` is now available to install.
Grab the latest from the shared drive and update: <<folder_url>|<name>>
```

Example: `🟢 *ObservePoint Consultant* \`v0.8.2\` is now available to install.\nGrab the latest from the
shared drive and update: <https://drive.google.com/drive/folders/1dxA…|ObservePoint Consultant>`

## Error handling
- No webhook configured → publish succeeds, post skipped, NOTE printed.
- POST failure / timeout → `post()` returns False, WARN printed; release still succeeds.
- These run after the artifact is on the Drive, so notification problems never affect distribution.

## Testing
- `test_notify_slack.py`: `build_message` (name/version/link correct, per-repo wording); `resolve_webhook`
  (env precedence, file fallback, none); `post` success/failure via an injected fake `_opener` (captures
  the request body, simulates 2xx and an exception — no real network).
- Manual: `release.sh --dry-run` prints the exact `[dry-run] would notify:` line; once the webhook URL is
  added, one real publish (or a `--notify` smoke post) confirms it lands in the channel.

## Rollout
- **revenue / consultant:** add the three changes to the committed `scripts/`; PR → merge. No version
  bump — release tooling isn't the plugin's capability; the notification activates on the next real
  version release of each plugin.
- **MCP:** add the same to the local `~/Documents/OP_MCP/release/` (nothing pushed to the org repo);
  activates on the next MCP release.

## Out of scope
- No bot token, no multi-channel routing, no `@here`/`@channel` ping, no per-recipient DMs.
- No change to the trigger, build, or publish-archive logic.
