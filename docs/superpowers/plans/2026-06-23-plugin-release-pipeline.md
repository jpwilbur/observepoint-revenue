# Plugin Release Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On a version bump on `main`, a local git hook builds an install-safe, version-stamped `.plugin` file into a gitignored `dist/` and publishes it to the matching Google shared-drive folder (current version in the folder, prior version moved to `Old Versions/`).

**Architecture:** A thin bash orchestrator (`release.sh`) calls a build step (`build_plugin.sh`, builds from committed HEAD + hard-gates on `claude plugin validate`) and a deterministic, unit-tested Python publish step (`publish_to_drive.py`). Git hooks (`post-commit`, `post-merge`) call an idempotent `release-check.sh` that only acts on `main` when the manifest version differs from what's published. Cloud CI (`validate.yml`) validates and smoke-builds but never publishes (it can't reach the local Drive mount).

**Tech Stack:** Bash, Python 3 (stdlib only — `argparse`, `glob`, `shutil`, `pathlib`, `re`), pytest, `git archive`, `zip`, GitHub Actions, the `claude` CLI (`claude plugin validate`).

**Spec:** `docs/superpowers/specs/2026-06-23-plugin-release-pipeline-design.md`

**Scope:** This plan covers the **`observepoint-revenue` repo** (this repo) end-to-end — a complete, testable deliverable. Replicating into `observepoint-consultant` is a scoped follow-up at the end (own plan), to run after revenue is proven with a real release.

## Global Constraints

- All new release tooling lives at the **repo root** under `scripts/` and `.github/` — NOT inside `observepoint-revenue/`. The build uses `git archive HEAD:observepoint-revenue`, so repo-root tooling is naturally excluded from the plugin bundle.
- **Python interpreter trap:** locally, use `/opt/homebrew/bin/python3` (bare `python3` may resolve to CLT 3.9 without pytest/openpyxl). Scripts fall back to `python3` only when the Homebrew path is absent (e.g. Linux CI).
- **Artifact filename:** `observepoint-<name>-<version>.plugin`, e.g. `observepoint-revenue-0.16.1.plugin`. `name`/`version` read from `observepoint-revenue/.claude-plugin/plugin.json`.
- **`dist/` is gitignored** — artifacts stay local, never pushed.
- A plugin bundle must have `.claude-plugin/plugin.json` at the **ZIP root** and must **not** contain `marketplace.json`.
- Drive path is auto-detected via `$HOME/Library/CloudStorage/GoogleDrive-*` + fixed suffix `Shared drives/Solutions Consulting/Claude/Plugins/<folder>`; `<folder>` for this repo is `ObservePoint Revenue`. Override with env `OP_PLUGIN_DRIVE_DIR` (points directly at the `<folder>`).
- Work on a feature branch (e.g. `feat/release-pipeline`), not directly on `main`. Use conventional-commit messages (`feat:`, `chore:`, `docs:`). Commit email stays the configured GitHub noreply.
- End every commit message with the trailer:
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```

---

### Task 1: `publish_to_drive.py` + tests (the deterministic core)

**Files:**
- Create: `scripts/publish_to_drive.py`
- Test: `scripts/test_publish_to_drive.py`

**Interfaces:**
- Produces:
  - `resolve_drive_dir(folder_name, *, override=None, home=None) -> pathlib.Path`
  - `current_published_version(drive_dir) -> str | None`
  - `publish(artifact, drive_dir, *, dry_run=False, force=False) -> dict` returning keys `published` (bool), `skipped` (bool), `archived` (list[str]), `target` (str)
  - `main(argv=None) -> int` (CLI: positional optional `artifact`; `--folder` required; `--drive-dir`; `--print-current`; `--dry-run`; `--force`)

- [ ] **Step 1: Write the failing tests**

Create `scripts/test_publish_to_drive.py`:

```python
import importlib.util
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("publish_to_drive", HERE / "publish_to_drive.py")
ptd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ptd)


def _make_artifact(tmp_path, name):
    p = tmp_path / name
    p.write_bytes(b"PK\x03\x04 fake zip")
    return p


def _drive(tmp_path):
    d = tmp_path / "drive"
    d.mkdir()
    return d


