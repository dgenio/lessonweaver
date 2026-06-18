# Daily driver guide for coding-agent teams

Use this guide when a team wants lessonweaver in the normal coding-agent
workflow, not as a one-off demo. The operating loop is:

```text
collect trace -> detect candidate -> interview/review -> approve
-> export to an instruction surface -> reload agent context -> validate
```

Every step is explicit. lessonweaver does not rewrite agent instructions,
install skills, or activate unreviewed guidance automatically.

## 1. Collect a trace from real work

Keep the trace small enough for review, but complete enough to show the mistake
and correction. For coding agents, the highest-signal traces usually include:

- the task the agent was asked to do;
- the file, diff, PR, issue, or command context the agent saw;
- the wrong action or missed check;
- the human correction;
- any test, lint, review, or CI output that proves the correction mattered.

Store team traces in a project-local registry or a controlled folder. Avoid raw
secrets and private customer data. If a trace contains sensitive details, scrub
or summarize them before sharing it outside the team.

## 2. Detect and review the candidate

For day-to-day use, start with `review-trace` so the command prints the review
packet and shows what is still missing:

```bash
lessonweaver review-trace traces/agent-mistake.json \
  --registry-root .lessonweaver
```

Answer the required questions. Prefer narrow, testable guidance over broad
rules:

```bash
lessonweaver review-trace traces/agent-mistake.json \
  --registry-root .lessonweaver \
  --answer scope=project \
  --answer action_type=skill \
  --answer risk_level=medium \
  --answer applicability=conditional \
  --answer negative_conditions=not_relevant \
  --answer decision=approve \
  --target agents-md
```

If the issue is better handled by an eval, guardrail, workflow change, or human
documentation, choose that action type instead of forcing a skill. See
[When not to create a skill](when-not-to-create-a-skill.md).

## 3. Approve only reviewed guidance

Approve after the required review answers are complete:

```bash
lessonweaver review-trace traces/agent-mistake.json \
  --registry-root .lessonweaver \
  --answer scope=project \
  --answer action_type=skill \
  --answer risk_level=medium \
  --answer applicability=conditional \
  --answer negative_conditions=not_relevant \
  --answer decision=approve \
  --approve \
  --approved-by reviewer@example.com
```

The approval step records the reviewer and produces a reviewed skill card. Do
not load or commit candidate text directly. A `LessonCandidate` is evidence to
review, not guidance to inject.

## 4. Export to the surface your agent reads

Use redaction, inspect the output, and commit the final instruction change like
code.

### AGENTS.md

Preview a diff-first insertion:

```bash
lessonweaver export-file skill-id \
  --path AGENTS.md \
  --format agents-md \
  --registry-root .lessonweaver
```

Apply only after review:

```bash
lessonweaver export-file skill-id \
  --path AGENTS.md \
  --format agents-md \
  --write \
  --registry-root .lessonweaver
```

### GitHub Copilot

```bash
lessonweaver export-skill skill-id --format copilot-repo \
  --redact --registry-root .lessonweaver

lessonweaver export-skill skill-id --format copilot-path \
  --applies-to "src/**/*.py" \
  --redact --registry-root .lessonweaver
```

Review the fragment before placing it in `.github/copilot-instructions.md` or
`.github/instructions/<skill-id>.instructions.md`. See
[GitHub Copilot integration](integrations/github-copilot.md).

### Claude Code

```bash
lessonweaver export-skill skill-id --format claude-skill \
  --redact --registry-root .lessonweaver

lessonweaver export-skill skill-id --format claude-rule \
  --redact --registry-root .lessonweaver

lessonweaver export-skill skill-id --format claude-md \
  --redact --registry-root .lessonweaver
```

Review the output before placing it in a Claude skill, `.claude/rules/`, or
`CLAUDE.md`. See [Claude Code integration](integrations/claude-code.md).

### Codex

```bash
lessonweaver export-skill skill-id --format codex \
  --redact --registry-root .lessonweaver
```

The `codex` export emits a skill-directory payload. Review the generated
`SKILL.md` content before installing or loading it in a coding-agent context.

## 5. Reload and validate

After the instruction file or skill is reviewed and committed, start a fresh
agent session so the updated context is actually loaded.

Validate in two ways:

- Re-run the original scenario and confirm the same mistake does not recur.
- Add a retrieval validation suite when the skill should load only for specific
  tasks:

```bash
lessonweaver validate-skill examples/coding_agent_pr_review/validation_suite.json \
  --skills-dir examples/coding_agent_pr_review
```

Use `explain-load` when a skill loads too often or not at all:

```bash
lessonweaver explain-load "Review this PR for missing tests" \
  --agent-type coding \
  --tools github \
  --registry-root .lessonweaver
```

## Avoid instruction poisoning

Instruction poisoning happens when a raw observation becomes durable agent
guidance without enough review or scope control. Keep these rules in the daily
loop:

- Treat traces and candidates as untrusted evidence.
- Reject one-off, vague, or already-covered lessons.
- Prefer evals or guardrails when a behavior can be tested or blocked directly.
- Keep `applies_when` and `does_not_apply_when` narrow.
- Export with `--redact`, then read the result before committing.
- Do not paste raw user messages, secrets, stack traces, or private data into
  instruction files.
- Use `explain-load` and `cleanup-skills` to find stale, broad, or overlapping
  guidance.

## Copy-paste guidance for coding agents

Use this when asking a coding agent to help maintain a lessonweaver-backed
instruction library:

```text
When a repeated coding-agent mistake is corrected, capture only the task,
relevant context, failure, human correction, and verification evidence. Do not
turn the trace into instructions directly. Run lessonweaver detection, answer
the review questions, and approve only after the lesson is scoped, redacted, and
reviewed. Export reviewed guidance to the target instruction surface, inspect
the diff, then validate that the original mistake no longer recurs.
```

For concrete coding-agent export recipes, see
[Cookbook: Coding Agents](cookbook/coding-agents.md). For the broader command
workflow, see [Developer workflow](developer-workflow.md).
