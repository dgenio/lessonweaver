# Developer workflow: trace → reviewed guidance → safe export

This is the recommended path for using lessonweaver day to day with coding
agents (VS Code / Copilot, Claude Code, AGENTS.md). It builds on the explicit
`detect → interview → answer → approve → export` subcommands — those remain the
canonical, scriptable API — and adds ergonomics and governance on top. Every
step stays deterministic: no LLM or network calls.

## One guided command: `review-trace`

Instead of memorizing the five-step pipeline, drive it from a single command:

```bash
# Detect candidates, save them, and print a guided review packet
lessonweaver review-trace trace.json --registry-root .lessonweaver

# Apply MCQ answers inline and preview an AGENTS.md export of the result
lessonweaver review-trace trace.json \
  --answer scope=project --answer action_type=skill --answer risk_level=low \
  --answer applicability=always --answer negative_conditions=none \
  --answer decision=approve \
  --target agents-md
```

The packet (JSON) lists, per detected candidate: the `remaining_questions`,
whether the review is `review_complete`, lint findings on the provisional skill,
and — with `--target FORMAT` — an `export_preview`. When a trace yields more than
one candidate, pass `--candidate <id>` to choose which one to answer or approve.

Approve in the same command once the review is complete:

```bash
lessonweaver review-trace trace.json --answer ... --approve --approved-by you
```

`--dry-run` detects and previews without saving candidates or persisting the
approval.

## The review gate is enforced

`approve` (and `review-trace --approve`) now **refuse to approve a candidate
until the required review questions are answered**. The adaptive interviewer
decides what "complete" means — a `reject` decision drops the scoping questions,
and `high` risk or a `workflow_change` action type queues a follow-up.

```bash
lessonweaver approve cand-1 --registry-root .lessonweaver
# Error: cannot approve 'cand-1': review is incomplete; unanswered required
# questions: scope, action_type, ... Answer them with `lessonweaver answer`,
# or pass --allow-incomplete-review to override.
```

For advanced/automated cases you can override with `--allow-incomplete-review`.
The override and the list of unanswered questions are recorded under
`incomplete_review_override` in the candidate and skill metadata
(`LessonCandidate.metadata` and `SkillCard.metadata`), so the bypass is
auditable.

## Diff-first file writes: `export-file`

`export-skill` prints export text; `export-file` puts it into a real instruction
file as a reviewable change. The skill is wrapped in id-keyed sentinels so a
later export of the same skill updates in place instead of appending a duplicate,
and hand-written content around it is preserved.

```bash
# Preview the unified diff (default — nothing is written)
lessonweaver export-file skill-1 --path AGENTS.md --format agents-md \
  --registry-root .lessonweaver

# Apply it
lessonweaver export-file skill-1 --path AGENTS.md --format agents-md --write
```

Redaction is on by default; pass `--no-redact` to disable it. `--dry-run`
forces preview even with `--write`. Re-running an unchanged export reports
`no changes` rather than rewriting the file. Review the diff like any code change
before committing.

## Eval before rollout

Before promoting a reviewed artifact to active use, generate a minimal positive
and negative retrieval suite and require it to pass:

```bash
# Generate a suite from an approved skill or candidate
lessonweaver generate-eval skill-1 --registry-root .lessonweaver > suite.json

# Inspect the pass/fail summary before promotion
lessonweaver validate-artifact skill-1 --eval-suite suite.json \
  --registry-root .lessonweaver

# Require the suite to pass before activation
lessonweaver promote-artifact skill-1 active --require-eval-pass \
  --eval-suite suite.json --registry-root .lessonweaver
```

Negative examples protect precision: a lesson that loads for unrelated tasks
fails rollout validation even if it loads for the intended positive case. If a
team intentionally accepts a failing suite, `--allow-eval-fail` records the
override in skill metadata under `eval_before_rollout`.

## Understand loading decisions: `explain-load`

A growing skill library poisons context if everything always loads. Diagnose
exactly what would load for a task, and why a skill was skipped:

```bash
lessonweaver explain-load "Review this PR" --agent-type coding --tools github \
  --registry-root .lessonweaver
# or, alongside the compiled snippet:
lessonweaver load "Review this PR" --explain
```

The output reports `loaded` skills (with score and match reason), `skipped`
skills with a reason code (`status_not_active`, `risk_above_threshold`,
`no_match`, `omitted_max_results`, `omitted_budget`), the context-`budget`
usage, and any `overlaps`/contradictions among the loaded skills.

## Keep the library healthy: `cleanup-skills`

Reviewed skills go stale, stop loading, start loading for the wrong tasks, or
pile up overlapping guidance. `cleanup-skills` aggregates those signals into
recommended actions (`retire`, `revise`, `narrow`):

```bash
# Report only (default)
lessonweaver cleanup-skills --registry-root .lessonweaver

# Apply the safe automated subset: deprecate expired skills via the lifecycle
lessonweaver cleanup-skills --registry-root .lessonweaver --write
```

`--write` only deprecates expired skills (through the governed
`ACTIVE`/`EXPERIMENTAL` → `DEPRECATED` transition); everything else stays
report-only for a human to act on. `--dry-run` never modifies the registry.