def test_publish_places_new_and_archives_old(tmp_path):
    drive = _drive(tmp_path)
    (drive / "observepoint-revenue-0.15.0.plugin").write_bytes(b"old")
    art = _make_artifact(tmp_path, "observepoint-revenue-0.16.0.plugin")
    result = ptd.publish(art, drive)
    assert result["published"] is True
    assert result["archived"] == ["observepoint-revenue-0.15.0.plugin"]
    assert [p.name for p in drive.glob("*.plugin")] == ["observepoint-revenue-0.16.0.plugin"]
    assert (drive / "Old Versions" / "observepoint-revenue-0.15.0.plugin").is_file()


def test_publish_creates_old_versions_when_missing(tmp_path):
    drive = _drive(tmp_path)
    (drive / "observepoint-revenue-0.15.0.plugin").write_bytes(b"old")
    art = _make_artifact(tmp_path, "observepoint-revenue-0.16.0.plugin")
    assert not (drive / "Old Versions").exists()
    ptd.publish(art, drive)
    assert (drive / "Old Versions").is_dir()


def test_publish_first_release_no_archive(tmp_path):
    drive = _drive(tmp_path)
    art = _make_artifact(tmp_path, "observepoint-revenue-0.16.0.plugin")
    result = ptd.publish(art, drive)
    assert result["archived"] == []
    assert (drive / "observepoint-revenue-0.16.0.plugin").is_file()


def test_publish_idempotent_noop(tmp_path):
    drive = _drive(tmp_path)
    art = _make_artifact(tmp_path, "observepoint-revenue-0.16.0.plugin")
    ptd.publish(art, drive)
    result = ptd.publish(art, drive)
    assert result["skipped"] is True
    assert result["published"] is False


def test_publish_force_republishes(tmp_path):
    drive = _drive(tmp_path)
    art = _make_artifact(tmp_path, "observepoint-revenue-0.16.0.plugin")
    ptd.publish(art, drive)
    result = ptd.publish(art, drive, force=True)
    assert result["published"] is True


def test_publish_self_heals_to_one_current(tmp_path):
    drive = _drive(tmp_path)
    (drive / "observepoint-revenue-0.15.0.plugin").write_bytes(b"old")
    (drive / "observepoint-revenue-0.16.0.plugin").write_bytes(b"stale-current")
    art = _make_artifact(tmp_path, "observepoint-revenue-0.16.0.plugin")
    ptd.publish(art, drive)
    assert [p.name for p in drive.glob("*.plugin")] == ["observepoint-revenue-0.16.0.plugin"]
    assert (drive / "Old Versions" / "observepoint-revenue-0.15.0.plugin").is_file()


def test_dry_run_touches_nothing(tmp_path):
    drive = _drive(tmp_path)
    (drive / "observepoint-revenue-0.15.0.plugin").write_bytes(b"old")
    art = _make_artifact(tmp_path, "observepoint-revenue-0.16.0.plugin")
    result = ptd.publish(art, drive, dry_run=True)
    assert result["published"] is True
    assert (drive / "observepoint-revenue-0.15.0.plugin").is_file()
    assert not (drive / "observepoint-revenue-0.16.0.plugin").exists()
    assert not (drive / "Old Versions").exists()


def test_current_published_version(tmp_path):
    drive = _drive(tmp_path)
    assert ptd.current_published_version(drive) is None
    (drive / "observepoint-revenue-0.16.1.plugin").write_bytes(b"x")
    assert ptd.current_published_version(drive) == "0.16.1"


def test_resolve_drive_dir_override(tmp_path):
    got = ptd.resolve_drive_dir("ObservePoint Revenue", override=str(tmp_path / "x"))
    assert got == tmp_path / "x"


def test_resolve_drive_dir_single_mount(tmp_path):
    mount = tmp_path / "Library" / "CloudStorage" / "GoogleDrive-me@x.com"
    mount.mkdir(parents=True)
    got = ptd.resolve_drive_dir("ObservePoint Revenue", home=str(tmp_path))
    assert got == (mount / "Shared drives" / "Solutions Consulting" / "Claude"
                   / "Plugins" / "ObservePoint Revenue")


def test_resolve_drive_dir_zero_mounts(tmp_path):
    with pytest.raises(ValueError):
        ptd.resolve_drive_dir("ObservePoint Revenue", home=str(tmp_path))


def test_resolve_drive_dir_multiple_mounts(tmp_path):
    for n in ("GoogleDrive-a@x.com", "GoogleDrive-b@x.com"):
        (tmp_path / "Library" / "CloudStorage" / n).mkdir(parents=True)
    with pytest.raises(ValueError):
        ptd.resolve_drive_dir("ObservePoint Revenue", home=str(tmp_path))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin" && /opt/homebrew/bin/python3 -m pytest scripts/test_publish_to_drive.py -q`
