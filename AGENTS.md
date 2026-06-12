# Agent Instructions

## Project Purpose

lessonweaver converts AI-agent execution traces into reviewed, reusable operational lessons. Human review is always required before a lesson becomes an active skill.

## Core Design Principles

- Conservative by default: detection should produce fewer, higher-quality candidates.
- Human review before activation: skills must be reviewed and approved before becoming active.
- No LLM in the core: detection, interview, linting, retrieval, and analysis are deterministic.
- No mandatory framework dependencies: framework integrations belong in `examples/`, not `src/lessonweaver/`.
- Stable data models: do not rename or remove dataclass fields without a migration plan.

## Testing Expectations

- Tests live in `tests/`.
- Use `pytest`.
- Use `tmp_path` for filesystem tests.
- Do not make real API calls in tests.
- Do not make real LLM calls in tests.
- Each new module should have a corresponding `tests/test_<module>.py`.
- Prefer small dataclass factory helpers for repeated test data.

## Dependency Policy

- Do not add runtime dependencies unless the issue explicitly allows it and the benefit is clear.
- Optional integrations go in `[project.optional-dependencies]`.
- Do not add `langchain`, `openai`, `anthropic`, or other AI framework packages as core dependencies.
- Developer tooling belongs in the `dev` optional dependency group.

## Adding a Detection Signal

1. Add the smallest deterministic rule to `LessonDetector` in `detection.py`.
2. Call it from `LessonDetector.detect()`.
3. Add unit tests for the true positive, false positive prevention, and edge cases.
4. Keep detection conservative; prefer false negatives over false positives.
5. Run `lessonweaver eval-detection examples/detection_corpus/corpus.json`
   before opening the PR. The CI gate enforces the current corpus floors
   (`--min-precision 1.0 --min-recall 0.833`); intentional floor changes must
   update `.github/workflows/ci.yml` in the same PR with a short justification.

## Adding an Export Format

1. Add a function to `export.py` named `export_<format>_<target>`.
2. Add the format to the CLI only when users can call it directly.
3. Add a snapshot-style test for stable text output.
4. Do not change existing export behavior unless the issue requires it.

## Adding an Adapter Example

1. Create `examples/<framework_name>_runtime_loader/`.
2. Use `try/except ImportError` for optional framework imports.
3. Bundle a minimal example registry if needed.
4. Do not add the framework as a core dependency.

## Safety and Privacy Rules

- Never add real API keys, tokens, credentials, or user secrets.
- Treat trace content as potentially sensitive.
- Use `SensitivityLevel` metadata and `SimpleRedactor` before export.
- Do not generate fake trace data that contains real-looking personal data.

## What Not To Do

- Do not add LLM inference calls to `detection.py` or `interview.py`.
- Do not add real credentials anywhere in the repository.
- Do not change `LessonStatus` or `SkillStatus` values without updating lifecycle guards.
- Do not skip review or promotion gates in examples.
