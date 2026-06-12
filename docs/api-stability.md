# API Stability

lessonweaver is pre-1.0, but the top-level `lessonweaver` package is still a
public contract. This page defines which exported names are stable enough for
users to build on and which names may change as the project evolves.

The current public surface is the package `__all__` list in
`src/lessonweaver/__init__.py`. `tests/public_api_snapshot.json` pins that list
so every public-surface change is an intentional review diff.

## Tiers

| Tier | Meaning | Compatibility rule before 1.0 |
| --- | --- | --- |
| Stable | Core models, lifecycle APIs, import/export entry points, and deterministic runtime paths users should build on. | Breaking changes need a deprecation warning, a changelog migration note, and at least one minor release before removal. |
| Provisional | Useful public APIs that are expected to evolve while the product surface settles. | May change in a minor release, but changes need a changelog note and a replacement path when practical. |
| Internal | Exported today for historical convenience, tests, or advanced inspection. | May change or be demoted with a deprecation cycle; avoid new user code depending on it. |

Patch releases should avoid breaking any tier. Stable APIs may gain optional
fields, parameters, enum values, or methods when existing callers keep working.

## Deprecation Mechanics

When a stable export must be renamed, removed, or changed incompatibly:

1. Keep the old name importable and emit `DeprecationWarning` from the old entry
   point when possible.
2. Add a changelog entry with the replacement and migration instructions.
3. Keep the compatibility shim for at least one minor release.
4. Remove the shim only in a release that clearly calls out the break.

For data models persisted to disk, also include a migration note for existing
registry artifacts.

## Stable Exports

| Export | Why it is stable |
| --- | --- |
| `DictTraceImporter` | Minimal importer implementation for dictionary-backed traces. |
| `ExportArtifact` | Persisted export artifact model. |
| `ExportFormat` | Export format enum used by artifacts and CLI choices. |
| `FailureCaseImporter` | Built-in failure-case importer. |
| `FileSystemRegistry` | Reference registry implementation. |
| `LessonCandidate` | Core detected-lesson model. |
| `LessonDetector` | Deterministic detection entry point. |
| `LessonInterviewer` | Human-review question builder. |
| `LessonStatus` | Persisted lesson lifecycle enum. |
| `LoadingPolicy` | Runtime load policy model. |
| `OperationalLesson` | Reviewed lesson decision record. |
| `RecommendedActionType` | Persisted action-type enum. |
| `ReviewAnswer` | Persisted review answer model. |
| `ReviewOption` | Review option model. |
| `ReviewQuestion` | Review question model. |
| `ReviewSession` | Review session model. |
| `RiskLevel` | Persisted risk enum. |
| `Scope` | Persisted scope enum. |
| `SensitivityLevel` | Persisted sensitivity enum. |
| `SkillCard` | Durable reviewed skill model. |
| `SkillLoader` | Runtime loading facade. |
| `SkillStatus` | Persisted skill lifecycle enum. |
| `SkillUsageEvent` | Persisted skill usage event model. |
| `TraceBundle` | Core trace model. |
| `TraceEvent` | Core trace event model. |
| `TraceEventType` | Trace event type enum. |
| `TraceImporter` | Importer protocol for external trace formats. |
| `apply_review_answer` | Review mutation helper. |
| `candidates_from_failure_case` | Built-in failure-case import helper. |
| `export_agents_md_fragment` | Supported exporter entry point. |
| `export_claude_md_snippet` | Supported exporter entry point. |
| `export_claude_rule_fragment` | Supported exporter entry point. |
| `export_claude_skill_fragment` | Supported exporter entry point. |
| `export_claude_skill_md` | Supported exporter entry point. |
| `export_codex_skill_directory` | Supported exporter entry point. |
| `export_copilot_instruction_fragment` | Supported exporter entry point. |
| `export_copilot_path_instruction` | Supported exporter entry point. |
| `export_copilot_repo_instruction` | Supported exporter entry point. |
| `export_eval_spec_markdown` | Supported exporter entry point. |
| `export_guardrail_rule_markdown` | Supported exporter entry point. |
| `export_operational_lesson_markdown` | Supported exporter entry point. |
| `export_runtime_prompt_snippet` | Supported exporter entry point. |
| `export_skillcard_json` | Supported exporter entry point. |
| `export_skillcard_markdown` | Supported exporter entry point. |
| `export_workflow_recommendation_markdown` | Supported exporter entry point. |
| `load_trace_bundle` | Trace loading entry point. |
| `validate_trace_dict` | Trace validation entry point. |