Expected: collection/exec error — `publish_to_drive.py` does not exist yet (FileNotFoundError loading the module).

- [ ] **Step 3: Write the implementation**

Create `scripts/publish_to_drive.py`:

```python
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
    """Return the semver embedded in the folder's current *.plugin name, or None."""
    files = sorted(p for p in Path(drive_dir).glob("*.plugin") if p.is_file())
    if not files:
        return None
    m = VERSION_RE.search(files[-1].name)
    return m.group(1) if m else None


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
    args = ap.parse_args(argv)

    try:
        drive_dir = resolve_drive_dir(args.folder, override=args.drive_dir)
    except ValueError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1

    if args.print_current:
        print(current_published_version(drive_dir) or "" if drive_dir.is_dir() else "")
        return 0

    if not args.artifact:
        print("ERROR: artifact path required.", file=sys.stderr)
        return 2

    try:
        if not args.dry_run:
            drive_dir.mkdir(parents=True, exist_ok=True)
        result = publish(Path(args.artifact), drive_dir, dry_run=args.dry_run, force=args.force)
    except ValueError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1

    prefix = "[dry-run] " if args.dry_run else ""
    if result["skipped"]:
        print("%sAlready current: %s (use --force to republish)" % (prefix, Path(args.artifact).name))
    else:
        for name in result["archived"]:
            print("%sArchived %s -> Old Versions/" % (prefix, name))
        print("%sPublished %s -> %s" % (prefix, Path(args.artifact).name, result["target"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin" && /opt/homebrew/bin/python3 -m pytest scripts/test_publish_to_drive.py -q`
Expected: PASS (12 passed).

- [ ] **Step 5: Commit**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
git add scripts/publish_to_drive.py scripts/test_publish_to_drive.py
git commit -m "feat(release): deterministic shared-drive publish step + tests

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `build_plugin.sh` (install-safe, version-stamped bundle) + gitignore

**Files:**
- Modify: `.gitignore` (add `dist/`)
- Create: `scripts/build_plugin.sh`

**Interfaces:**
- Consumes: `observepoint-revenue/.claude-plugin/plugin.json` (`name`, `version`).
- Produces: `dist/observepoint-revenue-<version>.plugin` (validated zip; `.claude-plugin/plugin.json` at zip root; no `marketplace.json`). Honors env `PLUGIN_SUBDIR` (default `observepoint-revenue`) and `PYTHON`.

- [ ] **Step 1: Ignore the dist directory**

Append to `.gitignore` (after the existing `.superpowers/` line):

```gitignore

# built plugin artifacts — local only, never pushed
dist/
```

- [ ] **Step 2: Write the build script**

Create `scripts/build_plugin.sh`:

