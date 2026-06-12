"""Tests for the lesson/skill registry."""

from pathlib import Path

import pytest

from lessonweaver import registry as registry_module
from lessonweaver.models import (
    ExportArtifact,
    ExportFormat,
    LessonCandidate,
    OperationalLesson,
    RecommendedActionType,
    RiskLevel,
    Scope,
    SkillCard,
    SkillUsageEvent,
)
from lessonweaver.registry import FileSystemRegistry, LessonRegistry, SkillStore


def _candidate() -> LessonCandidate:
    return LessonCandidate(
        id="lesson-1",
        summary="Test lesson.",
        evidence_trace_ids=["trace-1"],
        evidence_event_ids=["event-1"],
        observed_problem="Problem.",
        proposed_lesson="Lesson.",
        confidence=0.6,
        recommended_action_type=RecommendedActionType.SKILL,
        risk_level=RiskLevel.MEDIUM,
        scope=Scope.PROJECT,
    )


def _skill(skill_id: str = "skill-1") -> SkillCard:
    return SkillCard(
        id=skill_id,
        name="Test Skill",
        description="A test skill with enough detail.",
        applies_when=["testing"],
        does_not_apply_when=["production"],
        instructions=["do this"],
        anti_patterns=["don't do that"],
        evidence_trace_ids=["trace-1"],
        confidence=0.8,
        risk_level=RiskLevel.LOW,
        scope=Scope.PROJECT,
        version="0.1.0",
    )


def _lesson() -> OperationalLesson:
    candidate = _candidate()
    return OperationalLesson(
        lesson_id="op-lesson-1",
        candidate_id=candidate.id,
        title="Test Lesson",
        summary=candidate.summary,
        instructions=[candidate.proposed_lesson],
        applies_when=[candidate.summary],
        does_not_apply_when=["unrelated tasks"],
        anti_patterns=[candidate.observed_problem],
        risk_level=candidate.risk_level,
        scope=candidate.scope,
        recommended_action_type=candidate.recommended_action_type,
        evidence_trace_ids=candidate.evidence_trace_ids,
        evidence_event_ids=candidate.evidence_event_ids,
        confidence=candidate.confidence,
    )


def test_registry_add_and_get_lesson() -> None:
    registry = LessonRegistry()
    candidate = _candidate()
    registry.add_lesson(candidate)
    assert registry.get_lesson("lesson-1") is candidate
    assert registry.get_lesson("nonexistent") is None


def test_registry_add_and_get_skill() -> None:
    registry = LessonRegistry()
    skill = _skill()
    registry.add_skill(skill)
    assert registry.get_skill("skill-1") is skill
    assert registry.get_skill("nonexistent") is None


def test_lesson_registry_conforms_to_skill_store_protocol() -> None:
    registry = LessonRegistry()
    skill = _skill()
    event = _usage_event("usage-1")

    assert isinstance(registry, SkillStore)
    registry.save_skill(skill)
    registry.save_usage_event(event)

    assert registry.load_skill("skill-1") is skill
    assert registry.list_skills() == [skill]
    assert registry.list_usage_events() == [event]


@pytest.mark.parametrize(
    ("loader", "message"),
    [
        ("load_candidate", "candidate 'missing'"),
        ("load_skill", "skill 'missing'"),
        ("load_usage_event", "usage event 'missing'"),
    ],
)
def test_lesson_registry_missing_id_raises_helpful_error(
    loader: str, message: str
) -> None:
    registry = LessonRegistry()
    with pytest.raises(FileNotFoundError, match=message):
        getattr(registry, loader)("missing")


