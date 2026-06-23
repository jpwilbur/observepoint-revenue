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
