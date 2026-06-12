# lessonweaver claims and receipts

This page lists the project claims that are intended to be verifiable from the
repository. Each claim includes receipts: tests, examples, docs, or commands
that a reviewer can run from the repository root.

## Claims

| Claim | What it means | Receipts |
| --- | --- | --- |
| Deterministic core, no LLM calls | Core modules parse traces, detect candidates, ask review questions, export artifacts, and load skills without calling a model provider. | `docs/architecture.md`; `examples/coding_agent_pr_review/README.md`; `examples/closed_loop_contextweaver/README.md`; the core import grep below should return no core model or HTTP client imports. |
| Conservative detection | Benign traces should stay quiet, and known detection gaps are tracked instead of hidden. | `tests/test_detection.py`; `tests/test_detection_eval.py`; `examples/detection_corpus/README.md`; `lessonweaver eval-detection examples/detection_corpus/corpus.json --min-precision 1.0`. |
| Human review gate before approval | A candidate is not approved into durable guidance until required review answers are present, unless an explicit incomplete-review override is recorded. | `tests/test_cli.py::test_cli_approve_blocks_incomplete_review`; `tests/test_cli.py::test_cli_review_trace_approve_blocked_when_incomplete`; `tests/test_cli.py::test_cli_review_trace_full_answers_then_approve`; `docs/developer-workflow.md`. |
| No automatic activation | Approval, promotion, export, and runtime loading are separate steps; activation requires lifecycle promotion and lint gates. | `docs/architecture.md`; `tests/test_cli.py::test_cli_promote_skill`; `tests/test_lint.py`; `tests/test_loader.py`; `lessonweaver promote-skill <skill-id> active` after review and lint. |
| Export is explicit and surface-specific | lessonweaver renders reviewed skills or lessons only when export commands are called, and supports the documented instruction surfaces. | `tests/test_export.py`; `tests/test_cli.py::test_cli_export_skill_agents_md`; `tests/test_cli.py::test_cli_export_skill_copilot_path_applies_to`; `tests/test_cli.py::test_cli_export_skill_codex_is_json_directory`; `lessonweaver export-skill examples/coding_agent_pr_review/skill.json --format agents-md --redact`. |
| File writes are diff-first and idempotent | Instruction-file writes preview a diff by default, preserve hand-written content, and update existing managed blocks instead of duplicating them. | `tests/test_cli.py::test_cli_export_file_default_previews_diff_without_writing`; `tests/test_cli.py::test_cli_export_file_write_creates_then_is_idempotent`; `tests/test_cli.py::test_cli_export_file_preserves_handwritten_content`; `docs/developer-workflow.md`. |
| Redaction is a best-effort safety net | Redaction handles obvious secrets and PII patterns before export, but it is not a compliance guarantee. | `tests/test_privacy.py`; `tests/test_export.py::test_export_redactor_integration`; `tests/test_cli.py::test_cli_detect_sanitize_runs_and_preserves_detection`; `README.md` governance notes; `lessonweaver export-skill examples/coding_agent_pr_review/skill.json --format copilot --redact`. |
| Closed-loop examples are reproducible | The repository includes synthetic examples that run the detect -> review -> approve -> export -> load loop without real user data or model calls. | `examples/coding_agent_pr_review/README.md`; `examples/closed_loop_contextweaver/README.md`; `tests/test_examples.py`; `PYTHONPATH=src uvx --python 3.10 python examples/closed_loop_contextweaver/example.py`; `docs/assets/demo.sh`. |
| Runtime loading is scoped and testable | Loading uses active skill cards, task relevance, scope, risk, max-result, and budget controls; retrieval correctness can be validated with suites. | `tests/test_loader.py`; `tests/test_retrieval.py`; `tests/test_validation.py`; `examples/coding_agent_pr_review/validation_suite.json`; `lessonweaver validate-skill examples/coding_agent_pr_review/validation_suite.json --skills-dir examples/coding_agent_pr_review`. |

## Quick receipt commands

These commands are useful when reviewing a release or a claim-changing PR:

```bash
! rg -n '^(from|import) (openai|anthropic|requests|httpx|aiohttp|urllib)\b' src tests
PYTHONPATH=src uvx pytest tests/test_detection.py tests/test_detection_eval.py -q
PYTHONPATH=src uvx pytest tests/test_cli.py tests/test_export.py tests/test_privacy.py -q
PYTHONPATH=src uvx pytest tests/test_examples.py tests/test_loader.py tests/test_validation.py -q
PYTHONPATH=src uvx --from . lessonweaver eval-detection examples/detection_corpus/corpus.json --min-precision 1.0
PYTHONPATH=src uvx --from . lessonweaver validate-skill examples/coding_agent_pr_review/validation_suite.json --skills-dir examples/coding_agent_pr_review
PYTHONPATH=src uvx --from . lessonweaver export-skill examples/coding_agent_pr_review/skill.json --format agents-md --redact
PYTHONPATH=src uvx --python 3.10 python examples/closed_loop_contextweaver/example.py
```

## Non-claims

lessonweaver does not claim to be any of the following:

- autonomous self-training;
- an observability platform or live telemetry collector;
- a generic memory system;
- an eval runner or model-output grader;
- a compliance-grade privacy or secret scanner;
- a guarantee that a downstream agent host will obey exported guidance.

For category boundaries, see [docs/comparisons.md](docs/comparisons.md) and
[docs/ecosystem.md](docs/ecosystem.md).
