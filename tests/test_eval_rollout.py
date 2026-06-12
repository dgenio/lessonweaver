from lessonweaver.eval_rollout import (
    generate_eval_suite_for_candidate,
    generate_eval_suite_for_skill,
)
from lessonweaver.models import (
    LessonCandidate,
    LessonStatus,
    RecommendedActionType,
    RiskLevel,
    Scope,
    SkillCard,
    SkillStatus,
)


def _skill(status: SkillStatus = SkillStatus.EXPERIMENTAL) -> SkillCard:
    return SkillCard(
        id="skill-pr-review",
        name="PR Diff First",
        description="Inspect diffs before approving pull requests.",
        applies_when=["Reviewing pull requests"],
        does_not_apply_when=["Generating SQL migrations"],
        instructions=["Inspect changed files first"],
        anti_patterns=[],
        evidence_trace_ids=["trace-1"],
        confidence=0.8,
        risk_level=RiskLevel.LOW,
        scope=Scope.PROJECT,
        version="0.2.0",
        status=status,
    )


def _candidate() -> LessonCandidate:
    return LessonCandidate(
        id="cand-1",
        summary="Inspect diffs before PR review",
        evidence_trace_ids=["trace-1"],
        evidence_event_ids=["event-1"],
        observed_problem="Agent approved a PR without inspecting the diff.",
        proposed_lesson="Inspect changed files before drawing review conclusions.",
        confidence=0.62,
        recommended_action_type=RecommendedActionType.SKILL,
        risk_level=RiskLevel.MEDIUM,
        scope=Scope.PROJECT,
        status=LessonStatus.APPROVED,
    )


def test_generate_eval_suite_for_skill_has_positive_and_negative_examples() -> None:
    suite = generate_eval_suite_for_skill(_skill())

    assert suite.suite_id == "rollout-eval-skill-pr-review"
    assert suite.skill_id == "skill-pr-review"
    assert [example.should_load for example in suite.examples] == [True, False]
    assert suite.examples[0].task == "Reviewing pull requests"
    assert suite.examples[1].task == "Generating SQL migrations"


def test_generate_eval_suite_for_candidate_uses_expected_skill_id() -> None:
    suite = generate_eval_suite_for_candidate(_candidate(), skill_id="skill-cand-1")

    assert suite.skill_id == "skill-cand-1"
    assert suite.examples[0].task == "Inspect changed files before drawing review conclusions."
    assert suite.examples[0].expected_skill_id == "skill-cand-1"
    assert suite.examples[1].should_load is False
