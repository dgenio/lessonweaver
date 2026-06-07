"""Cleanup workflow for stale, expired, noisy, and overlapping skills.

Reviewed skills are not trustworthy forever: they expire, stop loading, start
loading for the wrong tasks, or pile up overlapping guidance that poisons
context. This module aggregates the existing stale report, runtime usage
outcomes, and overlap/contradiction analysis into a single set of recommended
cleanup actions, and can optionally *apply* the safe subset (deprecating expired
skills) through the governed lifecycle. Nothing is changed unless the caller
explicitly applies the plan.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from .analysis import SkillAnalyzer
from .governance import can_promote_skill, promote_skill
from .models import SkillStatus, SkillUsageEvent
from .registry import FileSystemRegistry
from .reporting import SkillReporter

# A skill is "noisy" when, across at least this many graded usage events, the
# majority recorded a negative outcome — it is loading but not helping.
_MIN_GRADED_USAGE_FOR_NOISE = 2
_NEGATIVE_RATIO_THRESHOLD = 0.5

# Map a stale-report reason to a cleanup recommendation verb.
_STALE_RECOMMENDATION = {
    "expired": "retire",
    "deprecated": "retire",
    "low_confidence": "revise",
    "never_used": "revise",
}


@dataclass(slots=True)
class CleanupAction:
    """A recommended action for one skill. ``recommendation`` is keep/revise/expire/retire/narrow.

    ``plan`` emits only actionable findings; a skill with no findings is an
    implicit "keep". ``reason`` is a stable code; ``detail`` is human-readable.
    """

    skill_id: str
    reason: str
    recommendation: str
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "skill_id": self.skill_id,
            "reason": self.reason,
            "recommendation": self.recommendation,
            "detail": self.detail,
        }


class SkillCleaner:
    """Plan and optionally apply cleanup over a filesystem registry."""

    def plan(
        self, registry: FileSystemRegistry, now: datetime | None = None
    ) -> list[CleanupAction]:
        moment = now or datetime.now(timezone.utc)
        actions: list[CleanupAction] = []

        for report in SkillReporter().report_stale(registry, now=moment):
            actions.append(
                CleanupAction(
                    skill_id=report.skill_id,
                    reason=report.reason,
                    recommendation=_STALE_RECOMMENDATION.get(report.reason, "revise"),
                    detail=f"stale report: {report.reason} (recommended {report.recommendation})",
                )
            )

        usage_by_skill: dict[str, list[SkillUsageEvent]] = defaultdict(list)
        for event in registry.list_usage_events():
            usage_by_skill[event.skill_id].append(event)
        for skill in registry.list_skills():
            graded = [
                event
                for event in usage_by_skill.get(skill.id, [])
                if event.outcome_positive is not None
            ]
            if len(graded) < _MIN_GRADED_USAGE_FOR_NOISE:
                continue
            negatives = sum(1 for event in graded if event.outcome_positive is False)
            if negatives / len(graded) >= _NEGATIVE_RATIO_THRESHOLD:
                actions.append(
                    CleanupAction(
                        skill_id=skill.id,
                        reason="noisy",
                        recommendation="revise",
                        detail=f"{negatives}/{len(graded)} graded usages had a negative outcome",
                    )
                )

        for finding in SkillAnalyzer().analyze(registry.list_skills()):
            if finding.finding_type not in {"overlap", "contradiction"}:
                continue
            actions.append(
                CleanupAction(
                    skill_id=finding.skill_id_a,
                    reason=finding.finding_type,
                    recommendation="narrow",
                    detail=f"{finding.finding_type} with {finding.skill_id_b}: {finding.reason}",
                )
            )

        return actions

    def apply(
        self,
        registry: FileSystemRegistry,
        actions: list[CleanupAction],
        now: datetime | None = None,
    ) -> list[str]:
        """Apply the safe automated subset of ``actions`` and return changed skill ids.

        Only ``retire`` actions are automated, and only by deprecating a skill
        through the governed lifecycle (``ACTIVE``/``EXPERIMENTAL`` -> ``DEPRECATED``).
        Skills already deprecated, or in a state that does not permit the
        transition, are left untouched — everything else stays report-only.
        """
        retire_ids = {action.skill_id for action in actions if action.recommendation == "retire"}
        changed: list[str] = []
        for skill_id in sorted(retire_ids):
            skill = registry.load_skill(skill_id)
            if skill.status is SkillStatus.DEPRECATED:
                continue
            if not can_promote_skill(skill, SkillStatus.DEPRECATED):
                continue
            registry.save_skill(promote_skill(skill, SkillStatus.DEPRECATED))
            changed.append(skill_id)
        return changed
