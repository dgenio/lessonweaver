# Cookbook: repository-check findings as reviewed lessons

Repository checkers (lint gates, secret scanners, policy gates) produce
structured findings on agent-authored diffs. When the same finding keeps coming
back, that is a repeatable signal worth turning into a reviewed operational
lesson — so future agent runs get the guidance *before* repeating the mistake.

> human correction on a flagged finding → reviewed lesson → exported instruction
> → future coding-agent context.

Tracking issue: [#75](https://github.com/dgenio/lessonweaver/issues/75).
**lessonweaver never injects unreviewed instructions automatically.** Every
recipe ends at a fragment you review before committing.

## The loop

1. A coding agent produces a problematic diff.
2. A deterministic checker flags it (a structured finding with id, severity, path).
3. A human reviews or fixes it (the correction).
4. lessonweaver captures the repeated pattern as a reviewed lesson.
5. Future runs receive better instructions before repeating the mistake.

## Input trace shape

Model the gate finding as a `tool_result` event carrying the finding metadata,
followed by the `human_correction` that resolved it. Use the bundled example:

```bash
lessonweaver detect examples/traces/repo_check_finding.json
```

[`examples/traces/repo_check_finding.json`](../../examples/traces/repo_check_finding.json)
records a `LW-SECRET-001` finding (hardcoded credential) and the human correction
to load the value from the environment. It produces exactly one `human_correction`
candidate — the failing-then-passing gate is intentionally *not* modelled as a
failed-then-successful tool call, so it does not also fire the tool-fallback
signal.

## Mapping a finding into a candidate

| Finding field | Where it goes |
| --- | --- |
| finding id (`LW-SECRET-001`) | `TraceEvent.metadata["finding_id"]`, kept as evidence |
| severity | `TraceEvent.metadata["severity"]` (informs reviewer risk choice) |
| path | `TraceEvent.metadata["path"]` |
| the human fix/comment | a `human_correction` event — the detection signal |

Detection stays conservative: the candidate is a hypothesis. The reviewer
decides whether it should become a durable instruction.

## Review questions to ask

- Is this a **recurring** pattern or a one-off? Only durable patterns earn a skill.
- What is the **scope** — this repo, this team, or every project?
- What is the **risk** if the guidance is wrong or over-applied?
- Should the fix be an **instruction**, a **guardrail/eval**, or just a checker
  rule that already covers it?

## Export to an instruction surface

After approval, export the reviewed skill to the surface your agents read:

```bash
# AGENTS.md fragment
lessonweaver export-skill <skill-id-or-json> --format agents-md

# GitHub Copilot repository instructions
lessonweaver export-skill <skill-id-or-json> --format copilot-repo

# Claude Code rule
lessonweaver export-skill <skill-id-or-json> --format claude-rule
```

## Safeguards against over-learning

- **Prefer the checker.** If a deterministic gate already catches the finding,
  a new instruction may be redundant noise — see
  [when not to create a skill](../when-not-to-create-a-skill.md).
- **Require repetition.** One finding is not a pattern; wait for recurrence.
- **Redact evidence.** Findings can contain secrets or PII; exports redact by
  default. Use `--no-redact` only when you intentionally need raw content, and
  review the fragment before committing.
- **Keep scope tight.** A repo-specific finding rarely deserves global scope.
