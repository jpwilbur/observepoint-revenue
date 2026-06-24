#!/usr/bin/env python3
"""Publish a built .plugin artifact into its Google shared-drive folder.

Deterministic: archive the previous current *.plugin into Old Versions/, then
copy the new versioned artifact into the top folder. Keeps exactly one current
.plugin in the top folder. Stdlib only; no network beyond the local Drive mount.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import sys
from pathlib import Path

DRIVE_SUFFIX = ("Shared drives", "Solutions Consulting", "Claude", "Plugins")
VERSION_RE = re.compile(r"-(\d+\.\d+\.\d+)\.plugin$")


def resolve_drive_dir(folder_name, *, override=None, home=None):
    """Return the Path to this plugin's shared-drive top folder.

    override: if given, use it directly as the top folder.
    else: glob <home>/Library/CloudStorage/GoogleDrive-* (exactly one required),
          append the fixed Plugins suffix + folder_name.
    Raises ValueError with a clear message on 0 or >1 Drive mounts.
    """
    if override:
        return Path(override).expanduser()
    home = Path(home) if home else Path.home()
    mounts = sorted(glob.glob(str(home / "Library" / "CloudStorage" / "GoogleDrive-*")))
    if len(mounts) == 0:
        raise ValueError(
            "No Google Drive mount under ~/Library/CloudStorage/GoogleDrive-*. "
            "Set OP_PLUGIN_DRIVE_DIR to the target folder."
        )
    if len(mounts) > 1:
        raise ValueError(
            "Multiple Google Drive mounts found: %s. Set OP_PLUGIN_DRIVE_DIR to disambiguate."
            % ", ".join(mounts)
        )
    return Path(mounts[0]).joinpath(*DRIVE_SUFFIX, folder_name)


def current_published_version(drive_dir):
    """Return the highest semver embedded in the folder's *.plugin names, or None.

    Compares parsed version tuples, not filenames, so 0.10.0 > 0.9.0.
    """
    best = None
    for p in Path(drive_dir).glob("*.plugin"):
        if not p.is_file():
            continue
        m = VERSION_RE.search(p.name)
        if not m:
            continue
        ver = tuple(int(x) for x in m.group(1).split("."))
        if best is None or ver > best[0]:
            best = (ver, m.group(1))
    return best[1] if best else None


def publish(artifact, drive_dir, *, dry_run=False, force=False):
    """Archive prior *.plugin into Old Versions/ and copy artifact into drive_dir.

    Idempotent: if drive_dir holds exactly artifact.name (and only it), no-op
    unless force. Returns {published, skipped, archived, target}.
    """
    artifact = Path(artifact)
    drive_dir = Path(drive_dir)
    if not artifact.is_file():
        raise ValueError("Artifact not found: %s" % artifact)
    if not drive_dir.is_dir():
        raise ValueError("Drive folder not found: %s" % drive_dir)

    existing = sorted(p for p in drive_dir.glob("*.plugin") if p.is_file())
    if [p for p in existing if p.name == artifact.name] and len(existing) == 1 and not force:
        return {"published": False, "skipped": True, "archived": [], "target": str(drive_dir)}

    old_versions = drive_dir / "Old Versions"
    to_archive = [p for p in existing if p.name != artifact.name]
    if to_archive and not dry_run:
        old_versions.mkdir(parents=True, exist_ok=True)
    archived = []
    for p in to_archive:
        if not dry_run:
            dest = old_versions / p.name
            if dest.exists():
                dest.unlink()
            shutil.move(str(p), str(dest))
        archived.append(p.name)

    if not dry_run:
        shutil.copy2(str(artifact), str(drive_dir / artifact.name))

    return {"published": True, "skipped": False, "archived": archived, "target": str(drive_dir)}


def _maybe_notify_slack(args, result):
    """On a real publish (not a no-op or dry-run), post a Slack announcement if --notify."""
    if not (args.notify and args.name and args.folder_url):
        return
    if result.get("skipped"):
        return
    import importlib
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    notify = importlib.import_module("notify_slack")
    m = VERSION_RE.search(Path(args.artifact).name)
    version = m.group(1) if m else "?"
    text = notify.build_message(args.name, version, args.folder_url)
    if args.dry_run:
        print("[dry-run] would notify: " + text)
        return
    webhook = notify.resolve_webhook()
    if not webhook:
        print("NOTE: %s not set; skipping Slack notification." % notify.WEBHOOK_ENV, file=sys.stderr)
    elif notify.post(webhook, text):
        print("Notified Slack.")
    else:
        print("WARN: Slack notification failed (publish already succeeded).", file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Publish a .plugin artifact to its shared-drive folder.")
    ap.add_argument("artifact", nargs="?", help="path to the built .plugin file")
    ap.add_argument("--folder", required=True, help='Drive folder name, e.g. "ObservePoint Revenue"')
    ap.add_argument("--drive-dir", default=os.environ.get("OP_PLUGIN_DRIVE_DIR"),
                    help="override the resolved top folder (else auto-detect)")
    ap.add_argument("--print-current", action="store_true",
                    help="print the version currently published to the folder, then exit")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--notify", action="store_true",
                    help="post a Slack release announcement on a real publish")
    ap.add_argument("--name", help="display name for the Slack message (e.g. 'ObservePoint Revenue')")
    ap.add_argument("--folder-url", help="Drive folder share link for the Slack message")
    args = ap.parse_args(argv)

    try:
        drive_dir = resolve_drive_dir(args.folder, override=args.drive_dir)
    except ValueError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1

    if args.print_current:
        version = current_published_version(drive_dir) if drive_dir.is_dir() else None
        print(version or "")
        return 0

    if not args.artifact:
        print("ERROR: artifact path required.", file=sys.stderr)
        return 2

    try:
        if not args.dry_run:
            drive_dir.mkdir(parents=True, exist_ok=True)
        result = publish(Path(args.artifact), drive_dir, dry_run=args.dry_run, force=args.force)
    except (ValueError, OSError) as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1

    prefix = "[dry-run] " if args.dry_run else ""
    if result["skipped"]:
        print("%sAlready current: %s (use --force to republish)" % (prefix, Path(args.artifact).name))
    else:
        for name in result["archived"]:
            print("%sArchived %s -> Old Versions/" % (prefix, name))
        print("%sPublished %s -> %s" % (prefix, Path(args.artifact).name, result["target"]))

    _maybe_notify_slack(args, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
