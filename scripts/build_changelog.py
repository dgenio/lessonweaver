#!/usr/bin/env python3
"""Assemble changelog fragments from ``changelog.d/`` into ``CHANGELOG.md``.

Contributors drop a small fragment file named ``<issue>.<category>.md`` under
``changelog.d/`` instead of editing ``CHANGELOG.md`` directly, so concurrent
pull requests never collide on the same lines (issue #343). At release time this
script folds the fragments into a new dated version section, in Keep a Changelog
order, and removes the consumed fragments.

Usage::

    python scripts/build_changelog.py --version 0.5.0
    python scripts/build_changelog.py --version 0.5.0 --dry-run

The output is deterministic (fragments sorted by filename, categories in a fixed
order), so re-running it produces byte-identical results.

This is release tooling only; it is intentionally dependency-free (stdlib) and
lives outside ``src/lessonweaver/`` so it never touches the runtime import graph.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

# Keep a Changelog categories, in the order they should appear in a section.
CATEGORIES = ["added", "changed", "deprecated", "removed", "fixed", "security"]

REPO_ROOT = Path(__file__).resolve().parent.parent
FRAGMENTS_DIR = REPO_ROOT / "changelog.d"
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"
UNRELEASED_HEADER = "## [Unreleased]"


def collect_fragments(fragments_dir: Path) -> dict[str, list[str]]:
    """Return fragment bodies grouped by category, ordered by filename.

    Each fragment is named ``<issue>.<category>.md`` where ``<category>`` is one
    of :data:`CATEGORIES`. ``README.md`` is ignored so the directory can document
    itself.
    """
    grouped: dict[str, list[str]] = {category: [] for category in CATEGORIES}
    for path in sorted(fragments_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        parts = path.name.split(".")
        if len(parts) != 3 or parts[2] != "md":
            raise ValueError(
                f"{path.name}: fragments must be named '<issue>.<category>.md' "
                f"(category one of: {', '.join(CATEGORIES)})"
            )
        category = parts[1].lower()
        if category not in grouped:
            raise ValueError(
                f"{path.name}: unknown category '{category}' "
                f"(expected one of: {', '.join(CATEGORIES)})"
            )
        body = path.read_text(encoding="utf-8").strip()
        if body:
            grouped[category].append(body)
    return grouped


def render_section(version: str, date: str, grouped: dict[str, list[str]]) -> str:
    """Render a single ``## [version] - date`` section from grouped fragments."""
    lines = [f"## [{version}] - {date}", ""]
    for category in CATEGORIES:
        entries = grouped.get(category, [])
        if not entries:
            continue
        lines.append(f"### {category.capitalize()}")
        lines.append("")
        lines.extend(entries)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def insert_section(original: str, section: str) -> str:
    """Insert ``section`` between the ``## [Unreleased]`` block and the next release.

    The new dated section is placed just before the first ``## [`` release header
    that follows ``## [Unreleased]`` (or at end of file if there is none), so any
    notes that happen to live under ``## [Unreleased]`` stay there instead of
    being absorbed into the new release. Blank lines around the inserted block are
    normalized locally rather than by rewriting the whole file.
    """
    lines = original.splitlines(keepends=True)
    unreleased_idx = next(
        (i for i, line in enumerate(lines) if line.strip() == UNRELEASED_HEADER),
        None,
    )
    if unreleased_idx is None:
        raise ValueError(f"CHANGELOG has no '{UNRELEASED_HEADER}' section to insert after.")

    # First release header after Unreleased, or end of file.
    insert_idx = next(
        (i for i in range(unreleased_idx + 1, len(lines)) if lines[i].startswith("## [")),
        len(lines),
    )

    before = lines[:insert_idx]
    after = lines[insert_idx:]
    while before and before[-1].strip() == "":
        before.pop()

    block = section if section.endswith("\n") else section + "\n"
    return "".join([*before, "\n", block, "\n", *after])


def build_changelog(version: str, date: str, changelog_path: Path, fragments_dir: Path) -> str:
    """Return the updated CHANGELOG text with a new section for ``version``."""
    grouped = collect_fragments(fragments_dir)
    if not any(grouped.values()):
        raise ValueError(f"No changelog fragments found in {fragments_dir}.")
    section = render_section(version, date, grouped)
    original = changelog_path.read_text(encoding="utf-8")
    return insert_section(original, section)


def _consumed_fragments(fragments_dir: Path) -> list[Path]:
    return [p for p in sorted(fragments_dir.glob("*.md")) if p.name != "README.md"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assemble changelog fragments into CHANGELOG.md.")
    parser.add_argument("--version", required=True, help="Version number for the new section.")
    parser.add_argument(
        "--date",
        default=datetime.now(timezone.utc).date().isoformat(),
        help="Release date (YYYY-MM-DD); defaults to today (UTC).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the updated CHANGELOG to stdout without writing or deleting fragments.",
    )
    args = parser.parse_args(argv)

    updated = build_changelog(args.version, args.date, CHANGELOG_PATH, FRAGMENTS_DIR)

    if args.dry_run:
        print(updated, end="")
        return 0

    CHANGELOG_PATH.write_text(updated, encoding="utf-8")
    for fragment in _consumed_fragments(FRAGMENTS_DIR):
        fragment.unlink()
    print(f"Wrote {CHANGELOG_PATH} and removed consumed fragments from {FRAGMENTS_DIR}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
