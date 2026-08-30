<!--
Thanks for contributing to lessonweaver. Keep PRs focused and small.
See CONTRIBUTING.md and AGENTS.md for the project principles.
-->

## What changed

<!-- Bullet list of the changes, ideally file by file. -->

## Why

<!-- Link the issue (e.g. "Closes #123") and the rationale grounded in it. -->

Closes #

## How verified

<!-- Exact commands run and their results. -->

- [ ] `python scripts/check.py` — the full required gate (lint, format check,
      type check, tests, detection-benchmark guard). `--list` shows the exact
      commands it runs, which are the ones CI runs.

## Checklist

- [ ] Changes are scoped to the linked issue (no unrelated refactors).
- [ ] Core stays deterministic — no LLM or network calls added to `src/lessonweaver/`.
- [ ] No runtime dependencies added casually (optional integrations go in extras / `examples/`).
- [ ] No dataclass fields renamed/removed without a migration note.
- [ ] New behavior has a test that fails without the change and passes with it.
- [ ] No real credentials or personal data added (traces/examples are synthetic).
- [ ] Docs updated if user-facing behavior changed; a `changelog.d/` fragment
      added for notable changes (see `changelog.d/README.md`) instead of editing
      `CHANGELOG.md` directly.
