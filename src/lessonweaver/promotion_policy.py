"""Policy-gated promotion decisions for reviewed skills."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from .governance import can_promote_skill, promote_skill
from .models import (
    RecommendedActionType,
    RiskLevel,
    Scope,
    SensitivityLevel,
    SkillCard,
    SkillStatus,
)

_RISK_ORDER: dict[RiskLevel, int] = {
    RiskLevel.LOW: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.HIGH: 3,
}


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    """Auditable result of evaluating a skill promotion request."""

    allowed: bool
    target_status: SkillStatus
    reason: str
    requires_human_review: bool
    audit: list[str]
    rollback_status: SkillStatus | None
    dry_run: bool
    skill_id: str

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "requires_human_review": self.requires_human_review,
            "target_status": self.target_status.value,
            "reason": self.reason,
            "audit": list(self.audit),
            "rollback_status": self.rollback_status.value if self.rollback_status else None,
            "dry_run": self.dry_run,
            "skill_id": self.skill_id,
        }


@dataclass(frozen=True, slots=True)
class PromotionPolicy:
    """Thresholds for automatic, governed skill promotion."""

    min_confidence: float = 0.75
    min_evidence_traces: int = 2
    max_auto_risk: RiskLevel = RiskLevel.LOW
    allowed_scopes: tuple[Scope, ...] = (Scope.USER, Scope.PROJECT, Scope.TEAM)
    allowed_action_types: tuple[RecommendedActionType, ...] = (RecommendedActionType.SKILL,)
    blocked_sensitivities: tuple[SensitivityLevel, ...] = (
        SensitivityLevel.CONFIDENTIAL,
        SensitivityLevel.RESTRICTED,
    )
    allow_auto_activate: bool = False
    review_reasons: tuple[str, ...] = field(default_factory=tuple)


def evaluate_promotion(
    skill: SkillCard,
    policy: PromotionPolicy,
    *,
    target_status: SkillStatus = SkillStatus.EXPERIMENTAL,
    action_type: RecommendedActionType | str | None = None,
    conflicts: list[str] | None = None,
    dry_run: bool = True,
) -> PromotionDecision:
    """Return an auditable policy decision without mutating the skill."""

    action = _resolve_action_type(skill, action_type)
    conflict_list = conflicts or []
    audit = [
        f"confidence {skill.confidence:.2f} >= {policy.min_confidence:.2f}",
        f"evidence {len(skill.evidence_trace_ids)} >= {policy.min_evidence_traces}",
        f"risk {skill.risk_level.value} <= {policy.max_auto_risk.value}",
        f"scope {skill.scope.value} in {[scope.value for scope in policy.allowed_scopes]}",
        f"sensitivity {skill.sensitivity.value} not blocked",
        f"action_type {action.value} allowed",
        f"target_status {target_status.value}",
        f"conflicts {len(conflict_list)}",
    ]

    blocking_reason = _first_blocking_reason(
        skill=skill,
        policy=policy,
        target_status=target_status,
        action_type=action,
        conflicts=conflict_list,
    )
    if blocking_reason:
        audit.append(blocking_reason)
        return PromotionDecision(
            allowed=False,
            target_status=target_status,
            reason=blocking_reason,
            requires_human_review=True,
            audit=audit,
            rollback_status=skill.status,
            dry_run=dry_run,
            skill_id=skill.id,
        )

    return PromotionDecision(
        allowed=True,
        target_status=target_status,
        reason=(
            "policy permits low-risk dry-run promotion"
            if dry_run
            else "policy permits low-risk promotion"
        ),
        requires_human_review=False,
        audit=audit,
        rollback_status=skill.status,
        dry_run=dry_run,
        skill_id=skill.id,
    )


def apply_promotion_decision(skill: SkillCard, decision: PromotionDecision) -> SkillCard:
    """Apply a non-dry-run allowed decision and record rollback metadata."""

    if not decision.allowed:
        raise ValueError(f"promotion blocked by policy: {decision.reason}")
    if decision.dry_run:
        return skill

    promoted = promote_skill(skill, decision.target_status)
    metadata = dict(promoted.metadata)
    metadata["promotion_decision"] = decision.to_dict()
    metadata["promotion_rollback_status"] = (
        decision.rollback_status.value if decision.rollback_status else None
    )
    return replace(promoted, metadata=metadata)


def _resolve_action_type(
    skill: SkillCard, action_type: RecommendedActionType | str | None
) -> RecommendedActionType:
    if action_type is None:
        raw_action = skill.metadata.get(
            "recommended_action_type", RecommendedActionType.SKILL.value
        )
        return RecommendedActionType(str(raw_action))
    if isinstance(action_type, RecommendedActionType):
        return action_type
    return RecommendedActionType(str(action_type))


def _first_blocking_reason(
    *,
    skill: SkillCard,
    policy: PromotionPolicy,
    target_status: SkillStatus,
    action_type: RecommendedActionType,
    conflicts: list[str],
) -> str | None:
    if target_status is SkillStatus.ACTIVE and not policy.allow_auto_activate:
        return "active target requires explicit policy permission and human review"
    if not can_promote_skill(skill, target_status):
        return "lifecycle transition requires human review"
    if _RISK_ORDER[skill.risk_level] > _RISK_ORDER[policy.max_auto_risk]:
        return "risk exceeds automatic promotion policy"
    if skill.scope not in policy.allowed_scopes:
        return "scope requires human review"
    if skill.sensitivity in policy.blocked_sensitivities:
        return "sensitivity requires human review"
    if skill.confidence < policy.min_confidence:
        return "confidence is below automatic promotion policy"
    if len(skill.evidence_trace_ids) < policy.min_evidence_traces:
        return "evidence count is below automatic promotion policy"
    if action_type not in policy.allowed_action_types:
        return "action_type requires human review"
    if conflicts:
        return "conflicts require human review"
    if policy.review_reasons:
        return "configured review reasons require human review"
    return None
