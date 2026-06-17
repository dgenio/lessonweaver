# Glossary

Canonical terms used across lessonweaver code, docs, and issues. Where a term
maps to a Python class or enum value, the mapping is shown. Terms marked
**(planned)** are not yet implemented in `src/lessonweaver/` and link to the
tracking issue.

## Pipeline objects

- **Trace** — A raw agent execution log for one run. Class: `TraceBundle`
  (`models.py`). Loaded from JSON by `load_trace_bundle` (`traces.py`).
- **Trace event** — A single step within a trace (a message, tool call, error,
  correction, evaluation, or workflow step). Class: `TraceEvent`; kinds are the
  `TraceEventType` enum (`user_message`, `assistant_message`, `model_call`,
  `tool_call`, `tool_result`, `error`, `retry`, `human_correction`,
  `evaluation_result`, `final_answer`, `workflow_step`).
- **Lesson candidate** — A potential lesson extracted from a trace by
  deterministic detection. Not yet reviewed. Class: `LessonCandidate`; produced
  by `LessonDetector.detect` (`detection.py`).
- **Operational lesson** — A reviewed, annotated lesson that has been assessed
  and approved but is a lower-level artifact than a skill. Class:
  `OperationalLesson`.
- **Skill card** — A named, reviewed, exportable operational skill. The durable
  artifact produced when a reviewed lesson's action type is `skill`. Class:
  `SkillCard`.
- **Export artifact** — A rendered, downstream-ready output (Markdown, JSON,
  instruction fragment, runtime snippet) derived from a skill or lesson. Class:
  `ExportArtifact`; format values are the `ExportFormat` enum.

## Review and governance

- **Review question / review answer** — The multiple-choice interface used to
  review a candidate. Classes: `ReviewQuestion`, `ReviewOption`, `ReviewAnswer`;
  questions are built by `LessonInterviewer.build_questions` (`interview.py`).
- **Approval gate** — The human review checkpoint a candidate must pass before
  it becomes an approved lesson/skill. Enforced by the `approve` CLI flow and the
  governed promotion in `governance.py`.
- **Promotion** — Moving a skill through its governed lifecycle (for example
  `approved` → `experimental` → `active`). Function: `promote_skill`;
  precondition check: `can_promote_skill` (`governance.py`).
- **Lint finding** — A deterministic structural/governance check result on a
  skill. Class: `LintFinding`; severities are `LintSeverity`
  (`error`/`warning`/`info`); produced by `SkillLinter.lint` (`lint.py`).
- **Analysis finding** — A detected duplicate, overlap, or contradiction between
  skills. Class: `AnalysisFinding`; produced by `SkillAnalyzer.analyze`
  (`analysis.py`).

## Action types

The artifact a reviewed lesson should become. Enum: `RecommendedActionType`.

- **Skill** (`skill`) — Runtime behavioral guidance, exported as a `SkillCard`.
- **Instruction patch** (`instruction_patch`) — A missing system-prompt rule.
- **Eval spec** (`eval`) — A testable condition for an eval framework.
- **Guardrail rule** (`guardrail`) — A hard behavioral constraint.
- **Workflow change** (`workflow_change`) — A structural/process change rather
  than prompt guidance.
- **Retrieval rule** (`retrieval_rule`) — Guidance that depends on context only
  known at runtime.
- **Documentation** (`documentation`) — A note for humans, not agents.
- **Test** (`test`) — A regression test or checklist item.
- **Reject** (`reject`) — No durable artifact; discard the candidate.

See [when not to create a skill](when-not-to-create-a-skill.md) for choosing
between these.

## Scoring and quality

- **Confidence** — Estimated probability that a candidate represents a
  generalizable pattern. Field: `LessonCandidate.confidence` /
  `SkillCard.confidence` (float, `0.0`–`1.0`).
- **Evidence strength** *(planned, [#36](https://github.com/dgenio/lessonweaver/issues/36))* —
  A concept distinct from confidence: the quality, quantity, and directness of
  the trace evidence supporting a candidate. A high-confidence guess and a
  well-evidenced observation are not the same thing. Not yet a model field.

## Runtime retrieval

- **Retrieval** — Ranking active skills against a task query with a deterministic
  lexical baseline. Classes: `RetrievalQuery`, `RetrievalResult`,
  `SkillRetriever` (`retrieval.py`).
- **Compilation** — Assembling retrieved skills into a context-budgeted prompt
  snippet. Classes: `SkillCompiler`, `CompiledContext`; verbosity is the
  `InclusionLevel` enum (`compile.py`).
- **Skill loader** — The public facade combining registry, retrieval, and
  compilation. Class: `SkillLoader.load_for_task` (`loader.py`).
- **Loading policy** *(planned, [#41](https://github.com/dgenio/lessonweaver/issues/41))* —
  Rules controlling which skills are eligible for runtime injection (risk
  ceiling, allowed scopes, denylist, approval requirement). Not yet implemented.

## Classification metadata

- **Scope** — The organizational level at which a skill applies. Enum: `Scope`
  (`user`, `project`, `team`, `organization`, `global`).
- **Risk level** — The impact if the lesson is ignored or wrong. Enum:
  `RiskLevel` (`low`, `medium`, `high`).
- **Sensitivity level** — The confidentiality classification of a skill's
  content. Enum: `SensitivityLevel` (`public`, `internal`, `confidential`,
  `restricted`).
- **Lesson status** — Lifecycle state of a lesson/candidate. Enum:
  `LessonStatus` (`candidate`, `needs_review`, `approved`, `rejected`,
  `exported`, `deprecated`).
- **Skill status** — Lifecycle state of a skill. Enum: `SkillStatus` (`draft`,
  `approved`, `experimental`, `active`, `rejected`, `deprecated`).
- **Redaction** — Best-effort removal of obvious secrets/PII before export or
  pre-mining sanitization. `SimpleRedactor` and `TraceSanitizer` share one rule
  set and emit markers such as `[REDACTED by email]`. A safety net, not a
  compliance control.

## Registry

- **Registry** — Storage for lessonweaver objects. Classes (`registry.py`):
  `LessonRegistry` (in-memory; holds candidates and skills only) and
  `FileSystemRegistry` (JSON files under `~/.lessonweaver/registry` by default;
  persists candidates, skills, operational lessons, and artifacts).