```bash
#!/usr/bin/env bash
#
# build_plugin.sh — build an install-safe, version-stamped `.plugin` bundle.
#
# A `.plugin` file is a ZIP of the plugin directory with `.claude-plugin/plugin.json`
# at the ZIP ROOT. If `marketplace.json` is present in the bundle, Claude classifies
# it as a MARKETPLACE (not a plugin) and the install fails. We build from committed
# HEAD, ensure no marketplace.json is in the staged tree, hard-gate on
# `claude plugin validate`, then zip.
#
# Layout is parameterized by PLUGIN_SUBDIR:
#   - revenue:    PLUGIN_SUBDIR=observepoint-revenue  (plugin in a subdir;
#                 marketplace.json sits ABOVE it and is naturally excluded)
#   - consultant: PLUGIN_SUBDIR=""                    (repo root IS the plugin;
#                 marketplace.json is inside the tree and is deleted)
#
# Usage: scripts/build_plugin.sh [output-path]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PLUGIN_SUBDIR="${PLUGIN_SUBDIR:-observepoint-revenue}"
if [ -n "$PLUGIN_SUBDIR" ]; then
  MANIFEST="$PLUGIN_SUBDIR/.claude-plugin/plugin.json"
  ARCHIVE_REF="HEAD:$PLUGIN_SUBDIR"
else
  MANIFEST=".claude-plugin/plugin.json"
  ARCHIVE_REF="HEAD"
fi

[ -f "$MANIFEST" ] || { echo "ERROR: $MANIFEST not found — run from inside the repo." >&2; exit 1; }

PYTHON="${PYTHON:-/opt/homebrew/bin/python3}"
command -v "$PYTHON" >/dev/null 2>&1 || PYTHON=python3
NAME="$("$PYTHON" -c "import json;print(json.load(open('$MANIFEST'))['name'])")"
VERSION="$("$PYTHON" -c "import json;print(json.load(open('$MANIFEST')).get('version','0.0.0'))")"
OUT="${1:-$ROOT/dist/${NAME}-${VERSION}.plugin}"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

# 1. Export committed content (tracked files at HEAD; omits .git/ and untracked).
git archive "$ARCHIVE_REF" | tar -x -C "$STAGE"

# 2. A plugin bundle must not contain a marketplace manifest.
rm -f "$STAGE/.claude-plugin/marketplace.json"
[ ! -f "$STAGE/.claude-plugin/marketplace.json" ] || { echo "ERROR: marketplace.json still in staged tree." >&2; exit 1; }
[ -f "$STAGE/.claude-plugin/plugin.json" ] || { echo "ERROR: no .claude-plugin/plugin.json at staged root." >&2; exit 1; }

# 3. HARD GATE: validate as a plugin. Skipped only when the claude CLI is absent
#    (e.g. Linux CI); on the maintainer's Mac it runs and gates every real release.
if command -v claude >/dev/null 2>&1; then
  VALIDATION="$(claude plugin validate "$STAGE" 2>&1 || true)"
  echo "$VALIDATION"
  grep -q "Validating plugin manifest" <<<"$VALIDATION" || { echo "ERROR: not classified as a plugin (did marketplace.json leak in?)." >&2; exit 1; }
  grep -q "Validation passed" <<<"$VALIDATION" || { echo "ERROR: plugin validation failed — see output above." >&2; exit 1; }
else
  echo "WARN: 'claude' CLI not found; skipping validation (build smoke test only)." >&2
fi

# 4. Zip staged contents at root so .claude-plugin/plugin.json sits at the ZIP root.
mkdir -p "$(dirname "$OUT")"
rm -f "$OUT"
( cd "$STAGE" && zip -rq "$OUT" . -x '*.DS_Store' )

echo
echo "Built ${NAME} v${VERSION} -> ${OUT}"
```

- [ ] **Step 3: Build and verify the artifact**

Run (commit any pending changes first — the build reads HEAD):

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
bash scripts/build_plugin.sh
```

Expected: prints `claude plugin validate` output ending in a pass, then `Built observepoint-revenue v0.16.1 -> .../dist/observepoint-revenue-0.16.1.plugin`. (If `claude` is absent it prints the WARN line and still builds.)

- [ ] **Step 4: Verify the zip is a plugin, not a marketplace**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
unzip -l dist/observepoint-revenue-0.16.1.plugin | grep -E '\.claude-plugin/plugin\.json'
unzip -l dist/observepoint-revenue-0.16.1.plugin | grep -c 'marketplace.json'   # expect 0
```

Expected: the first command lists `.claude-plugin/plugin.json`; the second prints `0`.

- [ ] **Step 5: Commit**

```bash
git add .gitignore scripts/build_plugin.sh
git commit -m "feat(release): version-stamped, validate-gated plugin build script

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `release.sh` orchestrator

**Files:**
- Create: `scripts/release.sh`

**Interfaces:**
- Consumes: `scripts/build_plugin.sh`, `scripts/publish_to_drive.py`.
- Produces: an executable `scripts/release.sh` accepting `--dry-run` and `--force`. Honors env `PLUGIN_SUBDIR` (default `observepoint-revenue`) and `OP_PLUGIN_DRIVE_FOLDER` (default `ObservePoint Revenue`).

- [ ] **Step 1: Write the orchestrator**

Create `scripts/release.sh`:

```bash
#!/usr/bin/env bash
#
# release.sh — build the versioned .plugin and publish it to the shared drive.
# Safe to run by hand; also invoked by the git hook on a version bump.
#
# Usage: scripts/release.sh [--dry-run] [--force]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PLUGIN_SUBDIR="${PLUGIN_SUBDIR:-observepoint-revenue}"
DRIVE_FOLDER="${OP_PLUGIN_DRIVE_FOLDER:-ObservePoint Revenue}"

