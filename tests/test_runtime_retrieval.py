from lessonweaver.models import RiskLevel, Scope, SkillCard, SkillStatus
from lessonweaver.registry import FileSystemRegistry
from lessonweaver.runtime import RuntimeLessonQuery, RuntimeLessonRetriever


def _skill(
    skill_id: str,
    *,
    status: SkillStatus = SkillStatus.ACTIVE,
    risk_level: RiskLevel = RiskLevel.LOW,
    scope: Scope = Scope.PROJECT,
    does_not_apply_when: list[str] | None = None,
) -> SkillCard:
    return SkillCard(
        id=skill_id,
        name="PR Diff First",
        description="Inspect diffs before reviewing pull requests.",
        applies_when=["reviewing pull requests"],
        does_not_apply_when=does_not_apply_when or ["no code changes"],
        instructions=["Inspect changed files first."],
        anti_patterns=["Approve from title only."],
        evidence_trace_ids=["trace-1"],
        confidence=0.8,
        risk_level=risk_level,
        scope=scope,
        version="0.1.0",
        status=status,
    )


def test_runtime_retrieval_returns_approved_and_active_lessons_by_default(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill("approved", status=SkillStatus.APPROVED))
    registry.save_skill(_skill("active", status=SkillStatus.ACTIVE))
    registry.save_skill(_skill("draft", status=SkillStatus.DRAFT))
    registry.save_skill(_skill("rejected", status=SkillStatus.REJECTED))
    registry.save_skill(_skill("deprecated", status=SkillStatus.DEPRECATED))

    results = RuntimeLessonRetriever(registry).retrieve(
        RuntimeLessonQuery(task="Review this pull request", max_results=10)
    )

    assert [result.skill.id for result in results] == ["approved", "active"]


def test_runtime_retrieval_excludes_negative_applicability_matches(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(
        _skill("no-code", does_not_apply_when=["reviewing pull requests with no code changes"])
    )

    results = RuntimeLessonRetriever(registry).retrieve(
        RuntimeLessonQuery(task="Review this pull request with no code changes")
    )

    assert results == []


def test_runtime_query_applies_scope_risk_and_tool_context(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill("low-project", scope=Scope.PROJECT, risk_level=RiskLevel.LOW))
    registry.save_skill(_skill("high-project", scope=Scope.PROJECT, risk_level=RiskLevel.HIGH))
    registry.save_skill(_skill("low-team", scope=Scope.TEAM, risk_level=RiskLevel.LOW))
    registry.save_skill(_skill("low-global", scope=Scope.GLOBAL, risk_level=RiskLevel.LOW))

    results = RuntimeLessonRetriever(registry).retrieve(
        RuntimeLessonQuery(
            task="Review this pull request",
            runtime="coding-agent",
            tools=["github"],
            scope="project",
            risk_level="medium",
            max_results=10,
        )
    )

    assert [result.skill.id for result in results] == ["low-project", "low-global"]


def test_runtime_query_serializes_context_contract() -> None:
    query = RuntimeLessonQuery(
        task="Review this pull request",
        runtime="coding-agent",
        tools=["github"],
        scope="project",
        risk_level="low",
        artifact_types=["skill"],
        max_results=3,
    )

    assert query.to_dict() == {
        "task": "Review this pull request",
        "runtime": "coding-agent",
        "tools": ["github"],
        "scope": "project",
        "risk_level": "low",
        "artifact_types": ["skill"],
        "max_results": 3,
    }
