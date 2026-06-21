from lessonweaver.models import RiskLevel, Scope, SkillCard, SkillStatus
from lessonweaver.retrieval import RetrievalQuery, SkillRetriever


def _skill(
    skill_id: str,
    name: str,
    applies_when: list[str],
    *,
    status: SkillStatus = SkillStatus.ACTIVE,
    risk_level: RiskLevel = RiskLevel.LOW,
    scope: Scope = Scope.PROJECT,
) -> SkillCard:
    return SkillCard(
        id=skill_id,
        name=name,
        description=f"{name} description with enough detail.",
        applies_when=applies_when,
        does_not_apply_when=["Unrelated tasks"],
        instructions=["Follow the relevant checklist."],
        anti_patterns=[],
        evidence_trace_ids=["trace-1"],
        confidence=0.8,
        risk_level=risk_level,
        scope=scope,
        version="0.2.0",
        status=status,
    )


def test_relevant_skill_scores_higher_than_unrelated_skill() -> None:
    pr_skill = _skill("pr", "PR Diff First", ["reviewing pull requests"])
    policy_skill = _skill("policy", "Policy Check", ["answering customer policy questions"])
    results = SkillRetriever().retrieve(
        [policy_skill, pr_skill], RetrievalQuery(task="Review this PR")
    )
    assert [result.skill.id for result in results] == ["pr"]


def test_pr_synonym_expansion_matches_pull_request_query() -> None:
    pr_skill = _skill("pr", "PR Diff First", ["reviewing code changes"])
    results = SkillRetriever().retrieve([pr_skill], RetrievalQuery(task="Review pull request"))
    assert [result.skill.id for result in results] == ["pr"]


def test_non_active_skills_are_excluded_by_default() -> None:
    skill = _skill("draft", "Draft Skill", ["reviewing pull requests"], status=SkillStatus.DRAFT)
    assert SkillRetriever().retrieve([skill], RetrievalQuery(task="Review this PR")) == []


def test_risk_level_filter_excludes_higher_risk_skill() -> None:
    skill = _skill(
        "high", "High Risk Skill", ["reviewing pull requests"], risk_level=RiskLevel.HIGH
    )
    assert (
        SkillRetriever().retrieve([skill], RetrievalQuery(task="Review this PR", risk_level="low"))
        == []
    )


def test_max_results_is_respected() -> None:
    skills = [
        _skill("a", "PR A", ["reviewing pull requests"]),
        _skill("b", "PR B", ["reviewing pull requests"]),
    ]
    results = SkillRetriever().retrieve(
        skills, RetrievalQuery(task="Review this PR", max_results=1)
    )
    assert len(results) == 1


def test_empty_skill_list_returns_empty_result() -> None:
    assert SkillRetriever().retrieve([], RetrievalQuery(task="Review this PR")) == []


def test_no_token_overlap_returns_empty_result() -> None:
    skill = _skill("policy", "Policy Check", ["answering customer policy questions"])
    assert SkillRetriever().retrieve([skill], RetrievalQuery(task="Generate SQL migration")) == []


def test_scope_boost_changes_ranking() -> None:
    project = _skill("project", "Review Skill", ["reviewing code"], scope=Scope.PROJECT)
    team = _skill("team", "Review Skill", ["reviewing code"], scope=Scope.TEAM)
    results = SkillRetriever().retrieve(
        [team, project], RetrievalQuery(task="reviewing code", scope="project")
    )
    assert results[0].skill.id == "project"


def test_invalid_scope_and_risk_level_are_ignored() -> None:
    skill = _skill("pr", "PR Diff First", ["reviewing pull requests"])
    results = SkillRetriever().retrieve(
        [skill],
        RetrievalQuery(task="Review this PR", scope="not-a-scope", risk_level="not-a-risk"),
    )
    assert [result.skill.id for result in results] == ["pr"]
