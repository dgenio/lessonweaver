# Examples

This directory contains sample traces, skill outputs, and worked end-to-end
examples. All data is synthetic — no real usernames, tokens, or PII.

## Traces

Expected candidate count is what `LessonDetector.detect()` produces for the
trace. Detection is conservative, so "boring" traces produce zero candidates.

| Trace | Scenario | Expected candidates |
| --- | --- | --- |
| `traces/github_pr_review_failure.json` | Human correction shows diff inspection was skipped. | 1 |
| `traces/external_chatbot_policy_failure.json` | Failed evaluation shows stale policy-version usage. | 1 |
| `traces/specialist_agent_governance_miss.json` | Governance miss corrected by a human reviewer. | 1 |
| `traces/voice_slot_correction.json` | Voice slot correction for time and location. | 1 |
| `traces/tool_api_fallback.json` | API call is rate-limited (429); agent falls back to a cached result. | 1 |
| `traces/repo_check_finding.json` | A repository-check finding plus a human correction. | 1 |
| `traces/workflow_validation_order.json` | Workflow validation order with no candidate signal (the boring case). | 0 |
| `traces/workflow_validation_failure.json` | A workflow step promotes to production before validation, then fails. | 1 |

## Detection corpus

- [`detection_corpus/`](detection_corpus/) — a labeled corpus of should-detect /
  should-not-detect traces and a precision/recall/F1 scorecard. Run it with
  `lessonweaver eval-detection examples/detection_corpus/corpus.json`.

## Skills

- `skills/github_pr_review_discipline.md` — example exported skill markdown.
- `skills/chatbot_policy_version_check.md` — example policy-version skill markdown.
- `skills/voice_slot_repair.md` — example voice slot-repair skill markdown.

## Worked examples

- [`closed_loop_contextweaver/`](closed_loop_contextweaver/) — the closed-loop
  keystone: a coding-agent failure → reviewed skill card → loaded back into an
  agent's context for the next run. The flagship "sum > parts" demo.
- [`coding_agent_pr_review/`](coding_agent_pr_review/) — the main end-to-end
  example: multiple PR-review traces, an approved skill, a validation suite, and
  the exported instruction fragment.
- [`usefulness_report/`](usefulness_report/) — count how often one reviewed
  skill would have been retrieved across a set of traces.

## Framework integration examples

Each is dependency-optional and runs the lessonweaver portion even when the
framework is not installed.

- [`llamaindex_runtime_loader/`](llamaindex_runtime_loader/) — load skills into a
  LlamaIndex system prompt.
- [`openai_agents_runtime_loader/`](openai_agents_runtime_loader/) — load skills
  into OpenAI Agents SDK instructions.

See also [docs/integrations/pipecat.md](../docs/integrations/pipecat.md) for the
voice-agent pattern using `traces/voice_slot_correction.json` and
`skills/voice_slot_repair.md`.
For a full chatbot and voice walkthrough, see the
[conversational-agent cookbook](../docs/cookbook/conversational-agents.md).
