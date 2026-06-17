# Contributing to lessonweaver

Thanks for your interest. lessonweaver is a small, deterministic library with a
clear set of principles. Contributions that respect those principles are easy to
review and merge.

Read [AGENTS.md](AGENTS.md) for the full agent/contributor rules and
[docs/architecture.md](docs/architecture.md) for how the pieces fit together.
Significant architecture changes should add or supersede an
[Architecture Decision Record](docs/adr/README.md).

## Project principles

- **Deterministic core.** No randomness in detection, interview, lint,
  retrieval, or analysis.
- **No LLM calls in core.** Do not add inference calls to `src/lessonweaver/`.
  LLM-backed helpers, if any, go behind an optional interface.
- **Human review before activation.** A candidate becomes an active skill only
  after review and governed promotion.
- **Privacy and governance first.** Treat traces and skill evidence as
  sensitive; redact before export.
- **No framework lock-in.** Framework integrations live in `examples/`, never as
  core dependencies.

## Local development

```bash
# Setup (editable install with dev tooling)
pip install -e ".[dev]"

# Lint, format check, type check, tests — the same checks CI runs
pre-commit run --all-files
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/lessonweaver/
pytest
```

CI runs pre-commit, lint, type check, and tests on Python 3.10, 3.11, and 3.12.
Run the commands above locally before opening a PR so there are no surprises.

## Where to contribute

| Area | What it involves | Good entry point |
| --- | --- | --- |
| Examples | New synthetic traces and skills under `examples/` | Add a trace and document it in `examples/README.md` |
| Docs | Markdown under `docs/` | Fix or extend a page; keep it factual |
| Exporters | New `export_<format>_<target>` in `export.py` | One function + a snapshot test |
| Importers | Map an external format to the trace schema | Keep it dependency-free (see [interoperability](docs/interoperability.md)) |
| CLI | New subcommands or flags in `cli.py` | Add a flag + a `tests/test_cli.py` case |
| Governance checks | New `SkillLinter` / `SkillAnalyzer` rules | Add a rule + tests for true/false positives |

## Good first issues

Self-contained, low-risk starting points (open at the time of writing):

- **Examples:** add a trace such as `tool_api_fallback.json`
  ([#32](https://github.com/dgenio/lessonweaver/issues/32)); usefulness report
  example ([#73](https://github.com/dgenio/lessonweaver/issues/73)).
- **Templates:** issue/PR templates
  ([#34](https://github.com/dgenio/lessonweaver/issues/34),
  [#70](https://github.com/dgenio/lessonweaver/issues/70)).

Browse the issue tracker for the most current list and labels.

## Testing expectations

- Tests live in `tests/` and use `pytest`.
- Use `tmp_path` for filesystem tests; never write to a real home directory.
- No real API or LLM calls in tests.
- Each new module gets a corresponding `tests/test_<module>.py`.
- Prefer small dataclass factory helpers for repeated test data.
- A new behavior should have a test that fails without the change and passes
  with it.

## Pull request expectations

- Keep PRs focused; describe what changed and why.
- Run lint, format check, type check, and tests before requesting review.
- Do not add runtime dependencies casually; optional integrations go in
  `[project.optional-dependencies]`.
- Do not rename or remove dataclass fields without a migration note.
- Do not weaken review or promotion gates, and never commit real
  credentials or personal data.

By contributing, you agree your contributions are licensed under the repository
[LICENSE](LICENSE).
