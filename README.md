# lessonweaver

**Turn agent execution traces into reviewed, governed instructions that prevent
repeated operational mistakes.**

AI agents repeat avoidable mistakes: skipping evidence checks, using stale
context, validating too late, or missing governance constraints. lessonweaver is
a small, **deterministic** loop that finds those patterns in execution traces,
puts a **human review gate** in front of them, and exports approved guidance back
into agent context. No LLM calls in the core, no automatic self-training, no
skill activation without review.

## Before / after

- **Before:** A coding agent "reviews" a PR from the title and description
  without inspecting the diff. A human corrects it. The same mistake recurs next
  week.
- **Trace:** The run is recorded, including the `human_correction` event.
- **lessonweaver:** Detects a conservative candidate, a human reviews it via
  multiple-choice questions, and approves it into a reviewed skill.
- **After:** The reviewed lesson is exported as a Markdown/runtime snippet and
  pasted into `AGENTS.md` / Copilot / Claude instructions, so future sessions
  start with "inspect the changed files first."

## What it is / what it is not

| It is | It is not |
| --- | --- |
| A reviewed-guidance layer over agent traces | An agent framework or orchestrator |
| A deterministic detect → review → export loop | An observability/telemetry product |
| A producer of governed instruction fragments | An eval runner |
| Human-gated and auditable | Autonomous self-training or generic memory |

lessonweaver **complements** observability, evals, and memory — see
[comparisons](docs/comparisons.md) and [ecosystem](docs/ecosystem.md).

## Quickstart

lessonweaver is not yet on PyPI (planned,
[#64](https://github.com/dgenio/lessonweaver/issues/64)). Install from source:

```bash
pip install -e ".[dev]"

# 1. Detect candidates from a trace and save them to a temporary registry
lessonweaver detect examples/traces/github_pr_review_failure.json \
  --save --registry-root /tmp/lw

# 2. Generate review questions
lessonweaver interview trace-gh-pr-review-001-human-correction --registry-root /tmp/lw

# 3. Record a review answer
lessonweaver answer trace-gh-pr-review-001-human-correction decision approve \
  --free-text "Diff inspection is required before review conclusions." \
  --registry-root /tmp/lw

# 4. Approve into an operational lesson and skill
lessonweaver approve trace-gh-pr-review-001-human-correction \
  --approved-by reviewer --registry-root /tmp/lw

# 5. Export the reviewed skill for an instruction surface
lessonweaver export-skill skill-trace-gh-pr-review-001-human-correction \
  --format markdown --redact --registry-root /tmp/lw
```

Drop `--registry-root /tmp/lw` to use the default `~/.lessonweaver/registry`.
For full recipes, see the [coding-agent cookbook](docs/cookbook/coding-agents.md).

## Runtime loading

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
- `lessonweaver answer <candidate-id> <question-id> <option-id> [--free-text ...]`
- `lessonweaver approve <candidate-id> [--approved-by ...]`
- `lessonweaver export-skill <skill-id-or-json> --format markdown|json|copilot|copilot-repo|copilot-path|claude|claude-skill|claude-rule|claude-md|agents-md|codex|runtime [--applies-to GLOB] [--redact]`
- `lessonweaver export-lesson <candidate-id-or-json> --format eval|guardrail|workflow [--redact]`
- `lessonweaver lint <skill-id-or-json>`
- `lessonweaver analyze-skills <skills-dir>`
- `lessonweaver retrieve "<task>"`
- `lessonweaver load "<task>"`
- `lessonweaver validate-skill <suite.json> [--skills-dir DIR | --registry-root ROOT]`
  - Suite JSON: `{"suite_id": "s1", "skill_id": "pr-review", "examples": [{"example_id": "pos", "task": "Review this pull request", "should_load": true}, {"example_id": "neg", "task": "Generate a SQL migration", "should_load": false}]}`. Negative examples (`should_load=false`) measure precision; the command prints the eval result as JSON and exits `0` when every example passes, `1` otherwise.
- `lessonweaver promote-skill <skill-id> <target-status>`

## Supported outputs and integrations

| Integration | Status |
| --- | --- |
| Markdown skill cards | Supported |
| JSON skill cards | Supported |
| GitHub Copilot instruction fragments | Supported (`copilot`, `copilot-repo`, `copilot-path`) |
| Claude Code skill / rule / CLAUDE.md exports | Supported (`claude`, `claude-skill`, `claude-rule`, `claude-md`) |
| Generic runtime prompt snippets | Supported |
| Codex skill directory export | Supported (`codex`) |
| AGENTS.md fragment export | Supported (`agents-md`) |
| Eval / guardrail / workflow exports | Supported (`export-lesson`) |
| LlamaIndex, OpenAI Agents SDK, Pipecat | Planned adapters (#20, #21, #22) |

## Governance and safety

- Detection is conservative; false negatives are preferred over noisy guidance.
- Human review is the expected governance step before a lesson becomes an
  approved skill; the workflow requires it, though the `approve` command does not
  yet enforce that review questions were answered.
- `experimental` skills must pass governed lifecycle checks (lint with no errors)
  before becoming `active`.
- `SimpleRedactor` is a best-effort safety net before export, not a compliance
  control.
- Skills carry owner, approver, expiration, sensitivity, scope, and evidence
  metadata.

See [when not to create a skill](docs/when-not-to-create-a-skill.md) — turning
every observation into a skill causes context poisoning.

## Anti-goals

- No LLM-based lesson generation in the core library.
- No automatic skill injection without human approval.
- No agent orchestration or framework lock-in.
- No replacement for evals, tests, or review gates.
- No compliance-grade privacy scanner.

## Roadmap

Grouped by adoption path (tracking issues):

- **Operational memory:** [#57](https://github.com/dgenio/lessonweaver/issues/57)
- **Runtime lesson retrieval API:** [#59](https://github.com/dgenio/lessonweaver/issues/59)
- **Eval companion:** [#60](https://github.com/dgenio/lessonweaver/issues/60)
- **Closed-loop effectiveness measurement:** [#61](https://github.com/dgenio/lessonweaver/issues/61)
- **Policy-gated lesson promotion:** [#62](https://github.com/dgenio/lessonweaver/issues/62)

## Documentation

- [Architecture](docs/architecture.md) — modules, data flow, lifecycle
- [Glossary](docs/glossary.md) — canonical terms
- [Comparisons](docs/comparisons.md) — vs. observability, evals, memory, frameworks
- [Ecosystem positioning](docs/ecosystem.md) — integration boundaries
- [When not to create a skill](docs/when-not-to-create-a-skill.md)
- [Coding-agent cookbook](docs/cookbook/coding-agents.md)
- [Interoperability](docs/interoperability.md)
- [Trace format](docs/trace-format.md)
- [Repository readiness](docs/repository-readiness.md)
- [Examples](examples/README.md)
- [Agent instructions](AGENTS.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for principles, local development, and
good first issues.

```bash
pip install -e ".[dev]"
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/lessonweaver/
pytest
```
