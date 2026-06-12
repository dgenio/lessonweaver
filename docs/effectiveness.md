# Effectiveness Review

Reviewed skills should keep earning their place in agent context. After a skill
is exported or loaded, compare usage logs and later traces to decide whether the
skill is helping, over-triggering, or failing to prevent the original pattern.

`SkillEffectivenessReviewer` produces a deterministic scorecard for one skill:

```python
from lessonweaver import SkillEffectivenessReviewer

scorecard = SkillEffectivenessReviewer().review(
    skill,
    usage_events=registry.list_skill_usage(skill.id),
    post_activation_traces=later_traces,
)

print(scorecard.to_dict())
```

The scorecard reports:

- relevant and irrelevant loads;
- positive and negative recorded outcomes;
- post-activation traces that look like recurrence of the skill's failure
  pattern;
- false-positive examples where the skill loaded for unrelated tasks;
- false-negative examples where the original pattern recurred;
- a recommendation: `keep`, `revise`, `narrow_scope`, or `review`.

This report is advisory. Promotion, deprecation, and cleanup still go through
the governed lifecycle and human review paths.
