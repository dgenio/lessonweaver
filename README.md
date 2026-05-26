# lessonweaver

**lessonweaver** converts AI-agent execution traces into reviewed, reusable operational lessons.

Agents often repeat avoidable mistakes: skipping evidence checks, using stale context, validating too late, or missing governance constraints. lessonweaver gives teams a small, deterministic loop for finding those patterns in traces, reviewing them with humans, and exporting approved guidance back into agent context. The core library is rule-based by design: no LLM calls, no automatic self-training, and no skill activation without review.

## Core Loop

1. Emit a trace from an agent run.
2. Run `lessonweaver detect` to identify conservative lesson candidates.
3. Run `lessonweaver interview` and record MCQ review answers.
4. Approve the candidate into an operational lesson and skill.
5. Export or retrieve the active skill for a future agent session.

## Quickstart

```powershell
pip install -e ".[dev]"

lessonweaver detect examples/traces/github_pr_review_failure.json --save
lessonweaver interview trace-gh-pr-review-001-human-correction
lessonweaver answer trace-gh-pr-review-001-human-correction decision approve --free-text "Diff inspection is required before review conclusions."
lessonweaver approve trace-gh-pr-review-001-human-correction --approved-by reviewer
lessonweaver export-skill skill-trace-gh-pr-review-001-human-correction --format markdown --redact
```

Use `--registry-root <path>` on those commands to keep examples in a temporary registry instead of the default `~/.lessonweaver/registry`.

## Trace Snippet

```json
{
  "trace_id": "trace-gh-pr-review-001",
  "source": "github_coding_agent",
  "task": "Review pull request quality",
  "events": [
    {"id": "e1", "type": "user_message", "content": "Please review this PR."},
    {"id": "e2", "type": "assistant_message", "content": "Looks good from title and description."},
    {"id": "e3", "type": "human_correction", "content": "You did not inspect changed files/diff before reviewing."}
  ],
  "outcome": "corrected_by_human"
}
```

## Review Snippet

```json
{
  "id": "decision",
  "question": "What is the review decision?",
  "recommended_option_id": "needs_review",
  "options": [
    {"id": "approve", "label": "A", "description": "Approve lesson"},
    {"id": "needs_review", "label": "B", "description": "Needs more review"},
    {"id": "reject", "label": "C", "description": "Reject lesson"}
  ]
}
```

## Skill Output

```markdown
# PR Diff-First Review Discipline

## Description
Always inspect changed files/diff before delivering review conclusions.

## Use when
- Reviewing pull requests with code changes.

## Instructions
- Fetch and inspect changed files first.
- Base review findings on concrete diff evidence.

## Evidence
- trace: trace-gh-pr-review-001
```

## Runtime Loading

```python
from lessonweaver import FileSystemRegistry, SkillLoader

registry = FileSystemRegistry()
loader = SkillLoader(registry=registry)

context = loader.load_for_task(
    task="Review this PR for security issues",
    agent_type="coding",
    tools=["github"],
    scope="project",
    budget_chars=2000,
)
print(context.snippet)
```

## Commands

- `lessonweaver detect <trace.json> [--save]`
- `lessonweaver interview <candidate-id-or-json>`
- `lessonweaver answer <candidate-id> <question-id> <option-id>`
- `lessonweaver approve <candidate-id>`
- `lessonweaver export-skill <skill-id-or-json> --format markdown|json|copilot|claude|runtime`
- `lessonweaver lint <skill-id-or-json>`
- `lessonweaver analyze-skills <skills-dir>`
- `lessonweaver retrieve "<task>"`
- `lessonweaver load "<task>"`
- `lessonweaver promote-skill <skill-id> <target-status>`

## Anti-Goals

- No LLM-based lesson generation in the core library.
- No automatic skill injection without human approval.
- No agent orchestration or framework lock-in.
- No replacement for evals, tests, or review gates.
- No compliance-grade privacy scanner.

## Safety and Governance

- Detection is conservative; false negatives are preferable to noisy guidance.
- Human review is required before a lesson becomes an approved skill.
- `experimental` skills must pass governed lifecycle checks before becoming `active`.
- `SimpleRedactor` is a safety net before export, not the primary privacy control.
- Skills can carry owner, approver, expiration, sensitivity, and evidence metadata.

## Integrations

| Integration | Status |
| --- | --- |
| Markdown skill cards | Supported |
| GitHub Copilot instruction fragments | Supported |
| Claude-style skill fragments | Supported |
| Generic runtime prompt snippets | Supported |
| Codex directory export | Model enum reserved |
| LlamaIndex, OpenAI Agents SDK, Pipecat | Planned adapters |

## Development

```powershell
pip install -e ".[dev]"

ruff check src/ tests/
ruff format --check src/ tests/
mypy src/lessonweaver/
pytest
```

## Links

- [Trace format](docs/trace-format.md)
- [Agent instructions](AGENTS.md)
- [Examples](examples/README.md)
