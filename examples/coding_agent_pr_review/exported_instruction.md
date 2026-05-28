# Exported instruction fragment

Generated from `skill.json` (status: approved) with `lessonweaver export-skill ... --format copilot` and `--format agents-md`.
Review it before pasting into an instruction surface.

## GitHub Copilot fragment (`--format copilot`)

```text
- Skill: Pull request diff-first review discipline
- Use when: reviewing pull requests; performing code review on changed files; checking pull requests for test coverage
- Avoid when: purely administrative requests with no code changes
- Do: Fetch and inspect changed files and diffs before stating review conclusions.; Confirm that code changes include matching test coverage.; If diffs are unavailable, state that limitation and avoid definitive approval.
```

## AGENTS.md fragment (`--format agents-md`)

```markdown
<!-- lessonweaver skill_id=skill-pr-review-diff-discipline confidence=0.62 -->
### Pull request diff-first review discipline

**When to apply:** reviewing pull requests; performing code review on changed files; checking pull requests for test coverage
**Do not apply when:** purely administrative requests with no code changes

- Fetch and inspect changed files and diffs before stating review conclusions.
- Confirm that code changes include matching test coverage.
- If diffs are unavailable, state that limitation and avoid definitive approval.
```
