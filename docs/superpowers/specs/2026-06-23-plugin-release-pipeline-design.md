# Plugin release pipeline — design

**Date:** 2026-06-23
**Status:** approved (pending spec review)
**Applies to:** both repos — `observepoint-revenue` (this repo) and `observepoint-consultant`
(`~/Documents/ObservePoint Consultant Skill`, remote `github.com/jpwilbur/observepoint-consultant`)

## Problem

Distributing these (almost entirely internal) plugins through the Claude Code **marketplace**
install/update flow has been unreliable and slow for teammates. We want a low-friction alternative:
the latest **install-safe** plugin artifact, version-stamped, sitting in a Google **shared drive**
folder teammates already have mounted, so they can grab and install it quickly. Past attempts at
hand-built plugin files have **failed to install** — we must make that impossible by construction.

## Goals

1. On a version bump, build a **functional, install-safe** `.plugin` file (validated zip) following
   the [Claude Code plugin docs](https://code.claude.com/docs/en/plugins).
2. The built artifact lands in the repo **locally but is never pushed remotely**.
3. The artifact is copied to the matching Google **shared-drive** folder, **version-stamped**, with
   the **current** version sitting directly in the folder and the **previous** one moved to
   `Old Versions/`.
4. Trigger this automatically when a new version lands on `main`, on the maintainer's Mac.
5. Standardize the **same machinery** in both repos.

## Non-goals

- Replacing the GitHub marketplace entirely (it can stay; this is a parallel, easier path).
- Publishing from cloud CI to the shared drive (impossible — see constraint below).
- Pruning the bundle to a lean runtime-only set (decided: keep everything tracked).

## Hard constraint that shapes the design

The shared drive is a **local mount** on the maintainer's Mac
(`~/Library/CloudStorage/GoogleDrive-<email>/Shared drives/...`). GitHub Actions runs on cloud
runners and **cannot write to that mount.** Therefore the build+publish-to-Drive step is **local
automation** (a git hook + scripts on the Mac), not cloud CI. Cloud CI is retained only for
**validation** (it can build and validate the artifact, just not publish it).

## Key facts established during research

- A `.plugin` file is just a **ZIP of the plugin directory with `.claude-plugin/plugin.json` at the
  ZIP root**. `claude --plugin-dir ./x.plugin` / `--plugin-url` accept a zip; Cowork's
  "install plugin via upload" accepts this file. (It is **not** a `.dxt`.)
- **Root cause of past install failures:** if `marketplace.json` is present in the bundle, Claude
  classifies the artifact as a **marketplace, not a plugin**, and the install fails with
  "Plugin validation failed." The consultant repo's existing `scripts/build_plugin.sh` already
  defends against this by deleting `marketplace.json` from the staged tree and asserting the result
  validates as a plugin. This design generalizes that defense.
- `claude plugin validate <dir>` is the authoritative pre-flight gate.

### Repo layout difference (must be handled)

| Repo | Plugin root | `marketplace.json` location |
|------|-------------|------------------------------|
| `observepoint-revenue` (this) | subdir `observepoint-revenue/` | repo root `.claude-plugin/` (one level **above** the plugin) |
| `observepoint-consultant` | repo root **is** the plugin | repo root `.claude-plugin/` (**inside** the plugin tree) |

- Revenue: `git archive HEAD:observepoint-revenue` yields the plugin tree at zip root, and
  `marketplace.json` is naturally absent (it lives above the plugin). Still asserted + validated.
- Consultant: `git archive HEAD` yields the whole repo; the explicit `rm marketplace.json` step is
  required (existing behavior).

### Shared-drive structure (already exists, both `Old Versions/` empty)

```
~/Library/CloudStorage/GoogleDrive-<email>/Shared drives/Solutions Consulting/Claude/Plugins/
├── ObservePoint Revenue/      ← revenue publishes here
│   └── Old Versions/
└── ObservePoint Consultant/   ← consultant publishes here
    └── Old Versions/
```

## Architecture

```
commit / merge on main
        │
        ▼
.git/hooks/{post-commit,post-merge}  ──▶  scripts/hooks/release-check.sh
        │   (wired once by scripts/install-hooks.sh; sources are committed, hooks are not)
        │
        │  on `main` AND plugin.json version ≠ version currently in the Drive folder?
        ▼  yes (else fast no-op; never aborts the git op, always exits 0)
scripts/release.sh   [--force] [--dry-run]
        ├─ scripts/build_plugin.sh   → dist/observepoint-<name>-<version>.plugin   (local, gitignored)
        │     • git archive committed HEAD → staging tree
        │     • assert/remove marketplace.json; assert no marketplace.json remains
        │     • `claude plugin validate` HARD GATE (must read as plugin + pass)
        │     • zip with .claude-plugin/plugin.json at ZIP ROOT, exclude .DS_Store
        └─ scripts/publish_to_drive.py  (deterministic, unit-tested)
              • resolve Drive folder for this repo
              • move existing top-folder *.plugin → Old Versions/
              • copy new versioned file into the top folder
              • invariant: top folder holds exactly one .plugin (the current version)
```

`release.sh` is a thin bash orchestrator. The fiddly archive/place logic lives in Python so it is
unit-testable and matches the repo's "deterministic scripts compute" principle.

## Components (per repo)

### `scripts/build_plugin.sh`
- Reads `name` + `version` from the plugin's `plugin.json`.
- Builds from **committed HEAD** (reproducible; the hook only fires post-commit/merge so HEAD is
  correct).
- Revenue uses `git archive HEAD:observepoint-revenue`; consultant uses `git archive HEAD` +
  `rm marketplace.json`. A single script parameterized by a `PLUGIN_SUBDIR` variable (empty for
  consultant) handles both; the assertion "staged tree has no `marketplace.json`" runs in both.
- **Hard gate:** if `claude` is on PATH, run `claude plugin validate <stage>`; fail unless it both
  classifies as a plugin and reports validation passed. If `claude` is absent, warn (CI/foreign
  machines) — but on the maintainer's Mac it is present, so the gate is real at release time.
- Output: `dist/observepoint-<name>-<version>.plugin` (version-stamped, both repos). Configurable
  output path as `$1`.

### `scripts/publish_to_drive.py`
- Inputs: built artifact path, the repo's Drive **folder name** (`ObservePoint Revenue` /
  `ObservePoint Consultant`). Flags: `--dry-run`, `--force`.
