from datetime import datetime, timezone

import pytest

from lessonweaver.governance import can_promote_skill, promote_skill
from lessonweaver.models import (
    ExportArtifact,
    ExportFormat,
    LessonCandidate,
    LessonStatus,
    LoadingPolicy,
    OperationalLesson,
    RecommendedActionType,
    ReviewAnswer,
    ReviewOption,
    ReviewQuestion,
    ReviewSession,
    RiskLevel,
    Scope,
    SkillCard,
    SkillStatus,
    SkillUsageEvent,
    StaleSkillReport,
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


def test_review_question_from_dict_rejects_invalid_bool() -> None:
    question = ReviewQuestion(
        id="scope",
        question="Where should this apply?",
        options=[ReviewOption("project", "A", "Project only", {"scope": "project"})],
        recommended_option_id="project",
        rationale="Evidence is project-local.",
    ).to_dict()
    question["allow_free_text"] = "nope"

    with pytest.raises(ValueError, match="allow_free_text"):
        ReviewQuestion.from_dict(question)


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


def test_operational_lesson_from_dict_rejects_confidence_outside_unit_interval() -> None:
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
    ).to_dict()
    lesson["confidence"] = 1.1

    with pytest.raises(ValueError, match="confidence"):
        OperationalLesson.from_dict(lesson)


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


def test_lesson_candidate_evidence_strength_is_distinct_from_confidence() -> None:
    candidate = _candidate()
    candidate.evidence_strength = 0.4
    candidate.evidence_summary = "Indirect signal only."
    assert candidate.confidence == 0.72
    assert candidate.evidence_strength == 0.4
    assert candidate.evidence_strength != candidate.confidence
    data = candidate.to_dict()
    assert data["evidence_strength"] == 0.4
    assert data["evidence_summary"] == "Indirect signal only."
    assert LessonCandidate.from_dict(data).to_dict() == data


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("confidence", -0.1),
        ("confidence", 1.1),
        ("evidence_strength", -0.1),
        ("evidence_strength", 1.1),
    ],
)
def test_lesson_candidate_from_dict_rejects_unit_interval_fields(field: str, value: float) -> None:
    data = _candidate().to_dict()
    data[field] = value
    with pytest.raises(ValueError, match=field):
        LessonCandidate.from_dict(data)


@pytest.mark.parametrize("value", [0.0, 1.0])
def test_lesson_candidate_from_dict_accepts_unit_interval_boundaries(value: float) -> None:
    data = _candidate().to_dict()
    data["confidence"] = value
    data["evidence_strength"] = value
    candidate = LessonCandidate.from_dict(data)
    assert candidate.confidence == value
    assert candidate.evidence_strength == value


def test_lesson_candidate_from_dict_defaults_missing_evidence_fields() -> None:
    data = _candidate().to_dict()
    del data["evidence_strength"]
    del data["evidence_summary"]
    candidate = LessonCandidate.from_dict(data)
    assert candidate.evidence_strength == 0.0
    assert candidate.evidence_summary == ""


def test_skill_usage_event_round_trip() -> None:
    event = SkillUsageEvent(
        id="usage-1",
        skill_id="skill-1",
        skill_version="0.2.0",
        task_context="Reviewing a pull request",
        loaded_at=NOW,
        outcome="resolved",
        outcome_positive=True,
        notes="Helped catch a missing test.",
    )
    assert SkillUsageEvent.from_dict(event.to_dict()).to_dict() == event.to_dict()


def test_skill_usage_event_outcome_defaults_to_none() -> None:
    event = SkillUsageEvent(
        id="usage-2",
        skill_id="skill-1",
        skill_version="0.2.0",
        task_context="Reviewing a pull request",
        loaded_at=NOW,
    )
    data = event.to_dict()
    assert data["outcome"] is None
    assert data["outcome_positive"] is None
    assert SkillUsageEvent.from_dict(data).outcome_positive is None


def test_skill_usage_event_from_dict_parses_false_string_as_false() -> None:
    data = SkillUsageEvent(
        id="usage-3",
        skill_id="skill-1",
        skill_version="0.2.0",
        task_context="Reviewing a pull request",
        loaded_at=NOW,
        outcome_positive=False,
    ).to_dict()
    data["outcome_positive"] = "false"

    assert SkillUsageEvent.from_dict(data).outcome_positive is False


def test_skill_usage_event_from_dict_rejects_invalid_bool() -> None:
    data = SkillUsageEvent(
        id="usage-4",
        skill_id="skill-1",
        skill_version="0.2.0",
        task_context="Reviewing a pull request",
        loaded_at=NOW,
    ).to_dict()
    data["outcome_positive"] = "definitely"

    with pytest.raises(ValueError, match="outcome_positive"):
        SkillUsageEvent.from_dict(data)


