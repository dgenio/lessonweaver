# Closed-loop keystone: failure → reviewed lesson → skill card → loaded back

This is the **flagship "sum > parts" demo**: a coding-agent failure becomes a
reviewed skill card, and that card is loaded **back into an agent's context** —
so the next run starts already knowing not to repeat the mistake. It is the
output side of lessonweaver's closed loop.

It satisfies the closed-loop keystone tracking issue
([#92](https://github.com/dgenio/lessonweaver/issues/92)).

Everything here is fully synthetic. No real repositories, usernames, tokens, or
PII. No model is called at any step.

## Contents

| File | What it is |
| --- | --- |
| `traces/agent_merged_without_tests.json` | A coding agent merges a dependency-bump PR from its title alone; a human reverts and corrects it. **1 candidate.** |
| `example_registry/skills/skill-run-tests-before-merge.json` | The reviewed **skill card** (an `active` `SkillCard`) — the same JSON shape `export-skill --format json` emits. Its content is curated review output, not the raw text `approve` generates from the candidate. This JSON is the shared interchange format contextweaver ingests. |
| `example.py` | Loads the skill card back into agent context (the closed loop). Runs standalone; soft-imports contextweaver. |

## The full loop

These commands write to a throwaway registry under `/tmp/lw-closed-loop`, so they
never touch your home directory. Run them from the repository root.

```bash
# 1. Detect the candidate from the failure trace
lessonweaver detect examples/closed_loop_contextweaver/traces/agent_merged_without_tests.json \
  --save --registry-root /tmp/lw-closed-loop

# 2. Generate multiple-choice review questions for the human reviewer
lessonweaver interview trace-closed-loop-merge-without-tests-001-human-correction \
  --registry-root /tmp/lw-closed-loop

# 3. Record a review answer (the human review gate). --free-text is saved as a
#    reviewer note on the candidate; it does not edit the exported skill's instructions.
lessonweaver answer trace-closed-loop-merge-without-tests-001-human-correction decision approve \
  --free-text "Run the full test suite and confirm it passes before merging any PR." \
  --registry-root /tmp/lw-closed-loop

# 4. Approve the candidate into an operational lesson and a skill
lessonweaver approve trace-closed-loop-merge-without-tests-001-human-correction \
  --approved-by reviewer --registry-root /tmp/lw-closed-loop

# 5. Export the reviewed skill as a skill card (the interchange artifact)
lessonweaver export-skill skill-trace-closed-loop-merge-without-tests-001-human-correction \
  --format json --registry-root /tmp/lw-closed-loop
```

Step 5 emits the same skill-card JSON shape as
`example_registry/skills/skill-run-tests-before-merge.json`, the bundled,
already-reviewed copy this example loads.

## Closing the loop

```bash
python examples/closed_loop_contextweaver/example.py
```

`example.py` loads the reviewed skill card into a context snippet for the next
task. The lessonweaver portion always runs. If contextweaver is installed, the
same skill card is what its skill-card loader ingests to inject the guidance into
an agent's context before its next run; see contextweaver's
`docs/interop_skill_cards.md` for that side.

## The skill-card interchange format

lessonweaver's `export-skill --format json` is the **producer**; contextweaver's
skill-card loader is the **consumer**. The contract is the `SkillCard` JSON shape
shown in `example_registry/skills/skill-run-tests-before-merge.json` (`id`,
`name`, `description`, `applies_when`, `does_not_apply_when`, `instructions`,
`anti_patterns`, plus governance metadata). Unknown fields are ignored, so the
format can grow without breaking either side.

## What this demonstrates

- **The loop closes.** A reviewed lesson exported as a skill card is loaded back
  into the context an agent sees on its next run.
- **Human review is required.** The candidate becomes a skill only after the
  review answer in step 3 and the approval in step 4.
- **No hard dependency in either direction.** lessonweaver exports a plain JSON
  skill card; contextweaver ingestion is optional and the example runs without it.

## What this is not

- It does not call the GitHub API or run a real coding agent.
- It does not claim a guaranteed behavior improvement; the loaded card is
  reviewed guidance, not proof.
- The trace is an illustrative fixture, not captured production data.
