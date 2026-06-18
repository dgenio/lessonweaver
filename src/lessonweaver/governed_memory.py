"""Governed operational memory snapshots over the registry."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .models import OperationalLesson, SkillCard, SkillStatus
from .registry import FileSystemRegistry


@dataclass(frozen=True, slots=True)
class GovernedMemoryRecord:
    lesson_id: str | None
    skill_id: str | None
    title: str
    reviewed: bool
    lifecycle: str
    risk_level: str
    scope: str
    evidence_trace_ids: list[str]
    evidence_event_ids: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "lesson_id": self.lesson_id,
            "skill_id": self.skill_id,
            "title": self.title,
            "reviewed": self.reviewed,
            "lifecycle": self.lifecycle,
            "risk_level": self.risk_level,
            "scope": self.scope,
            "evidence_trace_ids": list(self.evidence_trace_ids),
            "evidence_event_ids": list(self.evidence_event_ids),
        }


@dataclass(frozen=True, slots=True)
class GovernedMemorySnapshot:
    kind: str = "governed_operational_memory"
    generic_chat_memory: bool = False
    records: list[GovernedMemoryRecord] = field(default_factory=list)
    lifecycle_counts: dict[str, int] = field(default_factory=dict)
    governance_warnings: list[str] = field(default_factory=list)

    @property
    def lesson_count(self) -> int:
        return sum(1 for record in self.records if record.lesson_id is not None)

    @property
    def skill_count(self) -> int:
        return sum(1 for record in self.records if record.skill_id is not None)

    @property
    def evidence_trace_ids(self) -> list[str]:
        return sorted(
            {trace_id for record in self.records for trace_id in record.evidence_trace_ids}
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "generic_chat_memory": self.generic_chat_memory,
            "lesson_count": self.lesson_count,
            "skill_count": self.skill_count,
            "evidence_trace_ids": self.evidence_trace_ids,
            "lifecycle_counts": dict(self.lifecycle_counts),
            "governance_warnings": list(self.governance_warnings),
            "records": [record.to_dict() for record in self.records],
        }


def build_governed_memory_snapshot(registry: FileSystemRegistry) -> GovernedMemorySnapshot:
    """Summarize durable reviewed lessons and skills stored in a registry."""

    lessons = registry.list_lessons()
    skills = registry.list_skills()
    skills_by_candidate = {
        skill.metadata.get("candidate_id"): skill
        for skill in skills
        if skill.metadata.get("candidate_id")
    }
    records = [
        _lesson_record(lesson, _matching_skill(lesson, skills, skills_by_candidate))
        for lesson in lessons
    ]
    skill_ids_in_records = {record.skill_id for record in records if record.skill_id is not None}
    records.extend(_skill_record(skill) for skill in skills if skill.id not in skill_ids_in_records)
    lifecycle_counts = _lifecycle_counts(lessons, skills)
    warnings = _warnings(lessons, skills)
    return GovernedMemorySnapshot(
        records=records,
        lifecycle_counts=lifecycle_counts,
        governance_warnings=warnings,
    )


def _lesson_record(lesson: OperationalLesson, skill: SkillCard | None) -> GovernedMemoryRecord:
    evidence_trace_ids = _merge_ids(
        lesson.evidence_trace_ids,
        skill.evidence_trace_ids if skill else [],
    )
    return GovernedMemoryRecord(
        lesson_id=lesson.lesson_id,
        skill_id=skill.id if skill else None,
        title=lesson.title,
        reviewed=lesson.approved_at is not None or bool(lesson.review_answers),
        lifecycle=f"lesson:{lesson.status.value}",
        risk_level=lesson.risk_level.value,
        scope=lesson.scope.value,
        evidence_trace_ids=evidence_trace_ids,
        evidence_event_ids=list(lesson.evidence_event_ids),
    )


def _merge_ids(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)
    return merged


def _skill_record(skill: SkillCard) -> GovernedMemoryRecord:
    return GovernedMemoryRecord(
        lesson_id=None,
        skill_id=skill.id,
        title=skill.name,
        reviewed=bool(skill.approved_by or skill.metadata.get("approved_by")),
        lifecycle=f"skill:{skill.status.value}",
        risk_level=skill.risk_level.value,
        scope=skill.scope.value,
        evidence_trace_ids=list(skill.evidence_trace_ids),
        evidence_event_ids=[],
    )


def _matching_skill(
    lesson: OperationalLesson,
    skills: list[SkillCard],
    skills_by_candidate: dict[object, SkillCard],
) -> SkillCard | None:
    if lesson.candidate_id in skills_by_candidate:
        return skills_by_candidate[lesson.candidate_id]
    lesson_trace_ids = set(lesson.evidence_trace_ids)
    if not lesson_trace_ids:
        return None
    return next(
        (skill for skill in skills if lesson_trace_ids & set(skill.evidence_trace_ids)),
        None,
    )


def _lifecycle_counts(
    lessons: list[OperationalLesson],
    skills: list[SkillCard],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for lesson in lessons:
        counts[f"{lesson.status.value}_lessons"] += 1
    for skill in skills:
        counts[f"{skill.status.value}_skills"] += 1
    return dict(sorted(counts.items()))


def _warnings(lessons: list[OperationalLesson], skills: list[SkillCard]) -> list[str]:
    warnings: list[str] = []
    for lesson in lessons:
        if not lesson.evidence_trace_ids:
            warnings.append(f"lesson {lesson.lesson_id} has no evidence trace ids")
    for skill in skills:
        if not skill.evidence_trace_ids:
            warnings.append(f"skill {skill.id} has no evidence trace ids")
        if skill.status is SkillStatus.DEPRECATED:
            warnings.append(f"skill {skill.id} is deprecated")
    return warnings
