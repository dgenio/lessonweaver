# GitHub Copilot Instructions

Read `AGENTS.md` for the full repository rules.

- Keep core code deterministic; do not add LLM calls to `src/lessonweaver/`.
- Keep framework dependencies out of core package code.
- Use `pytest`, and use `tmp_path` for filesystem tests.
- Keep detection conservative; false negatives are better than noisy lessons.
- Preserve human review and governed promotion before a skill becomes active.
- Treat traces and skill evidence as sensitive; use redaction before export.
