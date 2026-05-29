"""Stale and unused skill detection over a filesystem registry."""

from __future__ import annotations

from datetime import datetime, timezone

from .models import SkillStatus, StaleSkillReport
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
        for skill in registry.list_skills():
            usage = registry.list_skill_usage(skill.id)
            last_used_at = max((event.loaded_at for event in usage), default=None)

            if skill.expires_at is not None and skill.expires_at <= moment:
                reports.append(
                    StaleSkillReport(
                        skill_id=skill.id,
                        reason="expired",
                        recommendation="revalidate",
                        last_used_at=last_used_at,
                        expires_at=skill.expires_at,
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
                    )
                )
        return reports
