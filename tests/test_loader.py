from lessonweaver.loader import SkillLoader
from lessonweaver.models import LoadingPolicy, RiskLevel, Scope, SkillCard, SkillStatus
from lessonweaver.registry import FileSystemRegistry, LessonRegistry


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


def test_loader_accepts_in_memory_registry() -> None:
    registry = LessonRegistry()
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


def test_loader_policy_loads_approved_skill_retrieval_would_drop(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    skill = _skill("pr", "PR Diff First", "Inspect diffs before reviewing.")
    skill.status = SkillStatus.APPROVED
    registry.save_skill(skill)

    # Without a policy, retrieval's ACTIVE-only default drops the APPROVED skill.
    no_policy = SkillLoader(registry).load_for_task("Review this PR", budget_chars=200)
    assert no_policy.included_skills == []

    # A policy that admits APPROVED skills must actually let them load.
    with_policy = SkillLoader(registry, policy=LoadingPolicy()).load_for_task(
        "Review this PR", budget_chars=200
    )
    assert with_policy.included_skills == ["pr"]


def test_loader_policy_without_approved_gate_loads_draft(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    skill = _skill("pr", "PR Diff First", "Inspect diffs before reviewing.")
    skill.status = SkillStatus.DRAFT
    registry.save_skill(skill)

    policy = LoadingPolicy(require_approved_status=False)
    context = SkillLoader(registry, policy=policy).load_for_task("Review this PR", budget_chars=200)
    assert context.included_skills == ["pr"]


def test_loader_policy_max_skills_caps_results(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill("a", "PR A", "Inspect diffs before reviewing carefully."))
    registry.save_skill(_skill("b", "PR B", "Inspect diffs before reviewing thoroughly."))

    context = SkillLoader(registry, policy=LoadingPolicy(max_skills=1)).load_for_task(
        "Review this PR", budget_chars=2000, max_skills=10
    )
    assert len(context.included_skills) == 1


def test_loader_policy_character_budget_caps_compilation(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill("a", "PR A", "x" * 200))
    registry.save_skill(_skill("b", "PR B", "y" * 200))

    context = SkillLoader(registry, policy=LoadingPolicy(max_budget_chars=12)).load_for_task(
        "Review this PR", budget_chars=2000, max_skills=2
    )
    assert len(context.snippet) <= 12
    assert context.omitted_skills
