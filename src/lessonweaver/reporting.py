"""Stale and unused skill detection over a filesystem registry."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from .models import SkillStatus, SkillUsageEvent, StaleSkillReport
from .registry import FileSystemRegistry

_LOW_CONFIDENCE_THRESHOLD = 0.3


class SkillReporter:
    """Inspect a registry and report skills that need attention.

    Reports only; nothing is deleted or deprecated automatically. A single
    skill may produce more than one report when it matches several reasons
    (for example, both expired and never used).
    """

    def report_stale(
        self,
        registry: FileSystemRegistry,
        now: datetime | None = None,
    ) -> list[StaleSkillReport]:
        """Return findings for expired, deprecated, low-confidence, or unused skills.

        ``now`` is injectable so time-based checks are deterministic in tests;
        it defaults to the current UTC time.
        """
        moment = now or datetime.now(timezone.utc)
        reports: list[StaleSkillReport] = []

        # Load the usage log once and group it by skill id in memory. Calling
        # ``registry.list_skill_usage`` per skill would re-scan and re-parse the
        # entire usage directory for every skill (O(skills * events) reads),
        # which degrades as the usage log accumulates over time.
        usage_by_skill: dict[str, list[SkillUsageEvent]] = defaultdict(list)
        for event in registry.list_usage_events():
            usage_by_skill[event.skill_id].append(event)

        for skill in registry.list_skills():
            usage = usage_by_skill.get(skill.id, [])
            last_used_at = max((event.loaded_at for event in usage), default=None)

            if skill.expires_at is not None and skill.expires_at <= moment:
                reports.append(
                    StaleSkillReport(
                        skill_id=skill.id,
                        reason="expired",
                        recommendation="revalidate",
                        last_used_at=last_used_at,
                        expires_at=skill.expires_at,
                        rollout_status=skill.rollout.status,
                        review_date=skill.rollout.review_date,
                    )
                )
            if skill.status is SkillStatus.DEPRECATED:
                reports.append(
                    StaleSkillReport(
                        skill_id=skill.id,
                        reason="deprecated",
                        recommendation="remove",
                        last_used_at=last_used_at,
                        expires_at=skill.expires_at,
                        rollout_status=skill.rollout.status,
                        review_date=skill.rollout.review_date,
                    )
                )
            if skill.confidence < _LOW_CONFIDENCE_THRESHOLD:
                reports.append(
                    StaleSkillReport(
                        skill_id=skill.id,
                        reason="low_confidence",
                        recommendation="revalidate",
                        last_used_at=last_used_at,
                        expires_at=skill.expires_at,
                        rollout_status=skill.rollout.status,
                        review_date=skill.rollout.review_date,
                    )
                )
            if not usage:
                reports.append(
                    StaleSkillReport(
                        skill_id=skill.id,
                        reason="never_used",
                        recommendation="revalidate",
                        last_used_at=None,
                        expires_at=skill.expires_at,
                        rollout_status=skill.rollout.status,
                        review_date=skill.rollout.review_date,
                    )
                )
        return reports
