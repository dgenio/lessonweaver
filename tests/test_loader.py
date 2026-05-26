from lessonweaver.loader import SkillLoader
from lessonweaver.models import RiskLevel, Scope, SkillCard, SkillStatus
from lessonweaver.registry import FileSystemRegistry


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


def test_loader_empty_registry_returns_empty_context(tmp_path) -> None:
    context = SkillLoader(FileSystemRegistry(tmp_path)).load_for_task("Review this PR")
    assert context.snippet == ""


def test_loader_single_skill_match(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill("pr", "PR Diff First", "Inspect diffs before reviewing."))
    context = SkillLoader(registry).load_for_task("Review this PR", budget_chars=200)
    assert "PR Diff First" in context.snippet
    assert context.included_skills == ["pr"]


def test_loader_multiple_skills_with_budget_trim(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill("a", "PR A", "x" * 200))
    registry.save_skill(_skill("b", "PR B", "y" * 200))
    context = SkillLoader(registry).load_for_task("Review this PR", budget_chars=12, max_skills=2)
    assert len(context.snippet) <= 12
    assert context.included_skills
    assert context.omitted_skills


def test_loader_no_match(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill("pr", "PR Diff First", "Inspect diffs before reviewing."))
    context = SkillLoader(registry).load_for_task("Write SQL migration")
    assert context.snippet == ""
