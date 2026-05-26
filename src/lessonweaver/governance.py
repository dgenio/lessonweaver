"""Governed lifecycle transitions for lessonweaver skills."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from .lint import LintSeverity, SkillLinter
from .models import SkillCard, SkillStatus

_ALLOWED_SKILL_TRANSITIONS: dict[SkillStatus, set[SkillStatus]] = {
    SkillStatus.DRAFT: {SkillStatus.APPROVED},
    SkillStatus.APPROVED: {SkillStatus.EXPERIMENTAL, SkillStatus.REJECTED},
    SkillStatus.EXPERIMENTAL: {SkillStatus.ACTIVE, SkillStatus.DEPRECATED},
    SkillStatus.ACTIVE: {SkillStatus.DEPRECATED},
    SkillStatus.REJECTED: set(),
    SkillStatus.DEPRECATED: set(),
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
