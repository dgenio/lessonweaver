# Changelog

All notable changes to lessonweaver are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

lessonweaver has not yet been published to PyPI. The `0.1.0` and `0.2.0`
entries below were reconstructed from the repository history to seed the
changelog; their dates are the dates of the corresponding work landing on
`main`, not PyPI release dates.

## [Unreleased]

### Added

- `CHANGELOG.md`, `CODE_OF_CONDUCT.md`, and `SECURITY.md` for OSS health.
- README status badges (CI, Python versions, license, PyPI).
- GitHub issue forms (bug, feature, trace importer, example request) and a pull
  request template under `.github/`.
- `docs/release.md` release checklist and a "Part of the Weaver Stack"
  README section with a closed-loop diagram.

### Changed

- README quickstart distinguishes the user install (`pip install lessonweaver`)
  from the contributor install (`pip install -e ".[dev]"`).

## [0.2.0] - 2026-05-30

### Added

- Export breadth: GitHub Copilot (`copilot`, `copilot-repo`, `copilot-path`),
  Claude Code (`claude`, `claude-skill`, `claude-rule`, `claude-md`), Codex
  (`codex`), and `agents-md` skill exporters, plus `export-lesson` for
  `eval`, `guardrail`, and `workflow` artifacts.
- Governed skill lifecycle: `promote-skill` with guarded transitions and a lint
  gate on activation, a skill usage log (`log-usage`), and stale/unused skill
  reporting (`report-stale`).
- Retrieval validation suites with precision/recall (`validate-skill`).
- Adaptive multiple-choice review with resumable, persisted sessions
  (`resume-interview`, `interview --session`, `answer --session`).
- CLI ergonomics: `--output`, `--dry-run`, `--json` flags and non-zero exit
  codes on bad input.
- Adoption and positioning documentation (comparisons, ecosystem,
  interoperability, integration guides, cookbooks).

## [0.1.0] - 2026-05-26

### Added

- Core trace model (`TraceBundle`, `TraceEvent`) and JSON loading.
- Conservative, deterministic `LessonDetector` with no LLM calls in the core.
- Multiple-choice review interview (`LessonInterviewer`).
- Filesystem registry for candidates, lessons, skills, and artifacts.
- Skill linting, lexical retrieval, snippet compilation, and the `SkillLoader`
  runtime facade.
- Markdown, JSON, and runtime-snippet skill exporters.
- Command-line interface wiring the modules together.

[Unreleased]: https://github.com/dgenio/lessonweaver/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/dgenio/lessonweaver/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/dgenio/lessonweaver/releases/tag/v0.1.0