def test_skillcard_from_dict_rejects_confidence_outside_unit_interval() -> None:
    data = _skill().to_dict()
    data["confidence"] = 7.3

    with pytest.raises(ValueError, match="confidence"):
        SkillCard.from_dict(data)


def test_review_session_from_dict_rejects_negative_current_question_index() -> None:
    data = ReviewSession(
        session_id="session-1",
        candidate_id="c1",
        started_at=NOW.isoformat(),
        updated_at=NOW.isoformat(),
    ).to_dict()
    data["current_question_index"] = -1

    with pytest.raises(ValueError, match="current_question_index"):
        ReviewSession.from_dict(data)


def test_review_session_from_dict_rejects_invalid_bool() -> None:
    data = ReviewSession(
        session_id="session-1",
        candidate_id="c1",
        started_at=NOW.isoformat(),
        updated_at=NOW.isoformat(),
    ).to_dict()
    data["completed"] = "nope"

    with pytest.raises(ValueError, match="completed"):
        ReviewSession.from_dict(data)


def test_loading_policy_round_trip() -> None:
    policy = LoadingPolicy(
        max_skills=3,
        max_token_budget=1500,
        allowed_scopes=[Scope.PROJECT, Scope.TEAM],
        max_risk_level=RiskLevel.HIGH,
        excluded_skill_ids=["skill-x"],
        require_approved_status=False,
    )
    assert LoadingPolicy.from_dict(policy.to_dict()).to_dict() == policy.to_dict()


@pytest.mark.parametrize("field", ["max_skills", "max_token_budget"])
def test_loading_policy_from_dict_rejects_negative_limits(field: str) -> None:
    data = LoadingPolicy().to_dict()
    data[field] = -1

    with pytest.raises(ValueError, match=field):
        LoadingPolicy.from_dict(data)


def test_loading_policy_from_dict_rejects_invalid_bool() -> None:
    data = LoadingPolicy().to_dict()
    data["require_approved_status"] = "nope"

    with pytest.raises(ValueError, match="require_approved_status"):
        LoadingPolicy.from_dict(data)


def test_loading_policy_default_returns_all_approved_skills() -> None:
    skills = [
        _skill_named("a", status=SkillStatus.APPROVED),
        _skill_named("b", status=SkillStatus.ACTIVE),
    ]
    assert LoadingPolicy().filter(skills) == skills


def test_loading_policy_excludes_skills_above_risk_ceiling() -> None:
    low = _skill_named("low", risk_level=RiskLevel.LOW)
    high = _skill_named("high", risk_level=RiskLevel.HIGH)
    policy = LoadingPolicy(max_risk_level=RiskLevel.MEDIUM)
    assert policy.filter([low, high]) == [low]


def test_loading_policy_excludes_skills_outside_allowed_scopes() -> None:
    project = _skill_named("project", scope=Scope.PROJECT)
    org = _skill_named("org", scope=Scope.ORGANIZATION)
    policy = LoadingPolicy(allowed_scopes=[Scope.PROJECT])
    assert policy.filter([project, org]) == [project]


def test_loading_policy_excludes_denylisted_skill_ids() -> None:
    keep = _skill_named("keep")
    drop = _skill_named("drop")
    policy = LoadingPolicy(excluded_skill_ids=["drop"])
    assert policy.filter([keep, drop]) == [keep]


def test_loading_policy_excludes_non_approved_when_required() -> None:
    draft = _skill_named("draft", status=SkillStatus.DRAFT)
    active = _skill_named("active", status=SkillStatus.ACTIVE)
    policy = LoadingPolicy(require_approved_status=True)
    assert policy.filter([draft, active]) == [active]


def test_loading_policy_allows_non_approved_when_not_required() -> None:
    draft = _skill_named("draft", status=SkillStatus.DRAFT)
    policy = LoadingPolicy(require_approved_status=False)
    assert policy.filter([draft]) == [draft]


def test_stale_skill_report_round_trip() -> None:
    report = StaleSkillReport(
        skill_id="skill-1",
        reason="expired",
        recommendation="revalidate",
        last_used_at=NOW,
        expires_at=NOW,
    )
    assert StaleSkillReport.from_dict(report.to_dict()).to_dict() == report.to_dict()


def _skill_named(
    skill_id: str,
    *,
    status: SkillStatus = SkillStatus.APPROVED,
    risk_level: RiskLevel = RiskLevel.LOW,
    scope: Scope = Scope.PROJECT,
) -> SkillCard:
    skill = _skill(status=status, risk_level=risk_level)
    skill.id = skill_id
    skill.scope = scope
    return skill
