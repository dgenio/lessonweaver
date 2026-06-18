# Outcome labels

Outcome labels attach human, guardrail, eval, error, or business-outcome
evidence to a trace before lesson detection. They help deployed-agent teams
filter and group candidate lessons by observed failure mode, but they are not
automatic truth: a label is evidence with a source, confidence, severity,
timestamp, and reviewer notes.

## Shape

Each `TraceBundle` can carry `outcome_labels`:

```json
{
  "trace_id": "prod-agent-run-42",
  "source": "otel-json",
  "task": "Answer a policy question",
  "events": [],
  "outcome": "failure",
  "outcome_labels": [
    {
      "label": "retrieval_miss",
      "severity": "high",
      "confidence": 0.8,
      "source": "manual",
      "timestamp": "2026-05-26T12:00:00+00:00",
      "notes": "Reviewer confirmed the answer used stale policy context.",
      "metadata": { "span_id": "span-123" }
    }
  ],
  "metadata": {}
}
```

Supported labels cover success/failure, human correction, user
dissatisfaction, wrong tool, bad handoff, retrieval miss, stale retrieval,
guardrail violation, unnecessary escalation, hallucinated answer, policy
violation, business metric failure, and rejected/no-lesson outcomes.

## Detection usage

`LessonDetector.detect()` propagates trace outcome labels onto each detected
candidate under `candidate.metadata["outcome_labels"]`. Callers can narrow
detection to specific evidence labels:

```python
from lessonweaver import LessonDetector, OutcomeLabelType

candidates = LessonDetector().detect(
    trace,
    outcome_labels={OutcomeLabelType.RETRIEVAL_MISS},
)
```

For inboxes or reports, group candidates by label:

```python
from lessonweaver import group_candidates_by_outcome_label

by_label = group_candidates_by_outcome_label(candidates)
```

Contradictory labels, such as `success` plus `failure`, remain attached to the
trace so reviewers can audit the evidence instead of silently treating one label
as authoritative.
