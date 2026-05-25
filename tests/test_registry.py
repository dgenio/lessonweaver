"""Tests for the lesson/skill registry."""

from lessonweaver.models import LessonCandidate, RecommendedActionType, RiskLevel, Scope, SkillCard, SkillStatus
from lessonweaver.registry import LessonRegistry


def test_registry_add_and_get_lesson() -> None:
    registry = LessonRegistry()
    candidate = LessonCandidate(
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
    registry.add_lesson(candidate)
    assert registry.get_lesson("lesson-1") is candidate
    assert registry.get_lesson("nonexistent") is None


def test_registry_add_and_get_skill() -> None:
    registry = LessonRegistry()
    skill = SkillCard(
        id="skill-1",
        name="Test Skill",
        description="A test skill.",
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
    registry.add_skill(skill)
    assert registry.get_skill("skill-1") is skill
    assert registry.get_skill("nonexistent") is None
