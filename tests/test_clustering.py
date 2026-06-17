"""Tests for deterministic multi-trace lesson clustering."""

import pytest

from lessonweaver.clustering import DEFAULT_SIMILARITY_THRESHOLD, LessonCluster, LessonClusterer
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


def _cluster_signature(clusters: list[LessonCluster]) -> list[tuple[str, str, tuple[str, ...]]]:
    return [
        (
            cluster.cluster_id,
            cluster.representative.id,
            tuple(member.id for member in cluster.members),
        )
        for cluster in clusters
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


def test_cluster_id_is_seeded_by_canonical_first_member() -> None:
    clusters = LessonClusterer().cluster(list(reversed(_recurring_pair())))
    assert clusters[0].cluster_id == "cluster-c1"


def test_representative_tie_breaks_on_lexicographic_id() -> None:
    first, second = _recurring_pair()
    clusters = LessonClusterer().cluster([second, first])
    assert len(clusters) == 1
    assert clusters[0].representative.id == "c1"


def test_cluster_output_is_independent_of_input_order() -> None:
    first, second = _recurring_pair()
    unrelated = _candidate(
        "c3",
        "Payment API timed out during checkout",
        "Fallback endpoint resolved the request",
    )

    original = [first, second, unrelated]
    shuffled = [unrelated, second, first]

    assert _cluster_signature(LessonClusterer().cluster(original)) == _cluster_signature(
        LessonClusterer().cluster(shuffled)
    )
    assert _cluster_signature(LessonClusterer().cluster(shuffled)) == [
        ("cluster-c1", "c1", ("c1", "c2")),
        ("cluster-c3", "c3", ("c3",)),
    ]


def test_empty_input_returns_no_clusters() -> None:
    assert LessonClusterer().cluster([]) == []


def test_invalid_threshold_raises() -> None:
    with pytest.raises(ValueError, match="threshold"):
        LessonClusterer(threshold=0.0)
    with pytest.raises(ValueError, match="threshold"):
        LessonClusterer(threshold=1.5)


def test_similarity_threshold_boundary_is_inclusive() -> None:
    # The two candidates share 2 tokens out of a 5-token union, so Jaccard = 0.4.
    base = _candidate("c1", "alpha beta gamma", "")
    boundary = _candidate("c2", "alpha beta delta epsilon", "")

    assert (
        len(
            LessonClusterer(threshold=DEFAULT_SIMILARITY_THRESHOLD - 0.01).cluster([base, boundary])
        )
        == 1
    )
    assert (
        len(LessonClusterer(threshold=DEFAULT_SIMILARITY_THRESHOLD).cluster([base, boundary])) == 1
    )
    assert (
        len(
            LessonClusterer(threshold=DEFAULT_SIMILARITY_THRESHOLD + 0.01).cluster([base, boundary])
        )
        == 2
    )


def test_to_dict_exposes_counts_and_members() -> None:
    clusters = LessonClusterer().cluster(_recurring_pair())
    payload = clusters[0].to_dict()
    assert payload["cluster_id"] == "cluster-c1"
    assert payload["occurrence_count"] == 2
    assert payload["representative_id"] == "c1"
    assert payload["member_ids"] == ["c1", "c2"]
    assert payload["representative"]["id"] == "c1"


def test_groups_three_similar_candidates_into_one_cluster() -> None:
    candidates = [
        _candidate(
            "c1",
            "Agent skipped the version check before answering",
            "Agent answered without verifying the policy version",
            confidence=0.55,
        ),
        _candidate(
            "c2",
            "Agent skipped version check before responding",
            "Agent answered without verifying policy version",
            confidence=0.80,
        ),
        _candidate(
            "c3",
            "Agent did check version before answering",
            "Agent answered without verifying the policy version field",
            confidence=0.60,
        ),
    ]
    clusters = LessonClusterer().cluster(candidates)
    assert len(clusters) == 1
    assert clusters[0].occurrence_count == 3
    assert {member.id for member in clusters[0].members} == {"c1", "c2", "c3"}
    # Representative is the highest-confidence member across all three.
    assert clusters[0].representative.id == "c2"


def test_identical_candidates_collapse_into_one_cluster() -> None:
    candidates = [
        _candidate(
            "dup-1",
            "Agent skipped the version check before answering",
            "Agent answered without verifying the policy version",
        ),
        _candidate(
            "dup-2",
            "Agent skipped the version check before answering",
            "Agent answered without verifying the policy version",
        ),
    ]
    clusters = LessonClusterer().cluster(candidates)
    assert len(clusters) == 1
    assert clusters[0].occurrence_count == 2
    assert {member.id for member in clusters[0].members} == {"dup-1", "dup-2"}
