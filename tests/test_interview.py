from lessonweaver.interview import LessonInterviewer
from lessonweaver.models import LessonCandidate, RecommendedActionType, RiskLevel, Scope


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
