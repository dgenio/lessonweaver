from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lessonweaver.models import (
    RecommendedActionType,
    RiskLevel,
    Scope,
    SensitivityLevel,
    SkillCard,
    SkillStatus,
)
from lessonweaver.promotion_policy import (
    PromotionPolicy,
    apply_promotion_decision,
    evaluate_promotion,
)

NOW = datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc)


def _skill(
    *,
    confidence: float = 0.86,
    evidence_trace_ids: list[str] | None = None,
    risk_level: RiskLevel = RiskLevel.LOW,
    scope: Scope = Scope.PROJECT,
    sensitivity: SensitivityLevel = SensitivityLevel.INTERNAL,
    status: SkillStatus = SkillStatus.APPROVED,
    metadata: dict[str, object] | None = None,
) -> SkillCard:
    return SkillCard(
        id="skill-policy-check",
        name="Policy Check",
        description="Check policy before promoting a reviewed lesson.",
        applies_when=["Promoting reviewed lessons"],
        does_not_apply_when=["No promotion is being considered"],
        instructions=["Evaluate the promotion policy before changing status."],
        anti_patterns=["Activating broad guidance without review"],
        evidence_trace_ids=evidence_trace_ids or ["trace-1", "trace-2"],
        confidence=confidence,
        risk_level=risk_level,
        scope=scope,
        version="0.1.0",
        status=status,
        sensitivity=sensitivity,
        approved_by="reviewer",
        created_at=NOW,
        updated_at=NOW,
        metadata=metadata or {},
    )


def test_low_risk_skill_can_be_dry_run_promoted_with_audit_and_rollback() -> None:
    decision = evaluate_promotion(_skill(), PromotionPolicy())

    assert decision.allowed is True
    assert decision.requires_human_review is False
    assert decision.dry_run is True
    assert decision.target_status is SkillStatus.EXPERIMENTAL
    assert decision.rollback_status is SkillStatus.APPROVED
    assert decision.skill_id == "skill-policy-check"
    assert any("confidence" in entry for entry in decision.audit)
    assert decision.to_dict() == {
        "allowed": True,
        "requires_human_review": False,
        "target_status": "experimental",
        "reason": "policy permits low-risk dry-run promotion",
        "audit": decision.audit,
        "rollback_status": "approved",
        "dry_run": True,
        "skill_id": "skill-policy-check",
    }


@pytest.mark.parametrize(
    ("skill", "reason_fragment"),
    [
        (_skill(risk_level=RiskLevel.HIGH), "risk"),
        (_skill(scope=Scope.GLOBAL), "scope"),
        (_skill(sensitivity=SensitivityLevel.CONFIDENTIAL), "sensitivity"),
        (_skill(confidence=0.6), "confidence"),
        (_skill(evidence_trace_ids=["trace-1"]), "evidence"),
    ],
)
def test_policy_forces_human_review_for_unsafe_promotion_inputs(
    skill: SkillCard, reason_fragment: str
) -> None:
    decision = evaluate_promotion(skill, PromotionPolicy())

    assert decision.allowed is False
    assert decision.requires_human_review is True
    assert reason_fragment in decision.reason
    assert any(reason_fragment in entry for entry in decision.audit)


def test_policy_forces_human_review_for_conflicts_and_disallowed_actions() -> None:
    action_decision = evaluate_promotion(
        _skill(),
        PromotionPolicy(),
        action_type=RecommendedActionType.WORKFLOW_CHANGE,
    )
    conflict_decision = evaluate_promotion(
        _skill(),
        PromotionPolicy(),
        conflicts=["existing active lesson gives opposite guidance"],
    )

    assert action_decision.allowed is False
    assert action_decision.requires_human_review is True
    assert "action_type" in action_decision.reason
    assert conflict_decision.allowed is False
    assert conflict_decision.requires_human_review is True
    assert "conflicts" in conflict_decision.reason


def test_active_promotion_requires_explicit_policy_permission() -> None:
    decision = evaluate_promotion(
        _skill(status=SkillStatus.EXPERIMENTAL),
        PromotionPolicy(),
        target_status=SkillStatus.ACTIVE,
    )

    assert decision.allowed is False
    assert decision.requires_human_review is True
    assert "active" in decision.reason


def test_apply_promotion_records_auditable_reversible_metadata() -> None:
    skill = _skill()
    decision = evaluate_promotion(skill, PromotionPolicy(), dry_run=False)

    promoted = apply_promotion_decision(skill, decision)

    assert promoted.status is SkillStatus.EXPERIMENTAL
    assert promoted.metadata["promotion_decision"]["allowed"] is True
    assert promoted.metadata["promotion_decision"]["rollback_status"] == "approved"
    assert promoted.metadata["promotion_rollback_status"] == "approved"


def test_apply_dry_run_or_blocked_decision_does_not_change_skill() -> None:
    skill = _skill()
    dry_run_decision = evaluate_promotion(skill, PromotionPolicy())
    blocked_decision = evaluate_promotion(_skill(risk_level=RiskLevel.HIGH), PromotionPolicy())

    assert apply_promotion_decision(skill, dry_run_decision) == skill
    with pytest.raises(ValueError, match="blocked by policy"):
        apply_promotion_decision(skill, blocked_decision)
