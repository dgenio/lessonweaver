# lessonweaver

**Turn agent traces into reviewed, reusable operational lessons.**

lessonweaver is a framework-agnostic system for converting AI-agent execution traces into governed operational improvements.

It is **not** generic memory, **not** autonomous self-training, and **not** a replacement for evals.

It **is** a governed loop for mining, reviewing, and exporting trace-backed lessons:

`trace → candidate lesson → MCQ review → approved skill/instruction/eval/guardrail/workflow recommendation → runtime reuse`

## What it does

A lesson is an evidence-backed insight extracted from an agent interaction, such as:

- An agent skipped PR diff inspection before reviewing.
- A chatbot used stale policy context.
- A workflow validated too late.
- A specialist agent missed a governance/security constraint.

A reviewed lesson can become:

- Skill card
- Instruction patch
- Eval spec
- Guardrail rule
- Workflow recommendation
- Retrieval rule
- Documentation/test/checklist update
- Rejected lesson

## Quickstart

```bash
pip install -e .
lessonweaver detect examples/traces/github_pr_review_failure.json
```

## MVP flow

1. Load trace bundle
2. Detect conservative lesson candidates
3. Run guided MCQ review interview
4. Export approved artifact

## Example outputs

- Markdown SkillCard
- JSON SkillCard
- GitHub Copilot instruction fragment
- Claude-style skill markdown fragment
- Generic runtime prompt snippet

## Future integrations

- GitHub Copilot via `.github/copilot-instructions.md` and `.github/instructions/*.instructions.md`
- Claude Code via `CLAUDE.md`, `.claude/rules`, and skills
- LlamaIndex applications
- OpenAI Agents SDK / ChatKit-style apps
- Pipecat voice agents
- Internal specialist agents
- Intelligent workflows

## Design principles

- Conservative by default
- Human review before activation
- Evidence-backed lessons
- Skills include applicability and negative conditions
- Not every lesson should become a skill
- Some lessons should become evals/guardrails/workflow changes/docs/tests
- Avoid leaking sensitive trace data

## Development

```bash
pip install -e .[dev]
pytest
```
