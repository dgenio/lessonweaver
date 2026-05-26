from lessonweaver.compile import InclusionLevel, SkillCompiler
from lessonweaver.models import RiskLevel, Scope, SkillCard, SkillStatus
from lessonweaver.retrieval import RetrievalResult


def _skill(skill_id: str, name: str, description: str) -> SkillCard:
    return SkillCard(
        id=skill_id,
        name=name,
        description=description,
        applies_when=["reviewing pull requests"],
        does_not_apply_when=["no code changes"],
        instructions=["Inspect changed files first"],
        anti_patterns=[],
        evidence_trace_ids=["trace-1"],
        confidence=0.8,
        risk_level=RiskLevel.LOW,
        scope=Scope.PROJECT,
        version="0.2.0",
        status=SkillStatus.ACTIVE,
    )


def _result(skill: SkillCard, score: float) -> RetrievalResult:
    return RetrievalResult(skill, score, "matched")


def test_compile_respects_budget_chars() -> None:
    result = _result(_skill("a", "Very Long Skill Name", "x" * 200), 1.0)
    context = SkillCompiler().compile(
        [result], budget_chars=30, default_inclusion=InclusionLevel.SUMMARY
    )
    assert len(context.snippet) <= 30
    assert context.included_skills == ["a"]


def test_higher_scoring_skills_are_included_first() -> None:
    low = _result(_skill("low", "Low", "Low description"), 0.2)
    high = _result(_skill("high", "High", "High description"), 0.9)
    context = SkillCompiler().compile([low, high], budget_chars=200)
    assert context.included_skills[:2] == ["high", "low"]


def test_skills_that_exceed_budget_are_omitted() -> None:
    result = _result(_skill("a", "NameTooLongForBudget", "description"), 1.0)
    context = SkillCompiler().compile(
        [result], budget_chars=5, default_inclusion=InclusionLevel.SUMMARY
    )
    assert context.included_skills == []
    assert context.omitted_skills == ["a"]


def test_name_only_downgrade() -> None:
    result = _result(_skill("a", "Short", "x" * 200), 1.0)
    context = SkillCompiler().compile(
        [result], budget_chars=13, default_inclusion=InclusionLevel.SUMMARY
    )
    assert context.snippet == "[Skill] Short"
    assert context.included_skills == ["a"]


def test_total_chars_matches_snippet_length() -> None:
    context = SkillCompiler().compile(
        [_result(_skill("a", "A", "Description"), 1.0)], budget_chars=200
    )
    assert context.total_chars == len(context.snippet)


def test_empty_results_return_empty_snippet() -> None:
    context = SkillCompiler().compile([])
    assert context.snippet == ""
    assert context.included_skills == []
    assert context.omitted_skills == []
