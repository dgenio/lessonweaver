import pytest

from lessonweaver.interview import LessonInterviewer, apply_review_answer
from lessonweaver.models import (
    LessonCandidate,
    LessonStatus,
    RecommendedActionType,
    ReviewAnswer,
    RiskLevel,
    Scope,
)


def _candidate(candidate_id: str = "c1") -> LessonCandidate:
    return LessonCandidate(
        id=candidate_id,
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


def test_generate_mcq_review_questions() -> None:
    questions = LessonInterviewer().build_questions(_candidate())
    assert len(questions) >= 6
    assert all(3 <= len(question.options) <= 10 for question in questions)
    assert all(question.allow_free_text for question in questions)


def test_recommended_option_reflects_candidate_scope() -> None:
    candidate = _candidate("c2")
    candidate.scope = Scope.USER
    candidate.recommended_action_type = RecommendedActionType.WORKFLOW_CHANGE
    questions = LessonInterviewer().build_questions(candidate)
    scope_q = next(q for q in questions if q.id == "scope")
    action_q = next(q for q in questions if q.id == "action_type")
    assert scope_q.recommended_option_id == "user"
    assert action_q.recommended_option_id == "workflow_change"


def test_apply_review_answer_updates_scope_and_history() -> None:
    candidate = _candidate("c3")
    question = next(q for q in LessonInterviewer().build_questions(candidate) if q.id == "scope")
    result = apply_review_answer(candidate, question, ReviewAnswer("scope", "team"))
    assert result.scope is Scope.TEAM
    assert result.metadata["review_history"] == [
        {"question_id": "scope", "chosen_option_id": "team", "free_text": ""}
    ]


def test_apply_review_answer_updates_status_approved_and_rejected() -> None:
    approve_candidate = _candidate("c4")
    approve_question = next(
        q for q in LessonInterviewer().build_questions(approve_candidate) if q.id == "decision"
    )
    approved = apply_review_answer(
        approve_candidate, approve_question, ReviewAnswer("decision", "approve")
    )
    assert approved.status is LessonStatus.APPROVED

    reject_candidate = _candidate("c5")
    reject_question = next(
        q for q in LessonInterviewer().build_questions(reject_candidate) if q.id == "decision"
    )
    rejected = apply_review_answer(
        reject_candidate, reject_question, ReviewAnswer("decision", "reject")
    )
    assert rejected.status is LessonStatus.REJECTED


def test_apply_review_answer_preserves_free_text_and_accumulates_history() -> None:
    candidate = _candidate("c6")
    questions = LessonInterviewer().build_questions(candidate)
    scope_question = next(q for q in questions if q.id == "scope")
    risk_question = next(q for q in questions if q.id == "risk_level")
    apply_review_answer(
        candidate, scope_question, ReviewAnswer("scope", "other", "Only platform repositories.")
    )
    apply_review_answer(
        candidate, risk_question, ReviewAnswer("risk_level", "high", "User-visible failure.")
    )
    assert candidate.metadata["review_note_scope"] == "Only platform repositories."
    assert candidate.metadata["review_note_risk_level"] == "User-visible failure."
    assert len(candidate.metadata["review_history"]) == 2
    assert candidate.risk_level is RiskLevel.HIGH


def test_apply_review_answer_stores_applies_when_hint() -> None:
    candidate = _candidate("c7")
    question = next(
        q for q in LessonInterviewer().build_questions(candidate) if q.id == "applicability"
    )
    apply_review_answer(candidate, question, ReviewAnswer("applicability", "specific_tools"))
    assert candidate.metadata["_applies_when_hint"] == "specific_tools"


def test_apply_review_answer_rejects_mismatched_question() -> None:
    candidate = _candidate("c8")
    question = next(q for q in LessonInterviewer().build_questions(candidate) if q.id == "scope")
    with pytest.raises(ValueError, match="does not match"):
        apply_review_answer(candidate, question, ReviewAnswer("risk_level", "high"))
