import pytest

from lessonweaver.interview import (
    LessonInterviewer,
    apply_review_answer,
    is_review_complete,
    load_session,
    remaining_review_questions,
    save_session,
)
from lessonweaver.models import (
    LessonCandidate,
    LessonStatus,
    RecommendedActionType,
    ReviewAnswer,
    ReviewOption,
    ReviewQuestion,
    ReviewSession,
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


def test_apply_review_answer_returns_new_candidate_without_mutating_input() -> None:
    candidate = _candidate("c3b")
    original = candidate.to_dict()
    question = next(q for q in LessonInterviewer().build_questions(candidate) if q.id == "scope")

    result = apply_review_answer(candidate, question, ReviewAnswer("scope", "team"))

    assert result is not candidate
    assert result.metadata is not candidate.metadata
    assert candidate.to_dict() == original
    assert result.scope is Scope.TEAM
    assert result.metadata["review_history"] == [
        {"question_id": "scope", "chosen_option_id": "team", "free_text": ""}
    ]


def test_apply_review_answer_natural_summary_reports_changes() -> None:
    interviewer = LessonInterviewer()
    before = _candidate("c3c")
    question = next(q for q in interviewer.build_questions(before) if q.id == "risk_level")

    after = apply_review_answer(before, question, ReviewAnswer("risk_level", "high"))
    summary = interviewer.build_session_summary(before, after, [])

    assert "risk_level: medium -> high" in summary


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
    candidate = apply_review_answer(
        candidate, scope_question, ReviewAnswer("scope", "other", "Only platform repositories.")
    )
    candidate = apply_review_answer(
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
    candidate = apply_review_answer(
        candidate, question, ReviewAnswer("applicability", "specific_tools")
    )
    assert candidate.metadata["_applies_when_hint"] == "specific_tools"


def test_apply_review_answer_accepts_metadata_effect() -> None:
    candidate = _candidate("c7b")
    candidate.metadata["existing"] = "old"
    question = ReviewQuestion(
        id="custom_metadata",
        question="Apply custom metadata?",
        options=[
            ReviewOption(
                "apply",
                "A",
                "Apply metadata",
                {"metadata": {"custom": "value"}},
            )
        ],
        recommended_option_id="apply",
        rationale="Custom review options may replace metadata.",
    )

    result = apply_review_answer(
        candidate,
        question,
        ReviewAnswer("custom_metadata", "apply", "custom note"),
    )

    assert result.metadata["custom"] == "value"
    assert "existing" not in result.metadata
    assert result.metadata["review_note_custom_metadata"] == "custom note"
    assert result.metadata["review_history"] == [
        {
            "question_id": "custom_metadata",
            "chosen_option_id": "apply",
            "free_text": "custom note",
        }
    ]


def test_apply_review_answer_rejects_mismatched_question() -> None:
    candidate = _candidate("c8")
    question = next(q for q in LessonInterviewer().build_questions(candidate) if q.id == "scope")
    with pytest.raises(ValueError, match="does not match"):
        apply_review_answer(candidate, question, ReviewAnswer("risk_level", "high"))


def test_next_questions_static_when_no_follow_up_fires() -> None:
    interviewer = LessonInterviewer()
    candidate = _candidate("nq1")
    base = interviewer.build_questions(candidate)
    remaining = interviewer.next_questions(candidate, [])
    assert [q.id for q in remaining] == [q.id for q in base]


def test_next_questions_reject_skips_scope_applicability_negative() -> None:
    interviewer = LessonInterviewer()
    candidate = _candidate("nq2")
    remaining = interviewer.next_questions(candidate, [ReviewAnswer("decision", "reject")])
    remaining_ids = {q.id for q in remaining}
    assert "decision" not in remaining_ids  # already answered
    assert remaining_ids.isdisjoint({"scope", "applicability", "negative_conditions"})
    assert "action_type" in remaining_ids
    assert "risk_level" in remaining_ids


def test_next_questions_high_risk_queues_approval_follow_up() -> None:
    interviewer = LessonInterviewer()
    candidate = _candidate("nq3")
    remaining = interviewer.next_questions(candidate, [ReviewAnswer("risk_level", "high")])
    ids = [q.id for q in remaining]
    assert "approval_requirement" in ids
    # The follow-up slots in right after its trigger (risk_level), not at the end.
    assert ids.index("approval_requirement") < ids.index("applicability")
    assert ids.index("approval_requirement") < ids.index("decision")


def test_next_questions_workflow_change_queues_determinism_follow_up() -> None:
    interviewer = LessonInterviewer()
    candidate = _candidate("nq4")
    remaining = interviewer.next_questions(
        candidate, [ReviewAnswer("action_type", "workflow_change")]
    )
    ids = [q.id for q in remaining]
    assert "workflow_determinism" in ids
    assert ids.index("workflow_determinism") < ids.index("risk_level")


def test_remaining_review_questions_uses_persisted_review_history() -> None:
    candidate = _candidate("gate1")
    candidate.metadata["review_history"] = [
        {"question_id": "decision", "chosen_option_id": "approve", "free_text": ""}
    ]
    assert remaining_review_questions(candidate) == [
        "scope",
        "action_type",
        "risk_level",
        "applicability",
        "negative_conditions",
    ]


def test_is_review_complete_uses_persisted_review_history() -> None:
    candidate = _candidate("gate-complete")
    candidate.metadata["review_history"] = [
        {"question_id": "scope", "chosen_option_id": "project", "free_text": ""},
        {"question_id": "action_type", "chosen_option_id": "skill", "free_text": ""},
        {"question_id": "risk_level", "chosen_option_id": "low", "free_text": ""},
        {"question_id": "applicability", "chosen_option_id": "always", "free_text": ""},
        {"question_id": "negative_conditions", "chosen_option_id": "none", "free_text": ""},
        {"question_id": "decision", "chosen_option_id": "approve", "free_text": ""},
    ]

    assert is_review_complete(candidate)


def test_follow_up_answer_is_stored_in_metadata() -> None:
    interviewer = LessonInterviewer()
    candidate = _candidate("nq5")
    follow_up = interviewer.build_follow_up_questions(candidate)["workflow_determinism"]
    candidate = apply_review_answer(
        candidate, follow_up, ReviewAnswer("workflow_determinism", "deterministic_rule")
    )
    assert candidate.metadata["_workflow_determinism"] == "deterministic_rule"


def test_build_session_summary_reports_changes_and_notes() -> None:
    interviewer = LessonInterviewer()
    before = _candidate("sum1")
    after = _candidate("sum1")
    after.risk_level = RiskLevel.HIGH
    after.status = LessonStatus.APPROVED
    answers = [
        ReviewAnswer("risk_level", "high", "User-visible failure."),
        ReviewAnswer("decision", "approve"),
    ]
    summary = interviewer.build_session_summary(before, after, answers)
    assert summary
    assert "candidate -> approved" in summary
    assert "risk_level: medium -> high" in summary
    assert "User-visible failure." in summary


def test_review_session_round_trip_is_lossless(tmp_path) -> None:
    session = ReviewSession(
        session_id="session-1",
        candidate_id="cand-1",
        started_at="2026-05-30T10:00:00+00:00",
        updated_at="2026-05-30T10:05:00+00:00",
        answers=[ReviewAnswer("risk_level", "high", "note")],
        current_question_index=1,
        completed=False,
        notes="paused for stakeholder input",
    )
    path = tmp_path / "session.json"
    save_session(session, path)
    restored = load_session(path)
    assert restored == session


def test_save_session_writes_valid_json(tmp_path) -> None:
    session = ReviewSession(
        session_id="session-2",
        candidate_id="cand-2",
        started_at="2026-05-30T10:00:00+00:00",
        updated_at="2026-05-30T10:00:00+00:00",
    )
    path = tmp_path / "session.json"
    save_session(session, path)
    import json

    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["session_id"] == "session-2"
    assert loaded["answers"] == []
    assert loaded["completed"] is False


def test_build_session_summary_reports_follow_up_effects() -> None:
    interviewer = LessonInterviewer()
    before = _candidate("eff1")
    after = _candidate("eff1")
    after.metadata["_approval_required"] = "explicit"
    summary = interviewer.build_session_summary(before, after, [])
    assert "## Follow-up effects" in summary
    assert "_approval_required: None -> explicit" in summary
