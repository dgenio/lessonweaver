"""Tests for the stale/noisy/overlapping skill cleanup workflow."""

from datetime import datetime, timezone

from lessonweaver.cleanup import SkillCleaner
from lessonweaver.models import (
    RiskLevel,
    Scope,
    SkillCard,
    SkillStatus,
    SkillUsageEvent,
)
from lessonweaver.registry import FileSystemRegistry

_PAST = datetime(2020, 1, 1, tzinfo=timezone.utc)
_NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)


def _skill(
    skill_id: str,
    *,
    applies_when: list[str],
    status: SkillStatus = SkillStatus.ACTIVE,
    confidence: float = 0.8,
    expires_at: datetime | None = None,
) -> SkillCard:
    return SkillCard(
        id=skill_id,
        name=skill_id,
        description=f"Guidance for {applies_when[0]}.",
        applies_when=applies_when,
        does_not_apply_when=["unrelated tasks"],
        instructions=[f"Handle {applies_when[0]} carefully"],
        anti_patterns=["skipping the check"],
        evidence_trace_ids=["trace-1"],
        confidence=confidence,
        risk_level=RiskLevel.LOW,
        scope=Scope.PROJECT,
        version="0.2.0",
        status=status,
        expires_at=expires_at,
    )


def _usage(
    skill_id: str, event_id: str, *, outcome_positive: bool | None = None
) -> SkillUsageEvent:
    return SkillUsageEvent(
        id=event_id,
        skill_id=skill_id,
        skill_version="0.2.0",
        task_context="ran",
        outcome_positive=outcome_positive,
    )


def _actions_by_skill(actions) -> dict[str, set[tuple[str, str]]]:
    grouped: dict[str, set[tuple[str, str]]] = {}
    for action in actions:
        grouped.setdefault(action.skill_id, set()).add((action.reason, action.recommendation))
    return grouped


def test_plan_covers_expired_unused_noisy_overlap_and_keeps_useful(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(
        _skill("expired-1", applies_when=["handling refund requests"], expires_at=_PAST)
    )
    registry.save_usage_event(_usage("expired-1", "u-exp"))
    registry.save_skill(_skill("unused-1", applies_when=["writing database migrations"]))
    registry.save_skill(_skill("noisy-1", applies_when=["formatting commit messages"]))
    registry.save_usage_event(_usage("noisy-1", "u-n1", outcome_positive=False))
    registry.save_usage_event(_usage("noisy-1", "u-n2", outcome_positive=False))
    registry.save_skill(_skill("ovl-a", applies_when=["deploying kubernetes manifests"]))
    registry.save_usage_event(_usage("ovl-a", "u-a"))
    registry.save_skill(_skill("ovl-b", applies_when=["deploying kubernetes manifests"]))
    registry.save_usage_event(_usage("ovl-b", "u-b"))
    registry.save_skill(_skill("useful-1", applies_when=["reviewing terraform plans"]))
    registry.save_usage_event(_usage("useful-1", "u-use", outcome_positive=True))

    grouped = _actions_by_skill(SkillCleaner().plan(registry, now=_NOW))

    assert ("expired", "retire") in grouped["expired-1"]
    assert ("never_used", "revise") in grouped["unused-1"]
    assert ("noisy", "revise") in grouped["noisy-1"]
    assert ("overlap", "narrow") in grouped["ovl-a"]
    assert "useful-1" not in grouped


def test_apply_deprecates_expired_active_skill_and_is_idempotent(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill("exp", applies_when=["handling refunds"], expires_at=_PAST))
    registry.save_usage_event(_usage("exp", "u-exp"))

    cleaner = SkillCleaner()
    actions = cleaner.plan(registry, now=_NOW)
    changed = cleaner.apply(registry, actions, now=_NOW)
    assert changed == ["exp"]
    assert registry.load_skill("exp").status is SkillStatus.DEPRECATED

    # Re-running finds nothing left to deprecate (the skill is already deprecated).
    again = cleaner.apply(registry, cleaner.plan(registry, now=_NOW), now=_NOW)
    assert again == []


def test_apply_does_not_deprecate_revise_only_findings(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill("unused-1", applies_when=["writing database migrations"]))

    cleaner = SkillCleaner()
    actions = cleaner.plan(registry, now=_NOW)
    assert cleaner.apply(registry, actions, now=_NOW) == []
    assert registry.load_skill("unused-1").status is SkillStatus.ACTIVE