DRY=""; FORCE=""
for a in "$@"; do
  case "$a" in
    --dry-run) DRY="--dry-run" ;;
    --force)   FORCE="--force" ;;
    *) echo "Unknown arg: $a" >&2; exit 2 ;;
  esac
done

PYTHON="${PYTHON:-/opt/homebrew/bin/python3}"
command -v "$PYTHON" >/dev/null 2>&1 || PYTHON=python3

# 1. Build (writes dist/<name>-<version>.plugin).
PLUGIN_SUBDIR="$PLUGIN_SUBDIR" PYTHON="$PYTHON" bash "$ROOT/scripts/build_plugin.sh"

# 2. Resolve the artifact path from the manifest.
if [ -n "$PLUGIN_SUBDIR" ]; then MANIFEST="$PLUGIN_SUBDIR/.claude-plugin/plugin.json"; else MANIFEST=".claude-plugin/plugin.json"; fi
NAME="$("$PYTHON" -c "import json;print(json.load(open('$MANIFEST'))['name'])")"
VERSION="$("$PYTHON" -c "import json;print(json.load(open('$MANIFEST')).get('version','0.0.0'))")"
ARTIFACT="$ROOT/dist/${NAME}-${VERSION}.plugin"

# 3. Publish to the shared drive.
"$PYTHON" "$ROOT/scripts/publish_to_drive.py" "$ARTIFACT" --folder "$DRIVE_FOLDER" $DRY $FORCE
```

- [ ] **Step 2: Verify with a dry run against a temp Drive folder**

This builds for real but publishes to a throwaway dir (no real Drive writes):

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
mkdir -p "/tmp/op-drive-test/ObservePoint Revenue"
OP_PLUGIN_DRIVE_DIR="/tmp/op-drive-test/ObservePoint Revenue" bash scripts/release.sh --dry-run
```

Expected: build output, then `[dry-run] Published observepoint-revenue-0.16.1.plugin -> /tmp/op-drive-test/ObservePoint Revenue`. Confirm nothing was written: `ls "/tmp/op-drive-test/ObservePoint Revenue"` is empty.

- [ ] **Step 3: Commit**

```bash
git add scripts/release.sh
git commit -m "feat(release): release.sh orchestrator (build -> publish)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Git hooks — version-bump detector + installer

**Files:**
- Create: `scripts/hooks/release-check.sh`
- Create: `scripts/install-hooks.sh`

**Interfaces:**
- Consumes: `scripts/release.sh`, `scripts/publish_to_drive.py` (via `--print-current`).
- Produces: `scripts/hooks/release-check.sh` (hook body) and `scripts/install-hooks.sh` (wires `.git/hooks/{post-commit,post-merge}` to it).

- [ ] **Step 1: Write the hook body**

Create `scripts/hooks/release-check.sh`:

```bash
#!/usr/bin/env bash
#
# release-check.sh — git hook body. On `main`, if the plugin version differs
# from the version already published to the shared drive, build + publish.
# NEVER aborts the git operation: always exits 0.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"   # scripts/hooks/ -> repo root
cd "$ROOT" || exit 0

BRANCH="$(git symbolic-ref --short -q HEAD || true)"
[ "$BRANCH" = "main" ] || exit 0

PLUGIN_SUBDIR="${PLUGIN_SUBDIR:-observepoint-revenue}"
DRIVE_FOLDER="${OP_PLUGIN_DRIVE_FOLDER:-ObservePoint Revenue}"
if [ -n "$PLUGIN_SUBDIR" ]; then MANIFEST="$PLUGIN_SUBDIR/.claude-plugin/plugin.json"; else MANIFEST=".claude-plugin/plugin.json"; fi
[ -f "$MANIFEST" ] || exit 0

PYTHON="${PYTHON:-/opt/homebrew/bin/python3}"
command -v "$PYTHON" >/dev/null 2>&1 || PYTHON=python3
VERSION="$("$PYTHON" -c "import json;print(json.load(open('$MANIFEST')).get('version','0.0.0'))" 2>/dev/null || true)"
[ -n "$VERSION" ] || exit 0

PUBLISHED="$("$PYTHON" "$ROOT/scripts/publish_to_drive.py" --folder "$DRIVE_FOLDER" --print-current 2>/dev/null || true)"

if [ "$VERSION" = "$PUBLISHED" ]; then
  exit 0   # already published this version — fast no-op
fi

