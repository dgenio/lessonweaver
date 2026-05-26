from datetime import datetime, timezone

import pytest

from lessonweaver.governance import can_promote_skill, promote_skill
from lessonweaver.models import (
    ExportArtifact,
    ExportFormat,
    LessonCandidate,
    LessonStatus,
    OperationalLesson,
    RecommendedActionType,
    ReviewAnswer,
    ReviewOption,
    ReviewQuestion,
    RiskLevel,
    Scope,
    SkillCard,
    SkillStatus,
)
from lessonweaver.traces import load_trace_bundle

NOW = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)


def _candidate() -> LessonCandidate:
    return LessonCandidate(
        id="c1",
        summary="Check policy version before answering.",
        evidence_trace_ids=["trace-1"],
        evidence_event_ids=["event-1"],
        observed_problem="The agent answered from stale policy context.",
        proposed_lesson="Verify the active policy version before answering policy questions.",
        confidence=0.72,
        recommended_action_type=RecommendedActionType.SKILL,
        risk_level=RiskLevel.MEDIUM,
        scope=Scope.PROJECT,
        created_at=NOW,
        updated_at=NOW,
        metadata={"source": "test"},
    )


def _skill(
    status: SkillStatus = SkillStatus.DRAFT, risk_level: RiskLevel = RiskLevel.LOW
) -> SkillCard:
    return SkillCard(
        id="skill-1",
        name="Policy Version Check",
        description="Check policy version before answering user policy questions.",
        applies_when=["Answering policy questions"],
        does_not_apply_when=["No policy content is involved"],
        instructions=["Check the active policy version before answering."],
        anti_patterns=["Answering from stale policy memory"],
        evidence_trace_ids=["trace-1"],
        confidence=0.8,
        risk_level=risk_level,
        scope=Scope.PROJECT,
        version="0.2.0",
        status=status,
        approved_by="reviewer",
        created_at=NOW,
        updated_at=NOW,
    )


def test_load_trace_bundle() -> None:
    trace = load_trace_bundle("examples/traces/github_pr_review_failure.json")
    assert trace.trace_id == "trace-gh-pr-review-001"
    assert trace.events[2].type.value == "human_correction"


def test_review_option_and_question_round_trip() -> None:
    question = ReviewQuestion(
        id="scope",
        question="Where should this apply?",
        options=[ReviewOption("project", "A", "Project only", {"scope": "project"})],
        recommended_option_id="project",
        rationale="Evidence is project-local.",
    )
    assert ReviewQuestion.from_dict(question.to_dict()).to_dict() == question.to_dict()


def test_review_answer_round_trip() -> None:
    answer = ReviewAnswer("scope", "project", "Use for this repository.")
    assert ReviewAnswer.from_dict(answer.to_dict()).to_dict() == answer.to_dict()


def test_lesson_candidate_round_trip_with_metadata() -> None:
    candidate = _candidate()
    assert LessonCandidate.from_dict(candidate.to_dict()).to_dict() == candidate.to_dict()


def test_lesson_candidate_from_dict_normalizes_naive_datetimes_to_utc() -> None:
    data = _candidate().to_dict()
    data["created_at"] = "2026-05-26T12:00:00"
    candidate = LessonCandidate.from_dict(data)
    assert candidate.created_at.tzinfo is timezone.utc
    assert candidate.to_dict()["created_at"] == "2026-05-26T12:00:00+00:00"


def test_operational_lesson_round_trip() -> None:
    lesson = OperationalLesson(
        lesson_id="lesson-1",
        candidate_id="c1",
        title="Policy Version Check",
        summary="Check policy version before answering.",
        instructions=["Verify policy version."],
        applies_when=["Answering policy questions"],
        does_not_apply_when=["No policy content"],
        anti_patterns=["Answering from stale memory"],
        risk_level=RiskLevel.HIGH,
        scope=Scope.PROJECT,
        recommended_action_type=RecommendedActionType.SKILL,
        evidence_trace_ids=["trace-1"],
        evidence_event_ids=["event-1"],
        confidence=0.82,
        review_answers=[ReviewAnswer("decision", "approve")],
        status=LessonStatus.APPROVED,
        created_at=NOW,
        approved_at=NOW,
    )
    assert OperationalLesson.from_dict(lesson.to_dict()).to_dict() == lesson.to_dict()


def test_export_artifact_round_trip() -> None:
    artifact = ExportArtifact(
        artifact_id="artifact-1",
        skill_id="skill-1",
        format=ExportFormat.MARKDOWN,
        content="# Skill",
        created_at=NOW,
    )
    assert ExportArtifact.from_dict(artifact.to_dict()).to_dict() == artifact.to_dict()


def test_skillcard_round_trip_includes_sensitivity() -> None:
    skill = _skill()
    data = SkillCard.from_dict(skill.to_dict()).to_dict()
    assert data["sensitivity"] == "internal"
    assert data == skill.to_dict()


def test_skill_status_experimental_exists() -> None:
    assert SkillStatus.EXPERIMENTAL.value == "experimental"


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (SkillStatus.DRAFT, SkillStatus.APPROVED),
        (SkillStatus.APPROVED, SkillStatus.EXPERIMENTAL),
        (SkillStatus.APPROVED, SkillStatus.REJECTED),
        (SkillStatus.EXPERIMENTAL, SkillStatus.ACTIVE),
        (SkillStatus.EXPERIMENTAL, SkillStatus.DEPRECATED),
        (SkillStatus.ACTIVE, SkillStatus.DEPRECATED),
    ],
)
def test_valid_skill_transitions(source: SkillStatus, target: SkillStatus) -> None:
    promoted = promote_skill(_skill(status=source), target)
    assert promoted.status is target


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (SkillStatus.DRAFT, SkillStatus.ACTIVE),
        (SkillStatus.DRAFT, SkillStatus.EXPERIMENTAL),
        (SkillStatus.APPROVED, SkillStatus.ACTIVE),
        (SkillStatus.ACTIVE, SkillStatus.APPROVED),
        (SkillStatus.REJECTED, SkillStatus.APPROVED),
        (SkillStatus.DEPRECATED, SkillStatus.ACTIVE),
    ],
)
def test_invalid_skill_transitions(source: SkillStatus, target: SkillStatus) -> None:
    skill = _skill(status=source)
    assert not can_promote_skill(skill, target)
    with pytest.raises(ValueError, match="cannot promote skill"):
        promote_skill(skill, target)


def test_promote_to_active_enforces_lint_blockers() -> None:
    skill = _skill(status=SkillStatus.EXPERIMENTAL, risk_level=RiskLevel.HIGH)
    skill.approved_by = None
    with pytest.raises(ValueError, match="LW006"):
        promote_skill(skill, SkillStatus.ACTIVE)
