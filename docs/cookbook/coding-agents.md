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
  --format agents-md --registry-root /tmp/lw
```

- The output is a compact `###`-titled fragment (with an HTML comment carrying
  the skill id) suitable for inclusion in `AGENTS.md`.
- Put generated content under a clearly marked section (for example
  `## Reviewed operational lessons`) so it stays separate from hand-written
  project rules.
- **Review before use:** read the fragment, confirm it contains no raw trace
  evidence, then paste it into `AGENTS.md` and commit it like any other change.

## 2. GitHub Copilot instruction workflow

```bash
# Compact bullet fragment
lessonweaver export-skill skill-trace-gh-pr-review-001-human-correction \
  --format copilot --registry-root /tmp/lw

# Repository-wide block for .github/copilot-instructions.md
lessonweaver export-skill skill-trace-gh-pr-review-001-human-correction \
  --format copilot-repo --registry-root /tmp/lw

# Path-specific file for .github/instructions/<id>.instructions.md
lessonweaver export-skill skill-trace-gh-pr-review-001-human-correction \
  --format copilot-path --applies-to "src/**/*.py" --registry-root /tmp/lw
```

- **Review before use:** append the output to the relevant Copilot instruction
  file manually. Do not auto-append; do not add raw evidence. See
  [docs/integrations/github-copilot.md](../integrations/github-copilot.md).

## 3. Claude Code / Claude-style skill workflow

```bash
# Full SKILL.md (claude-rule and claude-md produce shorter fragments)
lessonweaver export-skill skill-trace-gh-pr-review-001-human-correction \
  --format claude-skill --registry-root /tmp/lw
```

- `claude-skill` emits a full SKILL.md; `claude-rule` targets `.claude/rules/`
  and `claude-md` targets `CLAUDE.md`. The legacy `claude` format still emits the
  original short fragment.
- **Review before use:** use it as reviewed project guidance. Claude Code
  formats may evolve; treat the export as a starting point. See
  [docs/integrations/claude-code.md](../integrations/claude-code.md).

## 4. Manual fallback workflow

```bash
lessonweaver export-skill skill-trace-gh-pr-review-001-human-correction \
  --format markdown --registry-root /tmp/lw > reviewed-lesson.md
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
- [ ] **No secrets** — export redaction stayed enabled, and content was checked
      by a human.

## Notes

- Skill export formats: `markdown`, `json`, `copilot`, `copilot_instruction`,
  `copilot-repo`, `copilot-path`, `claude`, `claude_skill`, `claude-skill`,
  `claude-rule`, `claude-md`, `agents-md`, `codex`, `runtime`.
- Non-skill candidates (eval / guardrail / workflow recommendations) export via
  `lessonweaver export-lesson <candidate> --format eval|guardrail|workflow`.
- Drop `--registry-root /tmp/lw` to use registry discovery. Commands first honor
  `LESSONWEAVER_REGISTRY`, then the nearest `.lessonweaver/registry/` directory,
  then `~/.lessonweaver/registry`.
- See the [glossary](../glossary.md) and [architecture](../architecture.md) for
  the underlying model, and [when not to create a skill](../when-not-to-create-a-skill.md)
  before promoting a candidate.
