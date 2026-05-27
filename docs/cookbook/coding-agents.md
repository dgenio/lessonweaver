# Cookbook: Coding Agents

Practical recipes for using lessonweaver with the instruction surfaces that
coding agents read. The adoption path is always the same:

> human correction from coding-agent work → reviewed lesson → exported
> instruction → future coding-agent context.

**lessonweaver never injects unreviewed instructions automatically.** Every
recipe ends at a fragment you review before committing.

## Shared starting point

These recipes use the bundled trace and a temporary registry so they do not
touch your home directory.

```bash
# 1. Detect candidates and save them to a temporary registry
lessonweaver detect examples/traces/github_pr_review_failure.json \
  --save --registry-root /tmp/lw

# 2. Review: answer at least the decision question
lessonweaver answer trace-gh-pr-review-001-human-correction decision approve \
  --free-text "Diff inspection is required before review conclusions." \
  --registry-root /tmp/lw

# 3. Approve into an operational lesson + skill
lessonweaver approve trace-gh-pr-review-001-human-correction \
  --approved-by reviewer --registry-root /tmp/lw
# -> prints {"candidate_id": ..., "lesson_id": ..., "skill_id": "skill-trace-gh-pr-review-001-human-correction"}
```

The approved skill id is `skill-trace-gh-pr-review-001-human-correction`. Each
recipe below exports that skill into a different surface.

## 1. AGENTS.md workflow

```bash
lessonweaver export-skill skill-trace-gh-pr-review-001-human-correction \
  --format markdown --redact --registry-root /tmp/lw
```

- Put generated content under a clearly marked section (for example
  `## Reviewed operational lessons`) so it stays separate from hand-written
  project rules.
- **Review before use:** read the fragment, confirm it contains no raw trace
  evidence, then paste it into `AGENTS.md` and commit it like any other change.

> A dedicated `agents-md` export format is planned
> ([#48](https://github.com/dgenio/lessonweaver/issues/48)). Until then, use
> `markdown` or `runtime`.

## 2. GitHub Copilot instruction workflow

```bash
lessonweaver export-skill skill-trace-gh-pr-review-001-human-correction \
  --format copilot --redact --registry-root /tmp/lw
```

- The output is a compact bullet fragment (skill, use-when, avoid-when, do).
- **Review before use:** append it to `.github/copilot-instructions.md`
  manually. Do not auto-append; do not add raw evidence.

## 3. Claude Code / Claude-style skill workflow

```bash
lessonweaver export-skill skill-trace-gh-pr-review-001-human-correction \
  --format claude --redact --registry-root /tmp/lw
```

- The output is a `##`-titled skill fragment with description, when-to-apply,
  and instructions.
- **Review before use:** use it as reviewed project guidance. Claude Code
  formats may evolve; treat the export as a starting point.

## 4. Manual fallback workflow

```bash
lessonweaver export-skill skill-trace-gh-pr-review-001-human-correction \
  --format markdown --redact --registry-root /tmp/lw > reviewed-lesson.md
```

- Copy `reviewed-lesson.md` into a team knowledge base or review checklist.
- **Review before use:** treat it as a human-facing document; trim anything
  that is not actionable.

## 5. Governance checklist

Before any exported fragment is loaded into an agent, confirm:

- [ ] **Who approved it** — `approved_by` is recorded on the skill.
- [ ] **Evidence** — the skill lists at least one `evidence_trace_ids` entry.
- [ ] **Scope** — `scope` matches where the guidance should apply.
- [ ] **Risk and review** — high-risk active skills must record an approver
      (enforced by `SkillLinter` rule `LW006`).
- [ ] **Expiry / revisit** — note when the lesson should be re-reviewed.
- [ ] **When not to load it** — `does_not_apply_when` is populated.
- [ ] **No secrets** — exported with `--redact`; content checked by a human.

## Notes

- Available export formats today: `markdown`, `json`, `copilot`,
  `copilot_instruction`, `claude`, `claude_skill`, `runtime`.
- Drop `--registry-root /tmp/lw` to use the default `~/.lessonweaver/registry`.
- See the [glossary](../glossary.md) and [architecture](../architecture.md) for
  the underlying model, and [when not to create a skill](../when-not-to-create-a-skill.md)
  before promoting a candidate.