## Provisional Exports

| Export | Why it is provisional |
| --- | --- |
| `AnalysisFinding` | Analysis API is useful but still evolving. |
| `CompiledContext` | Runtime compilation details may change with loader policy work. |
| `DetectionCase` | Detection-eval corpus format may evolve. |
| `DetectionCorpus` | Detection-eval corpus format may evolve. |
| `DetectionEvalReport` | Evaluation report shape may change as metrics grow. |
| `DetectionEvalResult` | Per-case evaluation result shape may change. |
| `InclusionLevel` | Compilation inclusion semantics may change. |
| `LintFinding` | Lint rule payloads may evolve. |
| `LintSeverity` | Lint severity values may evolve with policy gates. |
| `LoadDiagnostics` | Diagnostics shape may change as loader explanations improve. |
| `LoadedSkill` | Diagnostics detail model. |
| `RetrievalDiagnostics` | Retrieval explanation model. |
| `RetrievalQuery` | Retrieval inputs may expand for embedding and policy work. |
| `RetrievalResult` | Retrieval scoring details may change. |
| `SanitizationRule` | Sanitizer rule model may expand. |
| `SkillAnalyzer` | Analysis facade. |
| `SkillCleaner` | Cleanup facade. |
| `SkillCompiler` | Prompt compiler facade. |
| `SkillEvalResult` | Validation result detail. |
| `SkillLinter` | Lint facade. |
| `SkillReporter` | Reporting facade. |
| `SkillRetriever` | Retrieval facade; lexical behavior remains the stable default. |
| `StaleSkillReport` | Reporting payload. |
| `TraceSanitizer` | Sanitization facade. |
| `ValidationExample` | Validation-suite model. |
| `ValidationResult` | Validation-suite result model. |
| `ValidationSuite` | Validation-suite model. |
| `can_promote_skill` | Lifecycle guard helper. |
| `explain_load` | Loader diagnostics helper. |
| `promote_skill` | Lifecycle promotion helper. |
| `run_detection_eval` | Detection-eval runner. |
| `run_validation_suite` | Validation-suite runner. |

## Internal Exports

These remain exported for compatibility, but new user code should prefer the
stable or provisional APIs above.

| Export | Notes |
| --- | --- |
| `FAILURE_CASE_PROVENANCE_KEY` | Importer metadata key; likely to move behind importer helpers. |
| `BudgetUsage` | Diagnostics detail model. |
| `CleanupAction` | Cleanup detail model. |
| `LessonCluster` | Clustering detail model. |
| `LessonClusterer` | Clustering implementation detail until recurring-pattern APIs settle. |
| `LessonRegistry` | Historical registry alias/protocol; prefer `FileSystemRegistry`. |
| `SimpleRedactor` | Best-effort helper; export redaction APIs are preferred. |
| `SkippedSkill` | Retrieval diagnostics detail. |
| `diff_managed_file` | Low-level file-merge helper. |
| `has_managed_block` | Low-level file-merge helper. |
| `load_session` | Review-session storage helper. |
| `managed_block` | Low-level file-merge helper. |
| `merge_managed_block` | Low-level file-merge helper. |
| `save_session` | Review-session storage helper. |

## Path To 1.0

Before 1.0, the project should shrink or confirm the internal tier, promote
settled provisional APIs, and document migration paths for any demoted exports.
After 1.0, stable-tier breaking changes should wait for a major version.
