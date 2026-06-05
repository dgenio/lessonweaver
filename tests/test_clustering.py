"""Tests for deterministic multi-trace lesson clustering."""

import pytest

from lessonweaver.clustering import LessonClusterer
from lessonweaver.models import LessonCandidate, RecommendedActionType, RiskLevel, Scope


def _candidate(
    candidate_id: str,
    summary: str,
    observed_problem: str,
    *,
    confidence: float = 0.5,
    evidence_strength: float = 0.4,
) -> LessonCandidate:
    return LessonCandidate(
        id=candidate_id,
        summary=summary,
        evidence_trace_ids=[f"{candidate_id}-trace"],
        evidence_event_ids=[],
        observed_problem=observed_problem,
        proposed_lesson="Apply the corrected check earlier.",
        confidence=confidence,
        recommended_action_type=RecommendedActionType.SKILL,
        risk_level=RiskLevel.LOW,
        scope=Scope.PROJECT,
        evidence_strength=evidence_strength,
    )


def _recurring_pair() -> list[LessonCandidate]:
    return [
        _candidate(
            "c1",
            "Agent skipped the version check before answering",
            "Agent answered without verifying the policy version",
        ),
        _candidate(
            "c2",
            "Agent skipped version check before responding",
            "Agent answered without verifying policy version",
        ),
    ]


def test_groups_similar_candidates_into_one_cluster() -> None:
    clusters = LessonClusterer().cluster(_recurring_pair())
    assert len(clusters) == 1
    assert clusters[0].occurrence_count == 2
    assert {member.id for member in clusters[0].members} == {"c1", "c2"}


def test_keeps_unrelated_candidates_separate() -> None:
    candidates = [
        _candidate(
            "c1",
            "Agent skipped the version check before answering",
            "Agent answered without verifying the policy version",
        ),
        _candidate(
            "c2",
            "Tool call failed and a fallback succeeded",
            "An external API timed out and required a retry",
        ),
    ]
    clusters = LessonClusterer().cluster(candidates)
    assert len(clusters) == 2
    assert all(cluster.occurrence_count == 1 for cluster in clusters)


def test_representative_is_highest_confidence_member() -> None:
    weak, strong = _recurring_pair()
    weak.confidence = 0.45
    strong.confidence = 0.80
    clusters = LessonClusterer().cluster([weak, strong])
    assert len(clusters) == 1
    assert clusters[0].representative.id == "c2"


def test_cluster_id_is_seeded_by_first_member() -> None:
    clusters = LessonClusterer().cluster(_recurring_pair())
    assert clusters[0].cluster_id == "cluster-c1"


def test_empty_input_returns_no_clusters() -> None:
    assert LessonClusterer().cluster([]) == []


def test_invalid_threshold_raises() -> None:
    with pytest.raises(ValueError):
        LessonClusterer(threshold=0.0)
    with pytest.raises(ValueError):
        LessonClusterer(threshold=1.5)


def test_to_dict_exposes_counts_and_members() -> None:
    clusters = LessonClusterer().cluster(_recurring_pair())
    payload = clusters[0].to_dict()
    assert payload["cluster_id"] == "cluster-c1"
    assert payload["occurrence_count"] == 2
    assert payload["representative_id"] == "c1"
    assert payload["member_ids"] == ["c1", "c2"]
    assert payload["representative"]["id"] == "c1"
