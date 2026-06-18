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
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/lessonweaver/
pytest
```

CI runs lint, type check, and tests on Python 3.10, 3.11, and 3.12. Run the
commands above locally before opening a PR so there are no surprises.

## Where to contribute

| Area | What it involves | Good entry point |
| --- | --- | --- |
| Examples | New synthetic traces and skills under `examples/` | Add a trace and document it in `examples/README.md` |
| Docs | Markdown under `docs/` | Fix or extend a page; keep it factual |
| Exporters | New `export_<format>_<target>` in `export.py` | One function + a snapshot test |
| Importers | Map an external format to the trace schema | Keep it dependency-free (see [interoperability](docs/interoperability.md)) |
| CLI | New subcommands or flags in `cli.py` | Add a flag + a `tests/test_cli.py` case |
| Governance checks | New `SkillLinter` / `SkillAnalyzer` rules | Add a rule + tests for true/false positives |

## Labels and triage

Labels describe what kind of work an issue needs, where it lands in the codebase,
and how urgent it is. Maintainers triage best-effort; these notes are routing
guidance, not a service-level guarantee.

| Label family | Meaning | Examples |
| --- | --- | --- |
| `type:*` | Primary work category | `type: docs`, `type: feature`, `type: integration`, `type: evals` |
| `area:*` | Main product surface touched | `area: traces`, `area: export`, `area: registry`, `area: examples` |
| `priority:*` | Maintainer priority signal | `priority: high`, `priority: medium`, `priority: low` |
| `ai-agent-ready` | The issue has enough scope and acceptance criteria for an AI coding assistant or first-pass contributor |
| `good-first-ai-issue` | A self-contained issue with a smaller review surface and explicit acceptance criteria |

Triage flow:

1. New issues should use a template and include reproduction steps, proposed
   scope, or acceptance criteria.
2. Maintainers add `type:*`, `area:*`, and `priority:*` labels when the path is
   clear enough to route.
3. `ai-agent-ready` means the issue is specified enough to attempt; it does not
   reserve the work.
4. Before starting, check for linked or open PRs that already cover the issue.
5. Questions, usage help, and early ideas belong in GitHub Discussions once the
   maintainer enables it for the repository.

## Good first issues

Self-contained, low-risk starting points should carry the
[`good-first-ai-issue`](https://github.com/dgenio/lessonweaver/issues?q=is%3Aissue+is%3Aopen+label%3Agood-first-ai-issue)
label. At the time of writing, current open starter candidates include:

- [#170](https://github.com/dgenio/lessonweaver/issues/170) — consolidate
  duplicated lexical utilities.
- [#177](https://github.com/dgenio/lessonweaver/issues/177) — align redaction
  defaults across export commands.
- [#181](https://github.com/dgenio/lessonweaver/issues/181) — clarify loading
  budget semantics.
- [#185](https://github.com/dgenio/lessonweaver/issues/185) — run the
  detection-eval corpus as a CI quality gate.

Browse the label query for the most current list, and avoid duplicating work if
an issue already has an active PR.

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
- Open large or uncertain work as a draft PR first; mark it ready for review
  after tests pass and the scope matches the issue.
- Run lint, format check, type check, and tests before requesting review.
- Do not add runtime dependencies casually; optional integrations go in
  `[project.optional-dependencies]`.
- Do not rename or remove dataclass fields without a migration note.
- Do not weaken review or promotion gates, and never commit real
  credentials or personal data.
- Maintainers review for scope, deterministic behavior, privacy, and test
  coverage before merge.

By contributing, you agree your contributions are licensed under the repository
[LICENSE](LICENSE).
