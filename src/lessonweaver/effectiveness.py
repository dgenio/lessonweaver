"""Closed-loop effectiveness review for loaded skills."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import SkillCard, SkillUsageEvent, TraceBundle, TraceEventType

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
