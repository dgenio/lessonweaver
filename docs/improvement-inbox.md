# Agent improvement inbox

The agent improvement inbox turns telemetry-derived `LessonCandidate` objects
into a review queue for agent owners. It groups recurring failure patterns,
surfaces evidence, recommends an artifact type, and records reviewer actions
back into the registry.

```python
from lessonweaver import AgentImprovementInboxBuilder, FileSystemRegistry

registry = FileSystemRegistry("/tmp/lw-registry")
candidates = registry.list_candidates()

inbox = AgentImprovementInboxBuilder(min_frequency=2).build(candidates)
print(inbox.to_markdown())
dashboard_payload = inbox.to_dict()
```

Each inbox item includes:

- title and candidate ids;
- affected agents and versions from candidate metadata;
- evidence trace ids and representative examples;
- frequency and trend;
- outcome labels and failure mode;
- recommended artifact type, risk level, and suggested scope;
- recommendation rationale, eval plan, rollout plan, and available actions.

## Review workflow

Use the Markdown output for human review and the JSON output for dashboards or
automation. Agent owners should start with high-risk, high-frequency items,
inspect the evidence traces, and choose one of the recorded actions:

- `approve` marks the candidate approved for the normal export path.
- `reject` marks the candidate rejected and preserves the reviewer note.
- `defer` keeps the candidate in review while recording why it is not ready.
- `create_issue` records that issue creation is the next action while keeping
  the candidate under review.

```python
from lessonweaver import record_improvement_inbox_action

record_improvement_inbox_action(
    registry,
    ["candidate-1", "candidate-2"],
    "defer",
    reviewer="agent-owner@example.com",
    note="Wait for another rollout sample before approving.",
)
```

The action record is stored under `candidate.metadata["improvement_inbox"]` so
it is visible in registry JSON and can be consumed by a future UI.
