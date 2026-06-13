"""Tests for the library-level approval service (#166)."""

from __future__ import annotations

import pytest

from lessonweaver import (
    IncompleteReviewError,
    LessonCandidate,
    LessonInterviewer,
    LessonStatus,
    RecommendedActionType,
    ReviewAnswer,
    RiskLevel,
    Scope,
    apply_review_answer,
    approve_and_save,
    approve_candidate,
    remaining_review_questions,
)
from lessonweaver.registry import FileSystemRegistry


def _candidate(candidate_id: str = "cand-1") -> LessonCandidate:
    return LessonCandidate(
        id=candidate_id,
        summary="Candidate lesson based on observed correction...",
        evidence_trace_ids=["trace-1"],
        evidence_event_ids=["event-1"],
        observed_problem="Agent missed key step.",
        proposed_lesson="Check diff first.",
        confidence=0.7,
        recommended_action_type=RecommendedActionType.SKILL,
        risk_level=RiskLevel.LOW,
        scope=Scope.PROJECT,
    )


def _answer(candidate: LessonCandidate, question_id: str, option_id: str) -> LessonCandidate:
    interviewer = LessonInterviewer()
    question = next(
        (
            item
            for item in [
                *interviewer.build_questions(candidate),
                *interviewer.build_follow_up_questions(candidate).values(),
            ]
            if item.id == question_id
        ),
        None,
    )
    assert question is not None
    return apply_review_answer(candidate, question, ReviewAnswer(question_id, option_id))


def _complete_review(candidate: LessonCandidate) -> LessonCandidate:
    for question_id, option_id in [
        ("scope", "project"),
        ("action_type", "skill"),
        ("risk_level", "low"),
        ("applicability", "always"),
        ("negative_conditions", "none"),
        ("decision", "approve"),
    ]:
        candidate = _answer(candidate, question_id, option_id)
    return candidate


def test_remaining_review_questions_matches_interviewer_gate() -> None:
    candidate = _candidate()
    remaining = remaining_review_questions(candidate)

    assert "decision" in remaining
    assert remaining == [
        question.id for question in LessonInterviewer().next_questions(candidate, [])
    ]


def test_approve_candidate_blocks_incomplete_review() -> None:
    candidate = _candidate()

    with pytest.raises(IncompleteReviewError) as exc:
        approve_candidate(candidate, approved_by="reviewer")

    assert "decision" in exc.value.unanswered_questions
    assert candidate.status is LessonStatus.CANDIDATE


def test_approve_candidate_returns_domain_objects_without_persisting() -> None:
    candidate = _complete_review(_candidate())
    result = approve_candidate(candidate, approved_by="reviewer", name="Diff First")

    assert result.candidate.status is LessonStatus.APPROVED
    assert result.candidate.approved_by == "reviewer"
    assert result.lesson.lesson_id == "lesson-cand-1"
    assert result.lesson.review_answers[0].question_id == "scope"
    assert result.skill.id == "skill-cand-1"
    assert result.skill.name == "Diff First"
    assert result.to_dict() == {
        "candidate_id": "cand-1",
        "lesson_id": "lesson-cand-1",
        "skill_id": "skill-cand-1",
    }


def test_approve_and_save_persists_all_objects(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    candidate = _complete_review(_candidate("cand-save"))
    registry.save_candidate(candidate)

    result = approve_and_save(registry, candidate, approved_by="reviewer")

    assert result.to_dict() == {
        "candidate_id": "cand-save",
        "lesson_id": "lesson-cand-save",
        "skill_id": "skill-cand-save",
    }
    assert registry.load_candidate("cand-save").status is LessonStatus.APPROVED
    assert registry.load_lesson("lesson-cand-save").candidate_id == "cand-save"
    assert registry.load_skill("skill-cand-save").metadata["candidate_id"] == "cand-save"


def test_approve_and_save_allow_incomplete_records_override(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    candidate = _candidate("cand-override")
    registry.save_candidate(candidate)

    result = approve_and_save(
        registry,
        candidate,
        approved_by="reviewer",
        allow_incomplete=True,
    )

    override = registry.load_skill(result.skill.id).metadata["incomplete_review_override"]
    assert override["approved_by"] == "reviewer"
    assert "decision" in override["unanswered_questions"]
    assert (
        registry.load_candidate("cand-override").metadata["incomplete_review_override"] == override
    )
