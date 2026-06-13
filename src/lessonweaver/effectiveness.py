"""Closed-loop effectiveness reports for activated skills."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from .models import SkillStatus, SkillUsageEvent
from .registry import FileSystemRegistry

_CAUSAL_UNCERTAINTY = (
    "usage outcomes are observational signals, not causal proof that the skill caused the result"
)


@dataclass(frozen=True, slots=True)
class SkillEffectivenessReport:
    skill_id: str
    skill_version: str
    signal: str
    recommendation: str
    total_usages: int
    positive_outcomes: int
    negative_outcomes: int
    ungraded_outcomes: int
    evidence_event_ids: list[str]
    last_used_at: datetime | None
    causal_uncertainty: str = _CAUSAL_UNCERTAINTY

    def to_dict(self) -> dict[str, object]:
        return {
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "signal": self.signal,
            "recommendation": self.recommendation,
            "total_usages": self.total_usages,
            "positive_outcomes": self.positive_outcomes,
            "negative_outcomes": self.negative_outcomes,
            "ungraded_outcomes": self.ungraded_outcomes,
            "evidence_event_ids": list(self.evidence_event_ids),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "causal_uncertainty": self.causal_uncertainty,
        }


class SkillEffectivenessReporter:
    """Aggregate usage evidence into conservative closed-loop recommendations."""

    def report(
        self,
        registry: FileSystemRegistry,
        *,
        now: datetime | None = None,
    ) -> list[SkillEffectivenessReport]:
        del now
        usage_by_skill: dict[str, list[SkillUsageEvent]] = defaultdict(list)
        for event in registry.list_usage_events():
            usage_by_skill[event.skill_id].append(event)

        reports: list[SkillEffectivenessReport] = []
        for skill in registry.list_skills():
            if skill.status is not SkillStatus.ACTIVE:
                continue
            usage = sorted(usage_by_skill.get(skill.id, []), key=lambda event: event.loaded_at)
            reports.append(
                _build_report(
                    skill_id=skill.id,
                    skill_version=skill.version,
                    usage=usage,
                )
            )
        return reports


def _build_report(
    *,
    skill_id: str,
    skill_version: str,
    usage: list[SkillUsageEvent],
) -> SkillEffectivenessReport:
    positives = [event for event in usage if event.outcome_positive is True]
    negatives = [event for event in usage if event.outcome_positive is False]
    ungraded = [event for event in usage if event.outcome_positive is None]
    last_used_at = max((event.loaded_at for event in usage), default=None)

    signal, recommendation = _classify(usage, positives, negatives)
    return SkillEffectivenessReport(
        skill_id=skill_id,
        skill_version=skill_version,
        signal=signal,
        recommendation=recommendation,
        total_usages=len(usage),
        positive_outcomes=len(positives),
        negative_outcomes=len(negatives),
        ungraded_outcomes=len(ungraded),
        evidence_event_ids=[event.id for event in usage],
        last_used_at=last_used_at,
    )


def _classify(
    usage: list[SkillUsageEvent],
    positives: list[SkillUsageEvent],
    negatives: list[SkillUsageEvent],
) -> tuple[str, str]:
    if not usage:
        return "staleness", "review"
    if any(_mentions_regression(event) for event in negatives):
        return "possible_regression", "deprecate_or_revise"
    if len(negatives) >= 2:
        return "repeated_failure", "revise"
    if len(positives) >= 2 and not negatives:
        return "improvement", "keep"
    if len(positives) > len(negatives):
        return "improvement", "keep"
    if negatives:
        return "repeated_failure", "revise"
    return "insufficient_evidence", "review"


def _mentions_regression(event: SkillUsageEvent) -> bool:
    text = " ".join(part for part in [event.outcome, event.notes] if part)
    return "regression" in text.lower()
