# Changelog fragments

Add a small fragment file here instead of editing `CHANGELOG.md` directly, so
concurrent pull requests never collide on the same lines (issue #343).

## How to add an entry

Create a file named `<issue-number>.<category>.md`, for example
`342.changed.md`, containing the Markdown bullet(s) for your change:

```markdown
- `eval-detection` now prints exactly what drifted on a benchmark mismatch (#345).
```

`<category>` is one of the Keep a Changelog sections, matching the ones this
project uses:

- `added` — new features, commands, or capabilities.
- `changed` — changes to existing behavior.
- `deprecated`, `removed`, `fixed`, `security` — as needed.

Keep the wording consistent with existing `CHANGELOG.md` entries and end each
bullet with the issue/PR reference (`(#123)`).

## How fragments become the changelog

At release time the maintainer runs:

```bash
python scripts/build_changelog.py --version X.Y.Z
```

This folds every fragment into a new dated `## [X.Y.Z]` section under
`## [Unreleased]` (in Keep a Changelog order), then deletes the consumed
fragments. Preview the result without writing anything using `--dry-run`. The
output is deterministic, so the assembled section diffs cleanly in review.