echo "[release-check] version $VERSION != published '${PUBLISHED:-none}'; releasing…"
bash "$ROOT/scripts/release.sh" || echo "[release-check] release failed (see above); not blocking git." >&2
exit 0
```

- [ ] **Step 2: Write the installer**

Create `scripts/install-hooks.sh`:

```bash
#!/usr/bin/env bash
#
# install-hooks.sh — wire post-commit and post-merge to scripts/hooks/release-check.sh.
# Run once per clone. Git hooks are not version-controlled; this re-creates them.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_DIR="$(git -C "$ROOT" rev-parse --git-path hooks)"
mkdir -p "$HOOKS_DIR"

for h in post-commit post-merge; do
  cat > "$HOOKS_DIR/$h" <<EOF
#!/usr/bin/env bash
# Auto-generated by scripts/install-hooks.sh — do not edit.
exec bash "$ROOT/scripts/hooks/release-check.sh"
EOF
  chmod +x "$HOOKS_DIR/$h"
  echo "Installed $h -> scripts/hooks/release-check.sh"
done
echo "Done. Hooks active for this clone. (Re-run after a fresh clone.)"
```

- [ ] **Step 3: Install the hooks and verify they were written**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
bash scripts/install-hooks.sh
cat .git/hooks/post-commit .git/hooks/post-merge
```

Expected: prints `Installed post-commit ...` / `Installed post-merge ...`; both hook files exist and `exec bash ".../scripts/hooks/release-check.sh"`.

- [ ] **Step 4: Verify no-op vs release behavior (against a temp Drive)**

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
export OP_PLUGIN_DRIVE_DIR="/tmp/op-drive-hooktest/ObservePoint Revenue"
mkdir -p "$OP_PLUGIN_DRIVE_DIR"

# First run: nothing published yet -> it releases into the temp folder.
bash scripts/hooks/release-check.sh
ls "$OP_PLUGIN_DRIVE_DIR"            # expect observepoint-revenue-0.16.1.plugin

# Second run: same version already published -> fast no-op (no output, exit 0).
bash scripts/hooks/release-check.sh; echo "exit=$?"
unset OP_PLUGIN_DRIVE_DIR
```

Expected: first run prints `[release-check] version 0.16.1 != published 'none'; releasing…` and writes the file; second run prints only `exit=0`.

- [ ] **Step 5: Commit**

```bash
git add scripts/hooks/release-check.sh scripts/install-hooks.sh
git commit -m "feat(release): version-bump git hook + one-time installer

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: GitHub Actions validation (cloud CI — validate + smoke build, no publish)

**Files:**
- Create: `.github/workflows/validate.yml`

**Interfaces:**
- Consumes: `observepoint-revenue/requirements*.txt`, `scripts/test_publish_to_drive.py`, `scripts/build_plugin.sh`.
- Produces: a CI workflow running on PR + push to `main`.

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/validate.yml`:

```yaml
name: validate

on:
  pull_request:
  push:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r observepoint-revenue/requirements.txt -r observepoint-revenue/requirements-dev.txt

      - name: Plugin test suite
        run: cd observepoint-revenue && python -m pytest tests -q

      - name: Release-tooling tests
        run: python -m pytest scripts/test_publish_to_drive.py -q

      - name: Build artifact (smoke test, no publish)
        run: bash scripts/build_plugin.sh /tmp/out.plugin

      - name: Bundle is a plugin, not a marketplace
        run: |
          unzip -l /tmp/out.plugin | grep -qE '\.claude-plugin/plugin\.json'
          if unzip -l /tmp/out.plugin | grep -q 'marketplace.json'; then
            echo "ERROR: marketplace.json leaked into the bundle" >&2; exit 1
          fi
```

> Note: in CI the `claude` CLI is absent, so `build_plugin.sh` prints the WARN line and still builds — the real `claude plugin validate` gate runs locally at release time. If the revenue `tests` suite turns out to require network and is flaky on CI, gate the offending tests with a pytest marker (or `-k`) and confirm offline-safety before relying on the push trigger; do not silently drop the step.

- [ ] **Step 2: Verify the workflow's commands succeed locally**

(GitHub Actions can't run locally; run the same commands the workflow runs.)

```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin"
/opt/homebrew/bin/python3 -m pytest scripts/test_publish_to_drive.py -q
bash scripts/build_plugin.sh /tmp/ci-smoke.plugin
unzip -l /tmp/ci-smoke.plugin | grep -E '\.claude-plugin/plugin\.json'
```

Expected: tests pass; build prints `Built observepoint-revenue v0.16.1 -> /tmp/ci-smoke.plugin`; grep lists the manifest.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/validate.yml
git commit -m "ci: validate suite + build/structure smoke test (no publish)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: `RELEASE.md` documentation

**Files:**
- Create: `RELEASE.md`

- [ ] **Step 1: Write the doc**

Create `RELEASE.md`:

```markdown
# Releasing the plugin

