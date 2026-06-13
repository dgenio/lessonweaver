"""Library-level approval service for reviewed lesson candidates."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone

from .interview import LessonInterviewer
from .models import (
    LessonCandidate,
    LessonStatus,
    OperationalLesson,
    ReviewAnswer,
    SensitivityLevel,
    SkillCard,
    SkillStatus,
)
from .registry import FileSystemRegistry


@dataclass(slots=True)
class ApprovalResult:
    """Domain objects produced when a candidate is approved."""

    candidate: LessonCandidate
    lesson: OperationalLesson
    skill: SkillCard

    def to_dict(self) -> dict[str, str]:
        return {
            "candidate_id": self.candidate.id,
            "lesson_id": self.lesson.lesson_id,
            "skill_id": self.skill.id,
        }


class IncompleteReviewError(ValueError):
    """Raised when approval is attempted before required review questions are done."""

    def __init__(self, candidate_id: str, unanswered_questions: list[str]) -> None:
        self.candidate_id = candidate_id
        self.unanswered_questions = unanswered_questions
        questions = ", ".join(unanswered_questions)
        super().__init__(
            f"candidate '{candidate_id}' review is incomplete; unanswered questions: {questions}"
        )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _review_answers(candidate: LessonCandidate) -> list[ReviewAnswer]:
    history = candidate.metadata.get("review_history", [])
    return [ReviewAnswer.from_dict(item) for item in history if isinstance(item, dict)]


def remaining_review_questions(candidate: LessonCandidate) -> list[str]:
    """Return required guided-review question ids that still need answers."""

    return [
        question.id
        for question in LessonInterviewer().next_questions(candidate, _review_answers(candidate))
    ]


def skill_from_candidate(
    candidate: LessonCandidate,
    *,
    skill_id: str,
    name: str,
    approved_by: str | None,
    now: datetime | None = None,
) -> SkillCard:
    moment = now or _utc_now()
    return SkillCard(
        id=skill_id,
        name=name,
        description=candidate.summary,
        applies_when=[candidate.summary],
        does_not_apply_when=["When the task is unrelated to the observed trace context."],
        instructions=[candidate.proposed_lesson],
        anti_patterns=[candidate.observed_problem],
        evidence_trace_ids=candidate.evidence_trace_ids,
        confidence=candidate.confidence,
        risk_level=candidate.risk_level,
        scope=candidate.scope,
        version="0.1.0",
        status=SkillStatus.APPROVED,
        sensitivity=SensitivityLevel.INTERNAL,
        owner=candidate.owner,
        approved_by=approved_by,
        created_at=moment,
        updated_at=moment,
        approved_at=moment,
        metadata={"candidate_id": candidate.id},
    )


def lesson_from_candidate(
    candidate: LessonCandidate,
    *,
    lesson_id: str,
    title: str,
    now: datetime | None = None,
) -> OperationalLesson:
    return OperationalLesson(
        lesson_id=lesson_id,
        candidate_id=candidate.id,
        title=title,
        summary=candidate.summary,
        instructions=[candidate.proposed_lesson],
        applies_when=[candidate.summary],
        does_not_apply_when=["When the task is unrelated to the observed trace context."],
        anti_patterns=[candidate.observed_problem],
        risk_level=candidate.risk_level,
        scope=candidate.scope,
        recommended_action_type=candidate.recommended_action_type,
        evidence_trace_ids=candidate.evidence_trace_ids,
        evidence_event_ids=candidate.evidence_event_ids,
        confidence=candidate.confidence,
        review_answers=_review_answers(candidate),
        status=LessonStatus.APPROVED,
        approved_at=now or _utc_now(),
    )


def approve_candidate(
    candidate: LessonCandidate,
    *,
    approved_by: str | None,
    name: str | None = None,
    lesson_id: str | None = None,
    skill_id: str | None = None,
    allow_incomplete: bool = False,
    now: datetime | None = None,
) -> ApprovalResult:
    """Approve a reviewed candidate into in-memory lesson and skill objects."""

    remaining = remaining_review_questions(candidate)
    if remaining and not allow_incomplete:
        raise IncompleteReviewError(candidate.id, remaining)

    moment = now or _utc_now()
    metadata = dict(candidate.metadata)
    approved = replace(
        candidate,
        status=LessonStatus.APPROVED,
        approved_by=approved_by,
        approved_at=moment,
        updated_at=moment,
        metadata=metadata,
    )
    title = name or approved.summary
    resolved_lesson_id = lesson_id or f"lesson-{approved.id}"
    resolved_skill_id = skill_id or f"skill-{approved.id}"
    lesson = lesson_from_candidate(approved, lesson_id=resolved_lesson_id, title=title, now=moment)
    skill = skill_from_candidate(
        approved,
        skill_id=resolved_skill_id,
        name=title,
        approved_by=approved_by,
        now=moment,
    )

    if remaining and allow_incomplete:
        override = {
            "unanswered_questions": remaining,
            "approved_by": approved_by,
            "approved_at": moment.isoformat(),
        }
        approved.metadata["incomplete_review_override"] = override
        skill.metadata["incomplete_review_override"] = override

    return ApprovalResult(candidate=approved, lesson=lesson, skill=skill)


def approve_and_save(
    registry: FileSystemRegistry,
    candidate: LessonCandidate,
    *,
    approved_by: str | None,
    name: str | None = None,
    lesson_id: str | None = None,
    skill_id: str | None = None,
    allow_incomplete: bool = False,
    now: datetime | None = None,
) -> ApprovalResult:
    """Approve a candidate and persist the resulting candidate, lesson, and skill."""

    result = approve_candidate(
        candidate,
        approved_by=approved_by,
        name=name,
        lesson_id=lesson_id,
        skill_id=skill_id,
        allow_incomplete=allow_incomplete,
        now=now,
    )
    registry.save_candidate(result.candidate)
    registry.save_lesson(result.lesson)
    registry.save_skill(result.skill)
    return result