def test_filesystem_registry_candidate_round_trip(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    candidate = _candidate()
    registry.save_candidate(candidate)
    assert registry.load_candidate(candidate.id).to_dict() == candidate.to_dict()
    assert registry.list_candidates()[0].id == candidate.id


def test_filesystem_registry_skill_round_trip(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    skill = _skill()
    registry.save_skill(skill)
    assert registry.load_skill(skill.id).to_dict() == skill.to_dict()
    assert registry.list_skills()[0].id == skill.id


def test_resolve_registry_root_prefers_explicit_path(tmp_path, monkeypatch) -> None:
    explicit = tmp_path / "explicit"
    env_root = tmp_path / "env"
    project_root = tmp_path / ".lessonweaver" / "registry"
    project_root.mkdir(parents=True)
    monkeypatch.setenv("LESSONWEAVER_REGISTRY", str(env_root))
    monkeypatch.chdir(tmp_path)

    assert registry_module.resolve_registry_root(str(explicit)) == explicit


def test_resolve_registry_root_uses_environment_variable(tmp_path, monkeypatch) -> None:
    env_root = tmp_path / "env-registry"
    project_root = tmp_path / ".lessonweaver" / "registry"
    project_root.mkdir(parents=True)
    monkeypatch.setenv("LESSONWEAVER_REGISTRY", str(env_root))
    monkeypatch.chdir(tmp_path)

    assert registry_module.resolve_registry_root(None) == env_root


def test_resolve_registry_root_discovers_project_registry_from_subdirectory(
    tmp_path, monkeypatch
) -> None:
    project_registry = tmp_path / ".lessonweaver" / "registry"
    nested = tmp_path / "src" / "pkg"
    project_registry.mkdir(parents=True)
    nested.mkdir(parents=True)
    monkeypatch.delenv("LESSONWEAVER_REGISTRY", raising=False)
    monkeypatch.chdir(nested)

    assert registry_module.resolve_registry_root(None) == project_registry


def test_resolve_registry_root_falls_back_to_home_default(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    cwd = tmp_path / "work"
    home.mkdir()
    cwd.mkdir()
    monkeypatch.delenv("LESSONWEAVER_REGISTRY", raising=False)
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.chdir(cwd)

    assert registry_module.resolve_registry_root(None) == home / ".lessonweaver" / "registry"


def test_filesystem_registry_default_uses_resolved_root(tmp_path, monkeypatch) -> None:
    project_registry = tmp_path / ".lessonweaver" / "registry"
    project_registry.mkdir(parents=True)
    monkeypatch.delenv("LESSONWEAVER_REGISTRY", raising=False)
    monkeypatch.chdir(tmp_path)

    assert FileSystemRegistry().root == project_registry


def test_filesystem_registry_lesson_and_artifact_round_trip(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    lesson = _lesson()
    artifact = ExportArtifact(
        "artifact-1", ExportFormat.MARKDOWN, "# content", lesson_id=lesson.lesson_id
    )
    registry.save_lesson(lesson)
    registry.save_artifact(artifact)
    assert registry.load_lesson(lesson.lesson_id).to_dict() == lesson.to_dict()
    assert registry.load_artifact(artifact.artifact_id).to_dict() == artifact.to_dict()


def test_filesystem_registry_missing_id_raises_helpful_error(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    with pytest.raises(FileNotFoundError, match="candidate 'missing'"):
        registry.load_candidate("missing")


@pytest.mark.parametrize("bad_id", ["../x", "a/b", "a\\b", "bad\x00id"])
def test_filesystem_registry_rejects_unsafe_ids(tmp_path, bad_id: str) -> None:
    registry = FileSystemRegistry(tmp_path)
    with pytest.raises(ValueError, match="unsafe registry id"):
        registry.save_skill(_skill(bad_id))


def test_filesystem_registry_delete(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    skill = _skill()
    registry.save_skill(skill)
    registry.delete_skill(skill.id)
    assert registry.list_skills() == []


def test_filesystem_registry_list_rejects_non_object_json(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.skills_dir.mkdir(parents=True)
    (registry.skills_dir / "bad.json").write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a JSON object"):
        registry.list_skills()


def test_filesystem_registry_list_rejects_invalid_json(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.skills_dir.mkdir(parents=True)
    (registry.skills_dir / "bad.json").write_text("{", encoding="utf-8")

    with pytest.raises(ValueError, match="contains invalid JSON"):
        registry.list_skills()


def _usage_event(event_id: str, skill_id: str = "skill-1") -> SkillUsageEvent:
    return SkillUsageEvent(
        id=event_id,
        skill_id=skill_id,
        skill_version="0.1.0",
        task_context="testing reuse",
    )


def test_filesystem_registry_usage_event_round_trip(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    event = _usage_event("usage-1")
    registry.save_usage_event(event)
    assert registry.load_usage_event("usage-1").to_dict() == event.to_dict()
    assert registry.list_usage_events()[0].id == "usage-1"


def test_filesystem_registry_list_skill_usage_filters_by_skill_id(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_usage_event(_usage_event("usage-1", skill_id="skill-1"))
    registry.save_usage_event(_usage_event("usage-2", skill_id="skill-1"))
    registry.save_usage_event(_usage_event("usage-3", skill_id="skill-2"))

    for_skill_1 = registry.list_skill_usage("skill-1")
    assert {event.id for event in for_skill_1} == {"usage-1", "usage-2"}
    assert registry.list_skill_usage("skill-2")[0].id == "usage-3"
    assert registry.list_skill_usage("unknown") == []
