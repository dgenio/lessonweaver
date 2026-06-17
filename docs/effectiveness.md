# Closed-loop effectiveness

lessonweaver can aggregate runtime usage events into conservative effectiveness
reports. These reports do not prove causality; they summarize observed signals
so maintainers know which reviewed skills deserve another governance pass.

Use `SkillEffectivenessReporter` with a registry:

```python
from lessonweaver import FileSystemRegistry, SkillEffectivenessReporter

registry = FileSystemRegistry()
reports = SkillEffectivenessReporter().report(registry)
for report in reports:
    print(report.to_dict())
```

Reports distinguish:

- `improvement` - positive graded usage evidence outweighs failures;
- `repeated_failure` - negative graded outcomes suggest the lesson still misses
  the failure pattern;
- `possible_regression` - a negative usage outcome or note explicitly mentions a
  regression after the skill loaded;
- `staleness` - an active skill has no usage evidence;
- `insufficient_evidence` - the available events are not enough to recommend a
  stronger action.

Recommendations are intentionally review-oriented: `keep`, `revise`,
`deprecate_or_revise`, or `review`. Operators can feed these reports into the
existing stale-report and cleanup workflows instead of trusting activated lessons
forever.

For a single reviewed skill, use `SkillEffectivenessReviewer` to compare usage
logs and later traces:

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
