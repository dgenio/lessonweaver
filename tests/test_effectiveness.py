"""Tests for closed-loop skill effectiveness scorecards."""

from __future__ import annotations

from datetime import datetime, timezone

from lessonweaver.effectiveness import SkillEffectivenessReviewer
from lessonweaver.models import (
    RiskLevel,
    Scope,
    SkillCard,
    SkillStatus,
    SkillUsageEvent,
    TraceBundle,
    TraceEvent,
    TraceEventType,
)

NOW = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)


def _skill() -> SkillCard:
    return SkillCard(
        id="skill-pr-review",
        name="PR Diff First",
        description="Inspect changed files before reviewing pull requests.",
        applies_when=["reviewing pull requests"],
        does_not_apply_when=["non-code writing tasks"],
        instructions=["Inspect the diff before approving a pull request."],
        anti_patterns=["approved a pull request without inspecting the diff"],
        evidence_trace_ids=["trace-original"],
        confidence=0.8,
        risk_level=RiskLevel.LOW,
        scope=Scope.PROJECT,
        version="0.2.0",
        status=SkillStatus.ACTIVE,
    )


def _usage(
    usage_id: str,
    task_context: str,
    *,
    outcome_positive: bool | None = None,
) -> SkillUsageEvent:
    return SkillUsageEvent(
        id=usage_id,
        skill_id="skill-pr-review",
        skill_version="0.2.0",
        task_context=task_context,
        outcome_positive=outcome_positive,
        loaded_at=NOW,
    )


def _trace(trace_id: str, task: str, content: str) -> TraceBundle:
    return TraceBundle(
        trace_id=trace_id,
        source="unit-test",
        task=task,
        events=[
            TraceEvent(
                id="event-1",
                type=TraceEventType.HUMAN_CORRECTION,
                content=content,
            )
        ],
        outcome="corrected_by_human",
    )


def _successful_trace(trace_id: str, task: str, content: str) -> TraceBundle:
    return TraceBundle(
        trace_id=trace_id,
        source="unit-test",
        task=task,
        events=[
            TraceEvent(
                id="event-1",
                type=TraceEventType.FINAL_ANSWER,
                content=content,
            )
        ],
        outcome="success",
    )


def test_effectiveness_scorecard_keeps_skill_with_positive_relevant_usage() -> None:
    report = SkillEffectivenessReviewer().review(
        _skill(),
        usage_events=[
            _usage("usage-positive", "Review this PR for security issues", outcome_positive=True)
        ],
        post_activation_traces=[],
    )

    assert report.loaded_relevant == 1
    assert report.loaded_irrelevant == 0
    assert report.recurrence_trace_ids == []
    assert report.recommendation == "keep"
    assert report.score > 0.5


def test_effectiveness_scorecard_flags_recurring_failure_after_activation() -> None:
    report = SkillEffectivenessReviewer().review(
        _skill(),
        usage_events=[
            _usage("usage-positive", "Review this PR for security issues", outcome_positive=True)
        ],
        post_activation_traces=[
            _trace(
                "trace-repeat",
                "Review pull request",
                "You approved the pull request without inspecting the diff.",
            )
        ],
    )

    assert report.recurrence_trace_ids == ["trace-repeat"]
    assert report.false_negative_examples == ["trace-repeat"]
    assert report.recommendation == "revise"
    assert report.score < 0.5


def test_effectiveness_scorecard_ignores_matching_task_without_failure_evidence() -> None:
    report = SkillEffectivenessReviewer().review(
        _skill(),
        usage_events=[
            _usage("usage-positive", "Review this PR for security issues", outcome_positive=True)
        ],
        post_activation_traces=[
            _successful_trace(
                "trace-healthy",
                "Review pull request",
                "The diff was inspected before the review completed.",
            )
        ],
    )

    assert report.recurrence_trace_ids == []
    assert report.false_negative_examples == []
    assert report.recommendation == "keep"


def test_effectiveness_scorecard_flags_irrelevant_loading_as_over_triggering() -> None:
    report = SkillEffectivenessReviewer().review(
        _skill(),
        usage_events=[_usage("usage-sql", "Generate a SQL migration", outcome_positive=False)],
        post_activation_traces=[],
    )

    assert report.loaded_relevant == 0
    assert report.loaded_irrelevant == 1
    assert report.false_positive_examples == ["usage-sql"]
    assert report.recommendation == "narrow_scope"


def test_effectiveness_scorecard_serializes_evidence_and_recommendation() -> None:
    report = SkillEffectivenessReviewer().review(
        _skill(),
        usage_events=[_usage("usage-sql", "Generate a SQL migration", outcome_positive=False)],
        post_activation_traces=[
            _trace(
                "trace-repeat",
                "Review pull request",
                "The review skipped diff inspection again.",
            )
        ],
    )

    assert report.to_dict() == {
        "skill_id": "skill-pr-review",
        "score": report.score,
        "recommendation": "revise",
        "loaded_relevant": 0,
        "loaded_irrelevant": 1,
        "positive_outcomes": 0,
        "negative_outcomes": 1,
        "recurrence_trace_ids": ["trace-repeat"],
        "false_positive_examples": ["usage-sql"],
        "false_negative_examples": ["trace-repeat"],
    }
