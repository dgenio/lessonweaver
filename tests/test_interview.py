from lessonweaver.interview import LessonInterviewer, apply_review_answer
from lessonweaver.models import LessonCandidate, LessonStatus, RecommendedActionType, ReviewOption, RiskLevel, Scope


def test_generate_mcq_review_questions() -> None:
    candidate = LessonCandidate(
        id="c1",
        summary="Candidate lesson based on observed correction...",
        evidence_trace_ids=["trace-1"],
        evidence_event_ids=["event-1"],
        observed_problem="Agent missed key step.",
        proposed_lesson="Check diff first.",
        confidence=0.7,
        recommended_action_type=RecommendedActionType.SKILL,
        risk_level=RiskLevel.MEDIUM,
        scope=Scope.PROJECT,
    )
    questions = LessonInterviewer().build_questions(candidate)
    assert len(questions) >= 6
    assert all(3 <= len(question.options) <= 10 for question in questions)
    assert all(question.allow_free_text for question in questions)


def test_recommended_option_reflects_candidate_scope() -> None:
    candidate = LessonCandidate(
        id="c2",
        summary="User-scoped candidate.",
        evidence_trace_ids=["trace-1"],
        evidence_event_ids=["event-1"],
        observed_problem="Problem.",
        proposed_lesson="Lesson.",
        confidence=0.5,
        recommended_action_type=RecommendedActionType.WORKFLOW_CHANGE,
        risk_level=RiskLevel.LOW,
        scope=Scope.USER,
    )
    questions = LessonInterviewer().build_questions(candidate)
    scope_q = next(q for q in questions if q.id == "scope")
    action_q = next(q for q in questions if q.id == "action_type")
    assert scope_q.recommended_option_id == "user"
    assert action_q.recommended_option_id == "workflow_change"


def test_apply_review_answer_updates_scope() -> None:
    candidate = LessonCandidate(
        id="c3",
        summary="Test.",
        evidence_trace_ids=[],
        evidence_event_ids=[],
        observed_problem="P.",
        proposed_lesson="L.",
        confidence=0.5,
        recommended_action_type=RecommendedActionType.SKILL,
        risk_level=RiskLevel.MEDIUM,
        scope=Scope.PROJECT,
    )
    option = ReviewOption("team", "B", "Team repositories", {"scope": "team"})
    result = apply_review_answer(candidate, option)
    assert result.scope is Scope.TEAM


def test_apply_review_answer_updates_status() -> None:
    candidate = LessonCandidate(
        id="c4",
        summary="Test.",
        evidence_trace_ids=[],
        evidence_event_ids=[],
        observed_problem="P.",
        proposed_lesson="L.",
        confidence=0.5,
        recommended_action_type=RecommendedActionType.SKILL,
        risk_level=RiskLevel.LOW,
        scope=Scope.PROJECT,
    )
    option = ReviewOption("approve", "A", "Approve lesson", {"status": "approved"})
    result = apply_review_answer(candidate, option)
    assert result.status is LessonStatus.APPROVED


def test_apply_review_answer_ignores_unknown_fields() -> None:
    candidate = LessonCandidate(
        id="c5",
        summary="Test.",
        evidence_trace_ids=[],
        evidence_event_ids=[],
        observed_problem="P.",
        proposed_lesson="L.",
        confidence=0.5,
        recommended_action_type=RecommendedActionType.SKILL,
        risk_level=RiskLevel.LOW,
        scope=Scope.PROJECT,
    )
    option = ReviewOption("x", "X", "Bad field", {"nonexistent_field": "value"})
    result = apply_review_answer(candidate, option)
    assert result.scope is Scope.PROJECT  # unchanged
