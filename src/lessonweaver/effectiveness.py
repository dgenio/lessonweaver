"""Closed-loop effectiveness review and reports for activated skills."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from .models import SkillCard, SkillStatus, SkillUsageEvent, TraceBundle, TraceEventType
from .registry import FileSystemRegistry

_CAUSAL_UNCERTAINTY = (
    "usage outcomes are observational signals, not causal proof that the skill caused the result"
)
_TOKEN_RE = re.compile(r"[A-Za-z0-9_']+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "before",
    "for",
    "in",
    "is",
    "of",
    "or",
    "the",
    "this",
    "to",
    "with",
    "without",
}


def _tokens(value: str) -> set[str]:
    tokens: set[str] = set()
    for raw in _TOKEN_RE.findall(value.lower()):
        if raw in _STOPWORDS:
            continue
        tokens.add(raw)
        if raw == "pr":
            tokens.update({"pull", "request"})
        if raw.endswith("ing") and len(raw) > 5:
            tokens.add(raw[:-3])
        if raw.endswith("s") and len(raw) > 4:
            tokens.add(raw[:-1])
    return tokens


def _skill_context_tokens(skill: SkillCard) -> set[str]:
    chunks = [
        skill.name,
        skill.description,
        *skill.applies_when,
        *skill.instructions,
    ]
    return set().union(*(_tokens(chunk) for chunk in chunks))


def _skill_failure_tokens(skill: SkillCard) -> set[str]:
    chunks = [skill.description, *skill.anti_patterns, *skill.instructions]
    return set().union(*(_tokens(chunk) for chunk in chunks))


def _is_relevant_usage(skill_tokens: set[str], event: SkillUsageEvent) -> bool:
    return bool(skill_tokens & _tokens(event.task_context))


def _is_recurrence(skill_tokens: set[str], trace: TraceBundle) -> bool:
    trace_text = " ".join(
        [
            *[
                event.content or ""
                for event in trace.events
                if event.type
                in {
                    TraceEventType.HUMAN_CORRECTION,
                    TraceEventType.ERROR,
                    TraceEventType.EVALUATION_RESULT,
                }
            ],
        ]
    )
    return bool(skill_tokens & _tokens(trace_text))


def _clamp_score(value: float) -> float:
    return max(0.0, min(1.0, round(value, 2)))


@dataclass(slots=True)
class EffectivenessScorecard:
    """A deterministic summary of whether a skill appears to help after loading."""

    skill_id: str
    score: float
    recommendation: str
    loaded_relevant: int
    loaded_irrelevant: int
    positive_outcomes: int
    negative_outcomes: int
    recurrence_trace_ids: list[str]
    false_positive_examples: list[str]
    false_negative_examples: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "skill_id": self.skill_id,
            "score": self.score,
            "recommendation": self.recommendation,
            "loaded_relevant": self.loaded_relevant,
            "loaded_irrelevant": self.loaded_irrelevant,
            "positive_outcomes": self.positive_outcomes,
            "negative_outcomes": self.negative_outcomes,
            "recurrence_trace_ids": self.recurrence_trace_ids,
            "false_positive_examples": self.false_positive_examples,
            "false_negative_examples": self.false_negative_examples,
        }


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


class SkillEffectivenessReviewer:
    """Score a reviewed skill against usage logs and later failure traces."""

    def review(
        self,
        skill: SkillCard,
        *,
        usage_events: list[SkillUsageEvent],
        post_activation_traces: list[TraceBundle],
    ) -> EffectivenessScorecard:
        skill_context = _skill_context_tokens(skill)
        skill_failures = _skill_failure_tokens(skill)
        relevant_usage = [
            event for event in usage_events if _is_relevant_usage(skill_context, event)
        ]
        irrelevant_usage = [
            event for event in usage_events if not _is_relevant_usage(skill_context, event)
        ]
        positive_outcomes = sum(1 for event in usage_events if event.outcome_positive is True)
        negative_outcomes = sum(1 for event in usage_events if event.outcome_positive is False)
        recurrence_trace_ids = [
            trace.trace_id
            for trace in post_activation_traces
            if _is_recurrence(skill_failures, trace)
        ]
        false_positive_examples = [event.id for event in irrelevant_usage]
        false_negative_examples = list(recurrence_trace_ids)

        score = _clamp_score(
            0.5
            + (0.2 * positive_outcomes)
            - (0.1 * negative_outcomes)
            - (0.2 * len(false_positive_examples))
            - (0.4 * len(recurrence_trace_ids))
        )

        if recurrence_trace_ids:
            recommendation = "revise"
        elif false_positive_examples:
            recommendation = "narrow_scope"
        elif relevant_usage and positive_outcomes:
            recommendation = "keep"
        else:
            recommendation = "review"

        return EffectivenessScorecard(
            skill_id=skill.id,
            score=score,
            recommendation=recommendation,
            loaded_relevant=len(relevant_usage),
            loaded_irrelevant=len(irrelevant_usage),
            positive_outcomes=positive_outcomes,
            negative_outcomes=negative_outcomes,
            recurrence_trace_ids=recurrence_trace_ids,
            false_positive_examples=false_positive_examples,
            false_negative_examples=false_negative_examples,
        )


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
            usage = sorted(
                (
                    event
                    for event in usage_by_skill.get(skill.id, [])
                    if event.skill_version == skill.version
                ),
                key=lambda event: event.loaded_at,
            )
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
    return "insufficient_evidence", "review"


def _mentions_regression(event: SkillUsageEvent) -> bool:
    text = " ".join(part for part in [event.outcome, event.notes] if part)
    return "regression" in text.lower()
