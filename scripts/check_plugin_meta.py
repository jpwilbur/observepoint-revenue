#!/usr/bin/env python3
"""Pre-publish metadata checks that mirror the Cowork / plugin-directory UPLOAD
validation — which is stricter than `claude plugin validate` and rejects bundles
the CLI happily passes. These are the rules that otherwise only surface as
"Plugin upload failed" at install time:

  - plugin.json `description` must be <= 500 characters
  - no skill `SKILL.md` frontmatter `description` may contain XML tags (`<...>`)

Run against a plugin directory (the staged build tree or the source plugin dir):

    check_plugin_meta.py <plugin-dir>

Exit 0 when clean, 1 on any violation (with a per-violation message), 2 on usage error.
Stdlib only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MAX_PLUGIN_DESCRIPTION = 500
XML_TAG = re.compile(r"<[^>]+>")


def frontmatter_description(skill_md_text):
    """Return the `description` value from a SKILL.md YAML frontmatter block, or None.

    Handles a single-line value and folded continuation lines (everything up to
    the next top-level `key:` or the end of the frontmatter).
    """
    if not skill_md_text.startswith("---"):
        return None
    parts = skill_md_text.split("---", 2)
    if len(parts) < 3:
        return None
    frontmatter = parts[1]
    m = re.search(r"(?ms)^description:[ \t]*(.+?)(?=^\w[\w-]*:|\Z)", frontmatter)
    return m.group(1).strip() if m else None


def check(plugin_dir):
    """Return a list of human-readable violation strings (empty list == clean)."""
    plugin_dir = Path(plugin_dir)
    errors = []

    manifest = plugin_dir / ".claude-plugin" / "plugin.json"
    if not manifest.is_file():
        return ["no .claude-plugin/plugin.json found under %s" % plugin_dir]

    try:
        data = json.loads(manifest.read_text())
    except json.JSONDecodeError as e:
        return ["plugin.json is not valid JSON: %s" % e]

    description = data.get("description", "") or ""
    if len(description) > MAX_PLUGIN_DESCRIPTION:
        errors.append(
            "plugin.json description is %d chars (max %d)"
            % (len(description), MAX_PLUGIN_DESCRIPTION)
        )

    for skill_md in sorted(plugin_dir.glob("skills/*/SKILL.md")):
        desc = frontmatter_description(skill_md.read_text())
        if desc is None:
            continue
        tags = sorted(set(XML_TAG.findall(desc)))
        if tags:
            rel = skill_md.relative_to(plugin_dir)
            errors.append(
                "%s description cannot contain XML tags: %s" % (rel, ", ".join(tags))
            )

    return errors


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: check_plugin_meta.py <plugin-dir>", file=sys.stderr)
        return 2

    errors = check(argv[0])
    if errors:
        print("Plugin metadata check FAILED (%d):" % len(errors), file=sys.stderr)
        for e in errors:
            print("  - %s" % e, file=sys.stderr)
        print(
            "These rules mirror the Cowork upload validator, which is stricter than "
            "`claude plugin validate`.",
            file=sys.stderr,
        )
        return 1

    print("Plugin metadata check passed (description <= %d chars, no XML tags in skill descriptions)." % MAX_PLUGIN_DESCRIPTION)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
