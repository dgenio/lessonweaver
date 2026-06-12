# Security model: avoiding instruction poisoning

lessonweaver is designed to turn agent failures into reviewed guidance without
letting an agent rewrite its own future behavior. The security boundary is the
reviewed artifact: traces and candidates are evidence, not instructions.

## Threat model

Instruction poisoning happens when untrusted or low-confidence content becomes
durable agent guidance. Common paths include:

- a trace contains adversarial user text and that text is exported directly;
- a one-off failure becomes an always-loaded skill;
- a generated rule bypasses human review and lands in `AGENTS.md`, Copilot,
  Claude, Codex, or runtime prompts;
- a broad skill loads for unrelated tasks and overrides local project policy;
- sensitive trace content is copied into exported instructions.

lessonweaver reduces these risks by separating detection, review, approval,
promotion, retrieval, and export. For the pipeline mechanics, see
[Architecture](architecture.md); for the day-to-day command workflow, see
[Developer workflow](developer-workflow.md).

## Trust boundaries

| Artifact | Trust level | Safe use |
| --- | --- | --- |
| `TraceBundle` | Untrusted evidence | Detect candidates; sanitize before storage when needed. |
| `LessonCandidate` | Unreviewed hypothesis | Review, reject, or convert to a non-skill artifact. |
| `OperationalLesson` | Reviewed decision record | Keep as audit evidence for why guidance exists. |
| `SkillCard` in `approved` status | Reviewed, not necessarily active | Export intentionally or promote through the lifecycle. |
| `SkillCard` in `active` status | Loadable runtime guidance | Retrieve with scope, risk, and budget controls. |
| Exported instruction text | Downstream project policy | Review diffs before committing or loading. |

Unknown metadata is preserved for auditability, but it is not automatically
trusted as guidance.

## Human review gate

The review gate is the primary defense. Detection is conservative, but a detected
candidate is still only a hypothesis. A reviewer must answer the adaptive review
questions and choose a disposition such as `skill`, `eval`, `guardrail`,
`workflow_change`, `documentation`, or `reject`.

`approve` and `review-trace --approve` refuse incomplete reviews unless
`--allow-incomplete-review` is passed. Overrides are explicit and recorded in
metadata so downstream reviewers can see the bypass.

## Promotion gate

Approval does not mean global activation. The skill lifecycle is guarded:

```text
draft -> approved -> experimental -> active -> deprecated
```

Promotion to `active` runs `SkillLinter` and blocks skills with ERROR findings,
including missing applicability bounds or missing instructions. High-risk active
skills must record an approver. This keeps reviewed but narrow lessons from
silently becoming broad runtime policy.

## Export boundaries

Exports are explicit commands. lessonweaver does not write instruction files
unless a user calls `export-file --write`, and that path is diff-first and
idempotent. The caller chooses the target surface:

- `agents-md` for `AGENTS.md`;
- `copilot`, `copilot-repo`, and `copilot-path` for GitHub Copilot;
- `claude-skill`, `claude-rule`, and `claude-md` for Claude-style surfaces;
- `codex` for a Codex skill directory;
- `runtime` for prompt snippets;
- `export-lesson` for eval, guardrail, and workflow recommendation artifacts.

Treat generated output like code: inspect the diff, verify the scope, and commit
only reviewed guidance.

## Redaction boundary

`SimpleRedactor` and trace sanitization are deterministic safety nets for obvious
emails, bearer tokens, API keys, AWS access keys, and private-key headers. They
are not compliance-grade privacy controls.

Use `--redact` before export, but do not rely on redaction alone. The safer path
is to keep raw trace evidence out of durable instructions and use evidence ids,
summaries, and reviewed guidance instead.

## Activation boundaries

Loading is intentionally filtered. `SkillRetriever`, `SkillCompiler`, and
`SkillLoader` select active skills by task relevance, scope, risk, max results,
and character budget. Use `explain-load` to see why a skill loaded or was
skipped.

Do not point runtime loaders at unreviewed candidates or draft skills. If a team
wants to experiment with draft guidance, keep it outside the production registry
or load it manually in a non-production prompt.

## Non-goals

- lessonweaver does not autonomously rewrite agent behavior.
- lessonweaver does not self-train from traces or worker findings.
- lessonweaver does not replace policy enforcement, tests, evals, or human code
  review.
- lessonweaver does not provide compliance-grade secret detection or privacy
  scanning.
- lessonweaver does not guarantee that downstream agent hosts will honor
  exported instructions exactly as written.

## Operational checklist

- Keep raw traces in a controlled registry location.
- Sanitize traces before sharing them outside the team.
- Reject candidates that are one-off, vague, or already covered by stronger
  policy.
- Prefer evals, guardrails, workflow changes, or documentation when runtime
  guidance is the wrong control.
- Export with redaction enabled and review the result before committing.
- Promote to `active` only after lint passes and ownership is clear.
- Periodically run `explain-load`, `analyze-skills`, and `cleanup-skills` to
  catch drift, overlap, and context poisoning.

For candidate disposition guidance, see
[When not to create a skill](when-not-to-create-a-skill.md).
