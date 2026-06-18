from datetime import datetime, timezone

from lessonweaver.detection import LessonDetector, group_candidates_by_outcome_label
from lessonweaver.models import (
    OutcomeLabel,
    OutcomeLabelType,
    OutcomeSeverity,
    TraceBundle,
    TraceEvent,
    TraceEventType,
)

NOW = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)


def _label(label: OutcomeLabelType, *, source: str = "manual") -> OutcomeLabel:
    return OutcomeLabel(
        label=label,
        severity=OutcomeSeverity.HIGH,
        confidence=0.8,
        source=source,
        timestamp=NOW,
        notes="reviewed by operator",
    )


def _trace(*labels: OutcomeLabel) -> TraceBundle:
    return TraceBundle(
        trace_id="trace-labels-1",
        source="unit-test",
        task="Review this pull request",
        events=[
            TraceEvent(
                id="eval-1",
                type=TraceEventType.EVALUATION_RESULT,
                status="failed",
                content="review missed a changed file",
            )
        ],
        outcome="failure",
        outcome_labels=list(labels),
    )


def test_outcome_label_serializes_with_evidence_metadata() -> None:
    label = _label(OutcomeLabelType.HALLUCINATED_ANSWER)

    assert OutcomeLabel.from_dict(label.to_dict()) == label
    assert label.to_dict() == {
        "label": "hallucinated_answer",
        "severity": "high",
        "confidence": 0.8,
        "source": "manual",
        "timestamp": "2026-05-26T12:00:00+00:00",
        "notes": "reviewed by operator",
        "metadata": {},
    }


def test_trace_bundle_round_trips_manual_and_imported_outcome_labels() -> None:
    manual = _label(OutcomeLabelType.RETRIEVAL_MISS, source="manual")
    imported_payload = {
        "label": "guardrail_violation",
        "severity": "medium",
        "confidence": 0.6,
        "source": "guardrail_span",
        "timestamp": "2026-05-26T12:01:00Z",
        "notes": "blocked unsafe answer",
        "metadata": {"span_id": "span-1"},
    }

    trace = _trace(manual)
    payload = trace.to_dict()
    payload["outcome_labels"].append(imported_payload)
    restored = TraceBundle.from_dict(payload)

    assert [label.label for label in restored.outcome_labels] == [
        OutcomeLabelType.RETRIEVAL_MISS,
        OutcomeLabelType.GUARDRAIL_VIOLATION,
    ]
    assert restored.outcome_labels[1].source == "guardrail_span"
    assert restored.to_dict()["outcome_labels"][1]["timestamp"] == "2026-05-26T12:01:00+00:00"


def test_contradictory_outcome_labels_are_detected() -> None:
    trace = _trace(_label(OutcomeLabelType.SUCCESS), _label(OutcomeLabelType.FAILURE))

    contradictions = trace.contradictory_outcome_labels()

    assert contradictions == [("success", "failure")]


def test_detection_filters_and_propagates_outcome_labels() -> None:
    trace = _trace(
        _label(OutcomeLabelType.RETRIEVAL_MISS),
        _label(OutcomeLabelType.USER_DISSATISFACTION),
    )

    detector = LessonDetector()
    all_candidates = detector.detect(trace)
    filtered = detector.detect(trace, outcome_labels={OutcomeLabelType.RETRIEVAL_MISS})
    missing = detector.detect(trace, outcome_labels={OutcomeLabelType.POLICY_VIOLATION})

    assert all_candidates
    assert filtered
    assert missing == []
    assert filtered[0].metadata["outcome_labels"][0]["label"] == "retrieval_miss"


def test_candidates_group_by_outcome_label() -> None:
    trace = _trace(
        _label(OutcomeLabelType.WRONG_TOOL),
        _label(OutcomeLabelType.HUMAN_CORRECTION),
    )
    candidates = LessonDetector().detect(trace)

    grouped = group_candidates_by_outcome_label(candidates)

    assert set(grouped) == {"wrong_tool", "human_correction"}
    assert grouped["wrong_tool"] == candidates


def test_candidates_group_by_outcome_label_deduplicates_candidate_per_label() -> None:
    trace = _trace(
        _label(OutcomeLabelType.RETRIEVAL_MISS, source="manual"),
        _label(OutcomeLabelType.RETRIEVAL_MISS, source="eval"),
    )
    candidates = LessonDetector().detect(trace)

    grouped = group_candidates_by_outcome_label(candidates)

    assert grouped["retrieval_miss"] == candidates
