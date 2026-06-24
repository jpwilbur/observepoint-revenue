#!/usr/bin/env python3
"""Post a release announcement to Slack via an Incoming Webhook. Stdlib only.

The webhook URL (the only secret) is read from env OP_RELEASE_SLACK_WEBHOOK
(precedence), else from ~/.config/op-release/slack-webhook. If neither is set,
callers skip posting. `post` never raises on a network/Slack error — it returns
False so a release is never blocked by a notification problem.
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

WEBHOOK_ENV = "OP_RELEASE_SLACK_WEBHOOK"
WEBHOOK_FILE = Path(".config") / "op-release" / "slack-webhook"  # relative to $HOME


def build_message(name, version, folder_url):
    """Return the Slack mrkdwn announcement for a new release."""
    return (
        "🟢 *%s* `v%s` is now available to install.\n"
        "Grab the latest from the shared drive and update: <%s|%s>"
        % (name, version, folder_url, name)
    )


def resolve_webhook(env=None, home=None):
    """Return the webhook URL from env (precedence) or the local file, else None."""
    env = os.environ if env is None else env
    val = (env.get(WEBHOOK_ENV) or "").strip()
    if val:
        return val
    home = Path(home) if home else Path.home()
    f = home / WEBHOOK_FILE
    if f.is_file():
        c = f.read_text().strip()
        if c:
            return c
    return None


def post(webhook, text, *, _opener=urllib.request.urlopen, timeout=10):
    """POST {"text": text} to the webhook. Return True on 2xx, False on any error."""
    data = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with _opener(req, timeout=timeout) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            return 200 <= int(code) < 300
    except Exception:
        return False