The latest installable plugin is published as a single version-stamped `.plugin`
file to the team Google shared drive:

`Solutions Consulting / Claude / Plugins / ObservePoint Revenue /`

The current version sits directly in that folder; previous versions are in
`Old Versions/`. Teammates grab the latest file and install it (Cowork
"install plugin via upload", or `claude --plugin-dir <file>` for a session).

## One-time setup (per clone)

```bash
./scripts/install-hooks.sh
```

This wires `post-commit` and `post-merge` git hooks. Git hooks are not version
controlled, so re-run this after a fresh clone.

## Cutting a release

1. Bump `version` in `observepoint-revenue/.claude-plugin/plugin.json`.
2. Commit on `main` (or merge the PR and pull `main`).
3. The hook detects the new version and runs `./scripts/release.sh`, which:
   - builds `dist/observepoint-revenue-<version>.plugin` (gitignored, local only),
     hard-gated on `claude plugin validate`;
   - moves the previous file in the Drive folder into `Old Versions/`;
   - copies the new file into the Drive folder.

`dist/` never leaves your machine — it is gitignored.

## Manual / troubleshooting

```bash
./scripts/release.sh             # build + publish now
./scripts/release.sh --dry-run   # show what would happen, write nothing
./scripts/release.sh --force     # rebuild + republish the same version
```

- **Drive not found / ambiguous:** set the target folder explicitly:
  `OP_PLUGIN_DRIVE_DIR="/path/to/Plugins/ObservePoint Revenue" ./scripts/release.sh`
- **Build only (no publish):** `bash scripts/build_plugin.sh`
- The hook only acts on `main` and only when the manifest version differs from
  what's already in the Drive folder; it never blocks a git operation.
```

- [ ] **Step 2: Commit**

```bash
git add RELEASE.md
git commit -m "docs: RELEASE.md — shared-drive release flow

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Acceptance / end-to-end (maintainer, against the real Drive)

Not a code task — the final proof, run once by the maintainer:

1. `./scripts/install-hooks.sh` (if not already).
2. Bump `version` in `observepoint-revenue/.claude-plugin/plugin.json` (e.g. 0.16.1 → 0.17.0), commit on `main`.
3. Confirm `dist/observepoint-revenue-0.17.0.plugin` exists locally and `git status` shows it ignored (untracked-but-ignored, never staged).
4. Confirm the real Drive folder `…/Plugins/ObservePoint Revenue/` now holds `observepoint-revenue-0.17.0.plugin` and the prior file moved to `Old Versions/`.
5. Install the published file in a clean session (Cowork upload or `claude --plugin-dir`) and confirm it loads without "Plugin validation failed".

---

## Follow-up (separate plan): replicate into `observepoint-consultant`

After revenue is proven, port the same machinery into `~/Documents/ObservePoint Consultant Skill`
(remote `github.com/jpwilbur/observepoint-consultant`). Deltas only:

- That repo root **is** the plugin, so the script defaults differ: `PLUGIN_SUBDIR=""` and
  `OP_PLUGIN_DRIVE_FOLDER="ObservePoint Consultant"`. Bake those as the defaults in its copies of
  `build_plugin.sh`, `release.sh`, and `release-check.sh`.
- It already has `scripts/build_plugin.sh` (unversioned output) — replace its output name with the
  version-stamped `observepoint-consultant-<version>.plugin` and align it to this repo's script.
- Add `publish_to_drive.py` + `test_publish_to_drive.py` (rename the fixture plugin names),
  `release.sh`, `scripts/hooks/release-check.sh`, `scripts/install-hooks.sh`.
- It already has `.github/workflows/validate.yml` — **extend** it with the build/structure smoke-test
  step (it keeps `quick_validate.py` + `run_evals.py`).
- Add `dist/` to its `.gitignore` if absent; publishes to `…/Plugins/ObservePoint Consultant/`.

This follow-up gets its own dated plan once revenue ships.
```
