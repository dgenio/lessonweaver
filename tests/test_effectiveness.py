from __future__ import annotations

from datetime import datetime, timezone

from lessonweaver.effectiveness import SkillEffectivenessReporter
from lessonweaver.models import RiskLevel, Scope, SkillCard, SkillStatus, SkillUsageEvent
from lessonweaver.registry import FileSystemRegistry

NOW = datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc)


def _skill(skill_id: str, *, status: SkillStatus = SkillStatus.ACTIVE) -> SkillCard:
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


def _usage(
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


def test_effectiveness_report_recommends_keep_after_improvement_evidence(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill("skill-keep"))
    registry.save_usage_event(_usage("skill-keep", "u1", positive=True, outcome="resolved"))
    registry.save_usage_event(_usage("skill-keep", "u2", positive=True, outcome="resolved"))
    registry.save_usage_event(_usage("skill-keep", "u3", positive=None, outcome="unknown"))

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
    registry.save_skill(_skill("skill-revise"))
    registry.save_usage_event(
        _usage("skill-revise", "u1", positive=False, outcome="repeat_failure")
    )
    registry.save_usage_event(
        _usage("skill-revise", "u2", positive=False, outcome="corrected_by_human")
    )

    report = SkillEffectivenessReporter().report(registry, now=NOW)[0]

    assert report.signal == "repeated_failure"
    assert report.recommendation == "revise"
    assert report.evidence_event_ids == ["u1", "u2"]


def test_effectiveness_report_filters_usage_to_current_skill_version(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    skill = _skill("skill-versioned")
    skill.version = "0.2.0"
    registry.save_skill(skill)
    registry.save_usage_event(
        _usage("skill-versioned", "old-failure", positive=False, skill_version="0.1.0")
    )
    registry.save_usage_event(
        _usage(
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
    registry.save_skill(_skill("skill-single-failure"))
    registry.save_usage_event(
        _usage("skill-single-failure", "u1", positive=False, outcome="corrected_by_human")
    )

    report = SkillEffectivenessReporter().report(registry, now=NOW)[0]

    assert report.signal == "insufficient_evidence"
    assert report.recommendation == "review"
    assert report.negative_outcomes == 1


def test_effectiveness_report_recommends_deprecate_for_possible_regression(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill("skill-regression"))
    registry.save_usage_event(
        _usage(
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
    registry.save_skill(_skill("skill-stale"))

    report = SkillEffectivenessReporter().report(registry, now=NOW)[0]

    assert report.signal == "staleness"
    assert report.recommendation == "review"
    assert report.total_usages == 0
    assert report.last_used_at is None
