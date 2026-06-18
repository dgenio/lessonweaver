"""Governed lifecycle transitions for lessonweaver skills."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from .lint import LintSeverity, SkillLinter
from .models import RolloutEnvironment, RolloutStatus, SkillCard, SkillStatus

_ALLOWED_SKILL_TRANSITIONS: dict[SkillStatus, set[SkillStatus]] = {
    SkillStatus.DRAFT: {SkillStatus.APPROVED},
    SkillStatus.APPROVED: {SkillStatus.EXPERIMENTAL, SkillStatus.REJECTED},
    SkillStatus.EXPERIMENTAL: {SkillStatus.ACTIVE, SkillStatus.DEPRECATED},
    SkillStatus.ACTIVE: {SkillStatus.DEPRECATED},
    SkillStatus.REJECTED: set(),
    SkillStatus.DEPRECATED: set(),
}

_ALLOWED_ROLLOUT_TRANSITIONS: dict[RolloutStatus, set[RolloutStatus]] = {
    RolloutStatus.DRAFT: {RolloutStatus.APPROVED, RolloutStatus.CANARY},
    RolloutStatus.APPROVED: {RolloutStatus.CANARY, RolloutStatus.ACTIVE, RolloutStatus.PAUSED},
    RolloutStatus.CANARY: {RolloutStatus.ACTIVE, RolloutStatus.PAUSED, RolloutStatus.RETIRED},
    RolloutStatus.ACTIVE: {RolloutStatus.PAUSED, RolloutStatus.RETIRED},
    RolloutStatus.PAUSED: {RolloutStatus.CANARY, RolloutStatus.ACTIVE, RolloutStatus.RETIRED},
    RolloutStatus.RETIRED: set(),
}


def can_promote_skill(skill: SkillCard, target: SkillStatus) -> bool:
    if target not in _ALLOWED_SKILL_TRANSITIONS[skill.status]:
        return False
    if target is SkillStatus.ACTIVE:
        proposed = replace(skill, status=target)
        return not any(
            finding.severity is LintSeverity.ERROR for finding in SkillLinter().lint(proposed)
        )
    return True


def promote_skill(skill: SkillCard, target: SkillStatus) -> SkillCard:
    if target not in _ALLOWED_SKILL_TRANSITIONS[skill.status]:
        raise ValueError(f"cannot promote skill from {skill.status.value} to {target.value}")

    now = datetime.now(timezone.utc)
    promoted = replace(skill, status=target, updated_at=now)

    if target is SkillStatus.ACTIVE:
        blocking = [
            finding
            for finding in SkillLinter().lint(promoted)
            if finding.severity is LintSeverity.ERROR
        ]
        if blocking:
            rules = ", ".join(finding.rule_id for finding in blocking)
            raise ValueError(f"cannot promote skill to active with blocking lint findings: {rules}")

    return promoted


def update_rollout_metadata(
    skill: SkillCard,
    *,
    target_agents: list[str] | None = None,
    target_versions: list[str] | None = None,
    environment: RolloutEnvironment | None = None,
    status: RolloutStatus | None = None,
    percentage: int | None = None,
    cohort: str | None = None,
    owner: str | None = None,
    approver: str | None = None,
    activation_date: datetime | None = None,
    review_date: datetime | None = None,
    expiry_date: datetime | None = None,
    rollback_instructions: str | None = None,
    linked_eval_suite: str | None = None,
    monitoring_window_days: int | None = None,
) -> SkillCard:
    """Return ``skill`` with governed rollout/canary metadata updates applied."""
    current = skill.rollout
    next_status = status or current.status
    if (
        next_status is not current.status
        and next_status not in _ALLOWED_ROLLOUT_TRANSITIONS[current.status]
    ):
        raise ValueError(f"cannot move rollout from {current.status.value} to {next_status.value}")
    if percentage is not None and not 0 <= percentage <= 100:
        raise ValueError("rollout percentage must be between 0 and 100")
    if monitoring_window_days is not None and monitoring_window_days < 0:
        raise ValueError("monitoring window must be non-negative")

    rollout = replace(
        current,
        target_agents=list(target_agents) if target_agents is not None else current.target_agents,
        target_versions=(
            list(target_versions) if target_versions is not None else current.target_versions
        ),
        environment=environment or current.environment,
        status=next_status,
        percentage=percentage if percentage is not None else current.percentage,
        cohort=cohort if cohort is not None else current.cohort,
        owner=owner if owner is not None else current.owner,
        approver=approver if approver is not None else current.approver,
        activation_date=(
            activation_date if activation_date is not None else current.activation_date
        ),
        review_date=review_date if review_date is not None else current.review_date,
        expiry_date=expiry_date if expiry_date is not None else current.expiry_date,
        rollback_instructions=(
            rollback_instructions
            if rollback_instructions is not None
            else current.rollback_instructions
        ),
        linked_eval_suite=(
            linked_eval_suite if linked_eval_suite is not None else current.linked_eval_suite
        ),
        monitoring_window_days=(
            monitoring_window_days
            if monitoring_window_days is not None
            else current.monitoring_window_days
        ),
    )
    return replace(skill, rollout=rollout, updated_at=datetime.now(timezone.utc))
