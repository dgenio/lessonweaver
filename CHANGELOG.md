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

- Detection corpus metric floors are documented, and clustering regression
  coverage now asserts input-order invariance and threshold-boundary behavior
  (#282).

### Changed

- `export-lesson` now uses the shared human-review gate and blocks candidates
  with unanswered review questions unless `--allow-incomplete-review` is passed
  (#163).

## [0.4.0] - 2026-06-16

### Added

- Developer-workflow commands for the coding-agent learning loop, documented in
  [`docs/developer-workflow.md`](docs/developer-workflow.md):
  - `review-trace` — one guided command that detects candidates, applies MCQ
    answers (`--answer q=opt`), optionally approves (`--approve`), and prints a
    review packet with remaining questions, lint findings, and an export preview
    (#106).
  - `export-file` — diff-first, idempotent insertion of a skill into an
    instruction file (`AGENTS.md`, `copilot-instructions.md`, `CLAUDE.md`, ...)
    using id-keyed managed blocks; previews a unified diff by default and writes
    only with `--write` (redacts by default; `--no-redact` to disable) (#107).
  - `explain-load` and `load --explain` — explain which skills load or are
    skipped (with reason codes), context-budget usage, and overlaps/contradictions
    among the loaded set; new `SkillRetriever.diagnose` and `explain_load` API (#110).
  - `cleanup-skills` — aggregate stale, low-confidence, never-used, noisy, and
    overlapping skills into recommended actions; `--write` deprecates expired
    skills through the governed lifecycle (#112).

### Changed

- `LoadingPolicy.max_token_budget` was renamed to `max_budget_chars` to match
  the character-based loader/compiler budget semantics; serialized policies
  using the old `max_token_budget` key still load as a deprecated fallback.
- `SimpleRedactor` and `TraceSanitizer` now use one shared redaction rule set,
  emit named `[REDACTED by <rule>]` markers, and no longer fail open by returning
  raw export text when a redaction rule raises (#176).
- `export-skill`, `export-lesson`, and `review-trace --target` now redact by
  default, matching `export-file`; pass `--no-redact` to emit raw content (#177).
- Registry defaults now resolve consistently for CLI and library callers:
  explicit `--registry-root`, `LESSONWEAVER_REGISTRY`, nearest project-local
  `.lessonweaver/registry/`, then the existing `~/.lessonweaver/registry`
  fallback (#180).

- `approve` now enforces the human-review gate: a candidate must have answered
  the required (adaptive) review questions before it can be approved. Use
  `--allow-incomplete-review` to override; the bypass and the unanswered
  questions are recorded in the candidate and skill metadata (#108).
- `apply_review_answer` now returns a new candidate instead of mutating the
  input candidate in place; callers should use the returned value (#173).
- CLI validation failures now consistently print `Error:` on stderr; malformed
  `answer` question/option inputs now exit `2` like other invalid inputs (#174).
- Lexical tokenization, stopword sets, Jaccard similarity, and retrieval
  synonym expansion now live in one private text utility module (#170).
- `SkillLoader`, stale reporting, and cleanup now depend on a `SkillStore`
  protocol so `FileSystemRegistry` and the in-memory `LessonRegistry` can be
  substituted consistently (#172).
- `detect --save` and `review-trace` now preserve existing candidates that
  already have review state; pass `--force` to overwrite them explicitly (#164).

- `CHANGELOG.md`, `CODE_OF_CONDUCT.md`, and `SECURITY.md` for OSS health.
- README status badges (CI, Python versions, license, PyPI).
- GitHub issue forms (bug, feature, trace importer, example request) and a pull
  request template under `.github/`.
- `docs/release.md` release checklist and a "Part of the Weaver Stack"
  README section with a closed-loop diagram.
- `TraceImporter` protocol with `DictTraceImporter` and a `docs/adapters.md`
  normalization contract (#52).
- `TraceSanitizer` pre-mining sanitization and a `detect --sanitize` flag (#46).
- `FailureCaseImporter`, `candidates_from_failure_case`, and an
  `import-failure-case` CLI command for replayable failure artifacts (#82),
  with an example under `examples/failure_cases/`.
- Sibling interop adapters (vibeguard, agent-kernel, ChainWeaver) under
  `examples/interop_adapters/` (#91).
- `docs/design/opentelemetry-import.md` design sketch for future OTel import
  (#27).
- Workflow-step detection signal: a `WORKFLOW_STEP` event preceding an error or
  human correction now yields a conservative `WORKFLOW_CHANGE` candidate, with an
  `examples/traces/workflow_validation_failure.json` fixture (#55).
- `LessonClusterer` / `LessonCluster` group recurring candidates across traces by
  lexical similarity, plus a `cluster` CLI command (#37).
- Detection-quality harness: `DetectionCorpus` / `run_detection_eval` report
  precision/recall/F1 against a labeled corpus, an `eval-detection` CLI command
  with `--min-precision` / `--min-recall` CI gates, and a baseline corpus under
  `examples/detection_corpus/` (#86).
- Closed-loop keystone example under `examples/closed_loop_contextweaver/`: a
  coding-agent failure → reviewed skill card → loaded back into agent context,
  plus the skill-card interchange-format notes for contextweaver ingestion (#92).
- `docs/assets/demo.sh`, a reproducible ~60-second closed-loop terminal demo, and
  `docs/awesome-list-submissions.md` listing copy (#88).

### Changed

- README hero now leads with the skills / `AGENTS.md` framing and the
  human-review-gate differentiator, with the recognizable export surfaces up
  front (#85).
- README quickstart distinguishes the user install (`pip install lessonweaver`)
  from the contributor install (`pip install -e ".[dev]"`).
- `load_trace_bundle` now delegates to `DictTraceImporter` (behavior unchanged).

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

[Unreleased]: https://github.com/dgenio/lessonweaver/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/dgenio/lessonweaver/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/dgenio/lessonweaver/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/dgenio/lessonweaver/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/dgenio/lessonweaver/releases/tag/v0.1.0
