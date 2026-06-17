"""Agent improvement inbox for telemetry-derived lesson candidates."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .clustering import LessonCluster, LessonClusterer
from .models import LessonCandidate, LessonStatus, RecommendedActionType, RiskLevel, Scope
from .registry import FileSystemRegistry

REVIEW_ACTIONS = ["approve", "reject", "defer", "create_issue"]
_OPEN_CANDIDATE_STATUSES = {LessonStatus.CANDIDATE, LessonStatus.NEEDS_REVIEW}

_RISK_RANK = {
    RiskLevel.HIGH: 3,
    RiskLevel.MEDIUM: 2,
    RiskLevel.LOW: 1,
}


@dataclass(slots=True)
class AgentImprovementInboxItem:
    """One review item grouping a recurring failure pattern."""

    item_id: str
    title: str
    candidate_ids: list[str]
    affected_agents: list[str]
    affected_versions: list[str]
    evidence_trace_ids: list[str]
    representative_examples: list[str]
    frequency: int
    trend: str
    outcome_labels: list[str]
    failure_mode: str
    recommended_action_type: RecommendedActionType
    risk_level: RiskLevel
    suggested_scope: Scope
    recommendation_rationale: str
    suggested_eval_plan: str
    suggested_rollout_plan: str
    review_actions: list[str] = field(default_factory=lambda: list(REVIEW_ACTIONS))

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "title": self.title,
            "candidate_ids": self.candidate_ids,
            "affected_agents": self.affected_agents,
            "affected_versions": self.affected_versions,
            "evidence_trace_ids": self.evidence_trace_ids,
            "representative_examples": self.representative_examples,
            "frequency": self.frequency,
            "trend": self.trend,
            "outcome_labels": self.outcome_labels,
            "failure_mode": self.failure_mode,
            "recommended_action_type": self.recommended_action_type.value,
            "risk_level": self.risk_level.value,
            "suggested_scope": self.suggested_scope.value,
            "recommendation_rationale": self.recommendation_rationale,
            "suggested_eval_plan": self.suggested_eval_plan,
            "suggested_rollout_plan": self.suggested_rollout_plan,
            "review_actions": self.review_actions,
        }


@dataclass(slots=True)
class AgentImprovementInbox:
    """A deterministic review inbox for agent owners."""

    items: list[AgentImprovementInboxItem]

    def to_dict(self) -> dict[str, Any]:
        return {"items": [item.to_dict() for item in self.items]}

    def to_markdown(self) -> str:
        lines = ["# Agent improvement inbox"]
        if not self.items:
            lines.append("")
            lines.append("No improvement candidates match the current filters.")
            return "\n".join(lines)

        for index, item in enumerate(self.items, start=1):
            lines.extend(
                [
                    "",
                    f"## {index}. {item.title}",
                    f"- Frequency: {item.frequency}",
                    f"- Trend: {item.trend}",
                    f"- Affected agents: {', '.join(item.affected_agents) or 'unknown'}",
                    f"- Affected versions: {', '.join(item.affected_versions) or 'unknown'}",
                    f"- Failure mode: {item.failure_mode}",
                    f"- Outcome labels: {', '.join(item.outcome_labels) or 'unknown'}",
                    f"- Recommended artifact: {item.recommended_action_type.value}",
                    f"- Risk: {item.risk_level.value}",
                    f"- Suggested scope: {item.suggested_scope.value}",
                    f"- Evidence traces: {', '.join(item.evidence_trace_ids)}",
                    f"- Rationale: {item.recommendation_rationale}",
                    f"- Eval plan: {item.suggested_eval_plan}",
                    f"- Rollout plan: {item.suggested_rollout_plan}",
                    f"- Actions: {', '.join(item.review_actions)}",
                ]
            )
        return "\n".join(lines)


class AgentImprovementInboxBuilder:
    """Build grouped improvement inbox items from telemetry-derived candidates."""

    def __init__(
        self,
        *,
        min_frequency: int = 1,
        clusterer: LessonClusterer | None = None,
    ) -> None:
        if min_frequency < 1:
            raise ValueError("min_frequency must be at least 1")
        self.min_frequency = min_frequency
        self.clusterer = clusterer or LessonClusterer()

    def build(self, candidates: list[LessonCandidate]) -> AgentImprovementInbox:
        open_candidates = [
            candidate for candidate in candidates if candidate.status in _OPEN_CANDIDATE_STATUSES
        ]
        clusters = self.clusterer.cluster(open_candidates)
        items = [
            _item_from_cluster(cluster)
            for cluster in clusters
            if cluster.occurrence_count >= self.min_frequency
        ]
        items.sort(
            key=lambda item: (
                -_RISK_RANK[item.risk_level],
                -item.frequency,
                item.title,
                item.item_id,
            )
        )
        return AgentImprovementInbox(items)


def record_improvement_inbox_action(
    registry: FileSystemRegistry,
    candidate_ids: list[str],
    action: str,
    *,
    reviewer: str,
    note: str = "",
) -> None:
    """Record a reviewer action for one or more inbox candidates in the registry."""
    if action not in REVIEW_ACTIONS:
        raise ValueError(f"unknown improvement inbox action: {action}")

    for candidate_id in candidate_ids:
        candidate = registry.load_candidate(candidate_id)
        if action == "approve":
            candidate.status = LessonStatus.APPROVED
        elif action == "reject":
            candidate.status = LessonStatus.REJECTED
        elif action in {"defer", "create_issue"}:
            candidate.status = LessonStatus.NEEDS_REVIEW

        candidate.metadata["improvement_inbox"] = {
            "action": action,
            "reviewer": reviewer,
            "note": note,
        }
        registry.save_candidate(candidate)


def _item_from_cluster(cluster: LessonCluster) -> AgentImprovementInboxItem:
    members = cluster.members
    representative = cluster.representative
    frequency = cluster.occurrence_count
    evidence_trace_ids = _unique(
        trace_id for member in members for trace_id in member.evidence_trace_ids
    )
    risk_level = _max_risk(member.risk_level for member in members)
    affected_agents = _unique_sorted(_metadata_values(members, "agent", "agent_id", "agent_name"))
    affected_versions = _unique_sorted(_metadata_values(members, "agent_version", "version"))
    outcome_labels = _unique_sorted(_metadata_values(members, "outcome_label", "outcome"))
    failure_mode = _most_common(_metadata_values(members, "failure_mode")) or "unclassified"

    return AgentImprovementInboxItem(
        item_id=f"inbox-{cluster.cluster_id}",
        title=representative.summary,
        candidate_ids=[member.id for member in members],
        affected_agents=affected_agents,
        affected_versions=affected_versions,
        evidence_trace_ids=evidence_trace_ids,
        representative_examples=_unique(member.observed_problem for member in members)[:3],
        frequency=frequency,
        trend="recurring" if frequency > 1 else "single",
        outcome_labels=outcome_labels,
        failure_mode=failure_mode,
        recommended_action_type=representative.recommended_action_type,
        risk_level=risk_level,
        suggested_scope=representative.scope,
        recommendation_rationale=_rationale(cluster, risk_level),
        suggested_eval_plan=_eval_plan(evidence_trace_ids, representative),
        suggested_rollout_plan=_rollout_plan(representative),
    )


def _metadata_values(candidates: list[LessonCandidate], *keys: str) -> list[str]:
    values: list[str] = []
    for candidate in candidates:
        for key in keys:
            raw = candidate.metadata.get(key)
            if isinstance(raw, list):
                values.extend(str(value) for value in raw if value not in (None, ""))
            elif raw not in (None, ""):
                values.append(str(raw))
    return values


def _unique(values: Iterable[object]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _unique_sorted(values: list[str]) -> list[str]:
    return sorted(set(values))


def _most_common(values: list[str]) -> str:
    if not values:
        return ""
    counts = Counter(values)
    return sorted(counts, key=lambda value: (-counts[value], value))[0]


def _max_risk(risks: Iterable[RiskLevel]) -> RiskLevel:
    return max(risks, key=lambda risk: _RISK_RANK[risk])


def _rationale(cluster: LessonCluster, risk_level: RiskLevel) -> str:
    representative = cluster.representative
    return (
        f"{cluster.occurrence_count} occurrence(s) grouped by recurring failure pattern; "
        f"representative confidence {representative.confidence:.2f}, "
        f"evidence strength {representative.evidence_strength:.2f}, risk {risk_level.value}."
    )


def _eval_plan(trace_ids: list[str], representative: LessonCandidate) -> str:
    traces = ", ".join(trace_ids[:3]) or "the representative trace"
    return (
        f"Create a regression eval from {traces} that fails when: {representative.observed_problem}"
    )


def _rollout_plan(representative: LessonCandidate) -> str:
    return (
        "Review the candidate, export the recommended artifact, test it against "
        f"the eval plan, then roll out at {representative.scope.value} scope."
    )
