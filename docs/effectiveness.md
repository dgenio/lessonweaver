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

- `improvement` — positive graded usage evidence outweighs failures;
- `repeated_failure` — negative graded outcomes suggest the lesson still misses
  the failure pattern;
- `possible_regression` — a negative usage outcome or note explicitly mentions a
  regression after the skill loaded;
- `staleness` — an active skill has no usage evidence;
- `insufficient_evidence` — the available events are not enough to recommend a
  stronger action.

Recommendations are intentionally review-oriented: `keep`, `revise`,
`deprecate_or_revise`, or `review`. Operators can feed these reports into the
existing stale-report and cleanup workflows instead of trusting activated lessons
forever.