- **Drive path resolution:** glob `$HOME/Library/CloudStorage/GoogleDrive-*` and append
  `Shared drives/Solutions Consulting/Claude/Plugins/<folder>`. Override with env
  `OP_PLUGIN_DRIVE_DIR` (points directly at the `<folder>`). If zero or multiple `GoogleDrive-*`
  mounts are found and no override is set → stop with a clear message.
- **Publish:** ensure `Old Versions/` exists; move every existing `*.plugin` in the top folder into
  `Old Versions/` (overwriting a same-named archive copy is fine); copy the new versioned file into
  the top folder.
- **Idempotent:** if the top folder already holds exactly this version, no-op unless `--force`.
- Prints exactly what it did (built vX, archived vY → Old Versions, published to `<path>`).

### `scripts/release.sh`
- Orchestrator: resolve name/version → `build_plugin.sh` → `publish_to_drive.py`.
- Flags pass through: `--force`, `--dry-run`.
- Safe to run by hand any time (the manual fallback for the chosen trigger).

### `scripts/hooks/release-check.sh` + `scripts/install-hooks.sh`
- `release-check.sh` (committed): the version-bump detector. Guards: only on branch `main`; compare
  `plugin.json` version at HEAD against the version embedded in the Drive folder's current
  `*.plugin` filename; if different, invoke `release.sh`. **Never aborts the git operation; always
  exits 0.** Near-instant no-op otherwise.
- `install-hooks.sh` (committed): one-time wiring that points `.git/hooks/post-commit` and
  `.git/hooks/post-merge` at `release-check.sh` (e.g. each hook is a 2-line shim that execs the
  committed script). No `post-checkout` (post-commit + post-merge cover the real workflows; manual
  `release.sh` covers the rest). Documented in `RELEASE.md`.

### `scripts/test_publish_to_drive.py`
- Pytest against a temp dir exercising the publish invariant: old `.plugin` moved to `Old Versions/`,
  new placed, **exactly one** `.plugin` in the top folder; `--dry-run` touches nothing; idempotent
  re-publish; `--force` re-publishes. Drive path injected via `OP_PLUGIN_DRIVE_DIR`.

### `.github/workflows/validate.yml`
- Revenue: **new.** Run the pytest suite + build the artifact as a **smoke test** (build + validate,
  **no Drive publish**). Catches a non-building/non-validating bundle in the cloud before the local
  hook runs.
- Consultant: already has `validate.yml` (`quick_validate.py` + `run_evals.py`); **extend** it with
  the same build-smoke-test step.

### `.gitignore`
- Add `dist/` in both repos so the `.plugin` artifacts stay **local and are never pushed**
  (requirement #2). (Revenue's `.gitignore` does not ignore it today.)

### `RELEASE.md` (new, per repo)
- The release flow, the one-time `./scripts/install-hooks.sh`, the `OP_PLUGIN_DRIVE_DIR` override,
  and how to publish manually (`./scripts/release.sh`, `--force`, `--dry-run`).

## Filename convention

`observepoint-<name>-<version>.plugin` — e.g. `observepoint-revenue-0.16.1.plugin`,
`observepoint-consultant-0.8.1.plugin`. The consultant's current unversioned
`observepoint-consultant.plugin` is replaced by the stamped name (confirmed).

## Error handling

- Build: hard-fail (non-zero) on validate failure or if `marketplace.json` leaks into the staging
  tree. The hook surfaces the message but still exits 0 so git is never blocked.
- Publish: hard-fail on unresolved/ambiguous Drive path (unless `OP_PLUGIN_DRIVE_DIR` set); no
  partial state (move-then-copy ordering means a failure leaves the old version archived and
  recoverable, never two currents).
- Hook: only acts on `main`; idempotent; double-firing (post-commit + post-merge) is harmless.

## Testing & verification

- `scripts/test_publish_to_drive.py` (added to each repo's pytest path).
- Manual end-to-end on the maintainer's Mac: bump version → commit on `main` → confirm
  `dist/<stamped>.plugin` exists locally and is gitignored; confirm the Drive top folder holds the
  new version and the prior one moved to `Old Versions/`; confirm `claude --plugin-dir <file>` (or
  Cowork upload) installs cleanly.
- Existing revenue suite (291 tests) must stay green; consultant suite likewise.

## Open assumptions to verify

- `claude plugin validate` is on the maintainer's PATH at release time (expected; it gates real
  releases).
- Google Drive for Desktop syncs writes into the mounted folder without extra steps (expected).
