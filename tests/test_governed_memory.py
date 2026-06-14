from datetime import datetime, timezone

from lessonweaver.governed_memory import build_governed_memory_snapshot
from lessonweaver.models import (
    LessonStatus,
    OperationalLesson,
    RecommendedActionType,
    ReviewAnswer,
    RiskLevel,
    Scope,
    SkillCard,
    SkillStatus,
)
from lessonweaver.registry import FileSystemRegistry

NOW = datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc)


def _lesson() -> OperationalLesson:
    return OperationalLesson(
        lesson_id="lesson-1",
        candidate_id="cand-1",
        title="Inspect diffs before review",
        summary="A reviewed operational lesson.",
        instructions=["Inspect changed files before conclusions."],
        applies_when=["reviewing pull requests"],
        does_not_apply_when=["no code changes"],
        anti_patterns=["approving from title only"],
        risk_level=RiskLevel.MEDIUM,
        scope=Scope.PROJECT,
        recommended_action_type=RecommendedActionType.SKILL,
        evidence_trace_ids=["trace-1"],
        evidence_event_ids=["event-1"],
        confidence=0.82,
        review_answers=[ReviewAnswer("decision", "approve", "Reviewed by maintainer.")],
        status=LessonStatus.APPROVED,
        created_at=NOW,
        approved_at=NOW,
    )


def _skill(*, status: SkillStatus = SkillStatus.ACTIVE) -> SkillCard:
    return SkillCard(
        id="skill-1",
        name="PR Diff First",
        description="Inspect diffs before review.",
        applies_when=["reviewing pull requests"],
        does_not_apply_when=["no code changes"],
        instructions=["Inspect changed files first."],
        anti_patterns=["Approving from title only."],
        evidence_trace_ids=["trace-1"],
        confidence=0.82,
        risk_level=RiskLevel.MEDIUM,
        scope=Scope.PROJECT,
        version="0.1.0",
        status=status,
        approved_by="reviewer",
        created_at=NOW,
        updated_at=NOW,
    )


def test_governed_memory_snapshot_survives_registry_reload_with_provenance(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_lesson(_lesson())
    registry.save_skill(_skill())

    reloaded = FileSystemRegistry(tmp_path)
    snapshot = build_governed_memory_snapshot(reloaded)

    assert snapshot.kind == "governed_operational_memory"
    assert snapshot.generic_chat_memory is False
    assert snapshot.lesson_count == 1
    assert snapshot.skill_count == 1
    assert snapshot.evidence_trace_ids == ["trace-1"]
    assert snapshot.lifecycle_counts == {"approved_lessons": 1, "active_skills": 1}
    assert snapshot.to_dict()["records"][0]["lesson_id"] == "lesson-1"
    assert snapshot.to_dict()["records"][0]["skill_id"] == "skill-1"
    assert snapshot.to_dict()["records"][0]["reviewed"] is True


def test_governed_memory_snapshot_reports_lifecycle_and_evidence_gaps(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    lesson = _lesson()
    lesson.evidence_trace_ids = []
    registry.save_lesson(lesson)
    registry.save_skill(_skill(status=SkillStatus.DEPRECATED))

    snapshot = build_governed_memory_snapshot(registry)

    assert snapshot.lifecycle_counts == {"approved_lessons": 1, "deprecated_skills": 1}
    assert snapshot.governance_warnings == [
        "lesson lesson-1 has no evidence trace ids",
        "skill skill-1 is deprecated",
    ]
