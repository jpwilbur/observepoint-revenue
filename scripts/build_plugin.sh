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

# NOTE: `:-` treats an empty string as unset, so passing PLUGIN_SUBDIR="" as an env
# override here re-defaults to observepoint-revenue. The consultant repo (root-is-plugin)
# must bake PLUGIN_SUBDIR="${PLUGIN_SUBDIR:-}" as its own default instead.
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

# 3. Pre-publish metadata gate that mirrors the Cowork / plugin-directory UPLOAD
#    validator (stricter than `claude plugin validate`): plugin.json description
#    <= 500 chars, and no skill SKILL.md description contains XML tags. Pure Python,
#    so this gate runs in CI too, where the claude CLI is absent.
"$PYTHON" "$ROOT/scripts/check_plugin_meta.py" "$STAGE" || { echo "ERROR: pre-publish metadata check failed (see above)." >&2; exit 1; }

# 4. HARD GATE: validate as a plugin. Skipped only when the claude CLI is absent
#    (e.g. Linux CI); on the maintainer's Mac it runs and gates every real release.
if command -v claude >/dev/null 2>&1; then
  VALIDATION="$(claude plugin validate "$STAGE" 2>&1 || true)"
  echo "$VALIDATION"
  grep -q "Validating plugin manifest" <<<"$VALIDATION" || { echo "ERROR: not classified as a plugin (did marketplace.json leak in?)." >&2; exit 1; }
  grep -q "Validation passed" <<<"$VALIDATION" || { echo "ERROR: plugin validation failed — see output above." >&2; exit 1; }
else
  echo "WARN: 'claude' CLI not found; skipping validation (build smoke test only)." >&2
fi

# 5. Zip staged contents at root so .claude-plugin/plugin.json sits at the ZIP root.
mkdir -p "$(dirname "$OUT")"
rm -f "$OUT"
( cd "$STAGE" && zip -rq "$OUT" . -x '*.DS_Store' )

echo
echo "Built ${NAME} v${VERSION} -> ${OUT}"
