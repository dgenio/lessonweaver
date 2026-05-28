# End-to-end example: coding-agent PR review

This is the main worked example for lessonweaver. It follows a coding agent that
"reviews" a pull request without inspecting the changed files, gets corrected by
a human, and shows how that correction becomes a reviewed, reusable instruction.

It satisfies two tracking issues: the multi-trace example with a validation
suite ([#25](https://github.com/dgenio/lessonweaver/issues/25)) and the polished
end-to-end demo ([#66](https://github.com/dgenio/lessonweaver/issues/66)).

Everything here is fully synthetic. No real repositories, usernames, tokens, or
PII. No model is called at any step.

## Contents

| File | What it is |
| --- | --- |
| `traces/pr_review_missing_test.json` | Agent approves a PR without checking tests; human corrects. **1 candidate.** |
| `traces/pr_review_correct.json` | Agent inspects the diff and reviews a well-tested PR. **0 candidates** (the boring case). |
| `traces/pr_review_security_miss.json` | Agent misses an SQL-injection risk; a failed eval and a human correction fire. **2 candidates.** |
| `candidate.json` | The `LessonCandidate` detected from `pr_review_missing_test.json` (`to_dict()`). |
| `skill.json` | The reviewed, **approved** `SkillCard` derived from the PR-review lessons. |
| `validation_suite.json` | Retrieval-correctness suite: 2 positive + 2 negative examples. |
| `exported_instruction.md` | The Copilot and AGENTS.md fragments exported from `skill.json`. |

## The full loop

These commands write to a throwaway registry under `/tmp/lw-pr-review`, so they
never touch your home directory. Run them from the repository root.

```bash
# 1. Detect candidates from each trace
lessonweaver detect examples/coding_agent_pr_review/traces/pr_review_missing_test.json \
  --save --registry-root /tmp/lw-pr-review

# The well-tested PR produces no candidate — detection is conservative.
lessonweaver detect examples/coding_agent_pr_review/traces/pr_review_correct.json

# 2. Generate multiple-choice review questions for the human reviewer
lessonweaver interview trace-pr-review-missing-test-001-human-correction \
  --registry-root /tmp/lw-pr-review

# 3. Record a review answer (the human review gate)
lessonweaver answer trace-pr-review-missing-test-001-human-correction decision approve \
  --free-text "Inspect changed files and verify test coverage before approving." \
  --registry-root /tmp/lw-pr-review

# 4. Approve the candidate into an operational lesson and a skill
lessonweaver approve trace-pr-review-missing-test-001-human-correction \
  --approved-by reviewer --registry-root /tmp/lw-pr-review

# 5. Validate retrieval correctness against the bundled suite
lessonweaver validate-skill examples/coding_agent_pr_review/validation_suite.json \
  --skills-dir examples/coding_agent_pr_review

# 6. Export the reviewed skill for an instruction surface
lessonweaver export-skill examples/coding_agent_pr_review/skill.json \
  --format copilot --redact
lessonweaver export-skill examples/coding_agent_pr_review/skill.json \
  --format agents-md --redact
```

Step 5 reads `skill.json` directly (already approved) so the suite runs without
the throwaway registry; it prints precision/recall and exits `0` when every
example passes. `exported_instruction.md` shows the exported text from step 6.

## What this demonstrates

- **Conservative detection.** The well-tested PR yields zero candidates; only
  the corrected runs produce lessons.
- **Human review is required.** A candidate becomes a skill only after the
  review answer in step 3 and the approval in step 4.
- **Retrieval is testable.** `validation_suite.json` asserts the skill loads for
  PR-review tasks and *not* for documentation edits or issue triage — so the
  exported guidance does not leak into unrelated contexts.

## What this is not

- It does not call the GitHub API or run a real coding agent.
- It does not claim a guaranteed behavior improvement; the exported fragment is
  reviewed guidance, not proof.
- The traces are illustrative fixtures, not captured production data.
