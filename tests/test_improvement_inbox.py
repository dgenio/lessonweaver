"""Tests for the agent improvement inbox (#116)."""

from __future__ import annotations

from lessonweaver import (
    AgentImprovementInboxBuilder,
    FileSystemRegistry,
    LessonCandidate,
    LessonStatus,
    RecommendedActionType,
    RiskLevel,
    Scope,
    record_improvement_inbox_action,
)


def _candidate(
    candidate_id: str,
    summary: str,
    observed_problem: str,
    *,
    risk: RiskLevel = RiskLevel.MEDIUM,
    action: RecommendedActionType = RecommendedActionType.SKILL,
    metadata: dict[str, object] | None = None,
) -> LessonCandidate:
    return LessonCandidate(
        id=candidate_id,
        summary=summary,
        evidence_trace_ids=[f"trace-{candidate_id}"],
        evidence_event_ids=[f"event-{candidate_id}"],
        observed_problem=observed_problem,
        proposed_lesson="Add the missing pre-check before answering.",
        confidence=0.7,
        recommended_action_type=action,
        risk_level=risk,
        scope=Scope.PROJECT,
        evidence_strength=0.6,
        evidence_summary="Human correction and failed evaluation agree.",
        metadata=dict(metadata or {}),
    )


def _inbox_candidates() -> list[LessonCandidate]:
    return [
        _candidate(
            "c1",
            "Agent skipped version validation before answering",
            "Agent answered without verifying policy version",
            risk=RiskLevel.HIGH,
            action=RecommendedActionType.GUARDRAIL,
            metadata={
                "agent": "support-bot",
                "agent_version": "1.2.0",
                "outcome_label": "incorrect_answer",
                "failure_mode": "missing_validation",
            },
        ),
        _candidate(
            "c2",
            "Agent skipped the version check before responding",
            "Agent answered without verifying the policy version",
            risk=RiskLevel.HIGH,
            action=RecommendedActionType.GUARDRAIL,
            metadata={
                "agent": "support-bot",
                "agent_version": "1.2.1",
                "outcome_label": "human_corrected",
                "failure_mode": "missing_validation",
            },
        ),
        _candidate(
            "c3",
            "Tool call timed out and fallback succeeded",
            "External API timed out before retry recovered",
            risk=RiskLevel.LOW,
            action=RecommendedActionType.WORKFLOW_CHANGE,
            metadata={"agent": "research-bot", "agent_version": "0.9.0"},
        ),
    ]


def test_inbox_groups_recurring_patterns_and_sorts_by_impact() -> None:
    inbox = AgentImprovementInboxBuilder().build(_inbox_candidates())

    assert [item.item_id for item in inbox.items] == ["inbox-cluster-c1", "inbox-cluster-c3"]
    recurring = inbox.items[0]
    assert recurring.title == "Agent skipped version validation before answering"
    assert recurring.candidate_ids == ["c1", "c2"]
    assert recurring.frequency == 2
    assert recurring.affected_agents == ["support-bot"]
    assert recurring.affected_versions == ["1.2.0", "1.2.1"]
    assert recurring.evidence_trace_ids == ["trace-c1", "trace-c2"]
    assert recurring.outcome_labels == ["human_corrected", "incorrect_answer"]
    assert recurring.failure_mode == "missing_validation"
    assert recurring.recommended_action_type is RecommendedActionType.GUARDRAIL
    assert recurring.risk_level is RiskLevel.HIGH
    assert recurring.suggested_scope is Scope.PROJECT
    assert "2 occurrence" in recurring.recommendation_rationale
    assert recurring.review_actions == ["approve", "reject", "defer", "create_issue"]


def test_inbox_can_filter_to_recurring_failures() -> None:
    inbox = AgentImprovementInboxBuilder(min_frequency=2).build(_inbox_candidates())

    assert len(inbox.items) == 1
    assert inbox.items[0].candidate_ids == ["c1", "c2"]


def test_inbox_skips_resolved_candidates_before_clustering() -> None:
    candidates = _inbox_candidates()
    candidates[0].status = LessonStatus.APPROVED
    candidates[1].status = LessonStatus.REJECTED
    candidates[2].status = LessonStatus.NEEDS_REVIEW

    inbox = AgentImprovementInboxBuilder().build(candidates)

    assert [item.candidate_ids for item in inbox.items] == [["c3"]]


def test_inbox_exports_json_and_markdown() -> None:
    inbox = AgentImprovementInboxBuilder(min_frequency=2).build(_inbox_candidates())

    payload = inbox.to_dict()
    assert payload["items"][0]["frequency"] == 2
    assert payload["items"][0]["review_actions"] == [
        "approve",
        "reject",
        "defer",
        "create_issue",
    ]

    markdown = inbox.to_markdown()
    assert "# Agent improvement inbox" in markdown
    assert "Agent skipped version validation before answering" in markdown
    assert "- Frequency: 2" in markdown
    assert "- Actions: approve, reject, defer, create_issue" in markdown


def test_record_inbox_action_rejects_and_defers_candidates(tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    for candidate in _inbox_candidates()[:2]:
        registry.save_candidate(candidate)

    record_improvement_inbox_action(
        registry,
        ["c1"],
        "reject",
        reviewer="alice",
        note="Too broad.",
    )
    rejected = registry.load_candidate("c1")
    assert rejected.status is LessonStatus.REJECTED
    assert rejected.metadata["improvement_inbox"]["action"] == "reject"
    assert rejected.metadata["improvement_inbox"]["reviewer"] == "alice"
    assert rejected.metadata["improvement_inbox"]["note"] == "Too broad."

    record_improvement_inbox_action(
        registry,
        ["c2"],
        "defer",
        reviewer="bob",
        note="Wait for rollout data.",
    )
    deferred = registry.load_candidate("c2")
    assert deferred.status is LessonStatus.NEEDS_REVIEW
    assert deferred.metadata["improvement_inbox"]["action"] == "defer"
