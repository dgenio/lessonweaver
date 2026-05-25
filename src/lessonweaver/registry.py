"""Simple in-memory registry for reviewed lessons and generated skills."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import LessonCandidate, SkillCard


@dataclass(slots=True)
class LessonRegistry:
    lessons: dict[str, LessonCandidate] = field(default_factory=dict)
    skills: dict[str, SkillCard] = field(default_factory=dict)

    def add_lesson(self, candidate: LessonCandidate) -> None:
        self.lessons[candidate.id] = candidate

    def add_skill(self, skill: SkillCard) -> None:
        self.skills[skill.id] = skill

    def get_lesson(self, lesson_id: str) -> LessonCandidate | None:
        return self.lessons.get(lesson_id)

    def get_skill(self, skill_id: str) -> SkillCard | None:
        return self.skills.get(skill_id)
