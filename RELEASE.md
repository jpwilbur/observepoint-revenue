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
