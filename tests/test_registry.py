"""Tests for the lesson/skill registry."""

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
)
from lessonweaver.registry import FileSystemRegistry, LessonRegistry


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
