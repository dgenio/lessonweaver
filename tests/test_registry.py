"""Tests for the lesson/skill registry."""

import json

import pytest

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
from lessonweaver.registry import FileSystemRegistry, LessonRegistry
from lessonweaver.schema_versioning import SCHEMA_VERSION


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


def test_filesystem_registry_writes_schema_version_to_all_artifacts(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    candidate = _candidate()
    skill = _skill()
    lesson = _lesson()
    artifact = ExportArtifact(
        "artifact-1", ExportFormat.MARKDOWN, "# content", lesson_id=lesson.lesson_id
    )
    usage = _usage_event("usage-1")

    registry.save_candidate(candidate)
    registry.save_skill(skill)
    registry.save_lesson(lesson)
    registry.save_artifact(artifact)
    registry.save_usage_event(usage)

    paths = [
        registry.candidates_dir / f"{candidate.id}.json",
        registry.skills_dir / f"{skill.id}.json",
        registry.lessons_dir / f"{lesson.lesson_id}.json",
        registry.artifacts_dir / f"{artifact.artifact_id}.json",
        registry.usage_dir / f"{usage.id}.json",
    ]
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == SCHEMA_VERSION


def test_filesystem_registry_loads_v0_payload_and_resaves_current_version(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    candidate = _candidate()
    registry.candidates_dir.mkdir(parents=True)
    path = registry.candidates_dir / f"{candidate.id}.json"
    path.write_text(json.dumps(candidate.to_dict()), encoding="utf-8")

    loaded = registry.load_candidate(candidate.id)
    assert loaded.to_dict() == candidate.to_dict()

    registry.save_candidate(loaded)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION


def test_filesystem_registry_rejects_future_schema_version(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    candidate = _candidate()
    registry.candidates_dir.mkdir(parents=True)
    payload = candidate.to_dict()
    payload["schema_version"] = SCHEMA_VERSION + 1
    (registry.candidates_dir / f"{candidate.id}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="newer lessonweaver"):
        registry.load_candidate(candidate.id)


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
