# Failure case → reviewed lesson candidate

This example shows the governed path from a **replayable failure case** to a
reviewed lesson candidate (issue #82). A failure case is a reproducible failure
artifact — for example, one discovered by fuzzing/property testing and captured
with a replay reference. lessonweaver maps it into the normal
`detect → review → approve → export` loop; it never promotes a lesson
automatically.

The accepted artifact shape mirrors the planned weaver-spec
`FailureCaseArtifact` (dgenio/weaver-spec#72) and is documented in
[`docs/adapters.md`](../../docs/adapters.md). The provenance (`failure_id`,
replay reference, severity) is preserved on every resulting candidate under
`metadata["failure_case"]` so a reviewer can always replay the original
failure.

## Run it

```bash
lessonweaver import-failure-case examples/failure_cases/replayable_eval_failure.json
```

This imports the artifact, runs the conservative detector, and prints the
candidate lessons as JSON — each stamped with its failure-case provenance. The
sample artifact carries both a failed evaluation and a human correction, so it
produces two candidates (a failed-eval signal and a human-correction signal).

Save them into the registry to continue with `interview` → `answer` →
`approve`, exactly as for any other trace:

```bash
lessonweaver import-failure-case examples/failure_cases/replayable_eval_failure.json --save
```

## Why review is still required

A single failure case is **evidence, not a skill**. The agent that hit it may
have been misconfigured, the failure may be a one-off, or the right fix may be a
deterministic guardrail rather than a prompt skill. The human-review gate (and
[when not to create a skill](../../docs/when-not-to-create-a-skill.md)) decides
whether the pattern is worth a reusable lesson.
