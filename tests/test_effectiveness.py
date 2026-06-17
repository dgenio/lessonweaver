"""Tests for closed-loop skill effectiveness."""

from __future__ import annotations

from datetime import datetime, timezone

from lessonweaver.effectiveness import (
    SkillEffectivenessReporter,
    SkillEffectivenessReviewer,
)
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
from lessonweaver.registry import FileSystemRegistry

NOW = datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc)


def _scorecard_skill() -> SkillCard:
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


def _report_skill(skill_id: str, *, status: SkillStatus = SkillStatus.ACTIVE) -> SkillCard:
    return SkillCard(
        id=skill_id,
        name=skill_id,
        description=f"Guidance for {skill_id}.",
        applies_when=["repeated failure pattern"],
        does_not_apply_when=["unrelated work"],
        instructions=["Apply the reviewed lesson."],
        anti_patterns=["Ignoring the reviewed lesson."],
        evidence_trace_ids=["trace-before-1"],
        confidence=0.8,
        risk_level=RiskLevel.LOW,
        scope=Scope.PROJECT,
        version="0.1.0",
        status=status,
    )


def _scorecard_usage(
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


def _report_usage(
    skill_id: str,
    event_id: str,
    *,
    positive: bool | None,
    skill_version: str = "0.1.0",
    outcome: str | None = None,
    notes: str | None = None,
) -> SkillUsageEvent:
    return SkillUsageEvent(
        id=event_id,
        skill_id=skill_id,
        skill_version=skill_version,
        task_context="same failure family",
        loaded_at=NOW,
        outcome=outcome,
        outcome_positive=positive,
        notes=notes,
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
        _scorecard_skill(),
        usage_events=[
            _scorecard_usage(
                "usage-positive",
                "Review this PR for security issues",
                outcome_positive=True,
            )
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
        _scorecard_skill(),
        usage_events=[
            _scorecard_usage(
                "usage-positive",
                "Review this PR for security issues",
                outcome_positive=True,
            )
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
        _scorecard_skill(),
        usage_events=[
            _scorecard_usage(
                "usage-positive",
                "Review this PR for security issues",
                outcome_positive=True,
            )
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
        _scorecard_skill(),
        usage_events=[
            _scorecard_usage(
                "usage-sql",
                "Generate a SQL migration",
                outcome_positive=False,
            )
        ],
        post_activation_traces=[],
    )

    assert report.loaded_relevant == 0
    assert report.loaded_irrelevant == 1
    assert report.false_positive_examples == ["usage-sql"]
    assert report.recommendation == "narrow_scope"


def test_effectiveness_scorecard_serializes_evidence_and_recommendation() -> None:
    report = SkillEffectivenessReviewer().review(
        _scorecard_skill(),
        usage_events=[
            _scorecard_usage(
                "usage-sql",
                "Generate a SQL migration",
                outcome_positive=False,
            )
        ],
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


def test_effectiveness_report_recommends_keep_after_improvement_evidence(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_report_skill("skill-keep"))
    registry.save_usage_event(_report_usage("skill-keep", "u1", positive=True, outcome="resolved"))
    registry.save_usage_event(_report_usage("skill-keep", "u2", positive=True, outcome="resolved"))
    registry.save_usage_event(_report_usage("skill-keep", "u3", positive=None, outcome="unknown"))

    report = SkillEffectivenessReporter().report(registry, now=NOW)[0]

    assert report.signal == "improvement"
    assert report.recommendation == "keep"
    assert report.positive_outcomes == 2
    assert report.negative_outcomes == 0
    assert report.ungraded_outcomes == 1
    assert "observational" in report.causal_uncertainty
    assert report.to_dict()["signal"] == "improvement"


def test_effectiveness_report_recommends_revise_for_repeated_failures(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_report_skill("skill-revise"))
    registry.save_usage_event(
        _report_usage("skill-revise", "u1", positive=False, outcome="repeat_failure")
    )
    registry.save_usage_event(
        _report_usage("skill-revise", "u2", positive=False, outcome="corrected_by_human")
    )

    report = SkillEffectivenessReporter().report(registry, now=NOW)[0]

    assert report.signal == "repeated_failure"
    assert report.recommendation == "revise"
    assert report.evidence_event_ids == ["u1", "u2"]


def test_effectiveness_report_filters_usage_to_current_skill_version(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    skill = _report_skill("skill-versioned")
    skill.version = "0.2.0"
    registry.save_skill(skill)
    registry.save_usage_event(
        _report_usage("skill-versioned", "old-failure", positive=False, skill_version="0.1.0")
    )
    registry.save_usage_event(
        _report_usage(
            "skill-versioned",
            "current-success",
            positive=True,
            skill_version="0.2.0",
            outcome="resolved",
        )
    )

    report = SkillEffectivenessReporter().report(registry, now=NOW)[0]

    assert report.skill_version == "0.2.0"
    assert report.total_usages == 1
    assert report.positive_outcomes == 1
    assert report.negative_outcomes == 0
    assert report.evidence_event_ids == ["current-success"]


def test_effectiveness_report_does_not_call_single_failure_repeated(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_report_skill("skill-single-failure"))
    registry.save_usage_event(
        _report_usage("skill-single-failure", "u1", positive=False, outcome="corrected_by_human")
    )

    report = SkillEffectivenessReporter().report(registry, now=NOW)[0]

    assert report.signal == "insufficient_evidence"
    assert report.recommendation == "review"
    assert report.negative_outcomes == 1


def test_effectiveness_report_recommends_deprecate_for_possible_regression(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_report_skill("skill-regression"))
    registry.save_usage_event(
        _report_usage(
            "skill-regression",
            "u1",
            positive=False,
            outcome="new_regression",
            notes="Reviewer saw a regression after the skill loaded.",
        )
    )

    report = SkillEffectivenessReporter().report(registry, now=NOW)[0]

    assert report.signal == "possible_regression"
    assert report.recommendation == "deprecate_or_revise"


def test_effectiveness_report_distinguishes_staleness_when_never_used(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_report_skill("skill-stale"))

    report = SkillEffectivenessReporter().report(registry, now=NOW)[0]

    assert report.signal == "staleness"
    assert report.recommendation == "review"
    assert report.total_usages == 0
    assert report.last_used_at is None
