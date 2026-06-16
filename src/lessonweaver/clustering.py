"""Deterministic clustering of recurring lesson candidates across traces.

The detector emits one candidate per trace, so a failure pattern that recurs
across many traces produces many isolated candidates and a reviewer has to spot
the repetition by hand. ``LessonClusterer`` groups candidates by normalized word
overlap (Jaccard) of their ``summary`` + ``observed_problem`` text, so a
recurring pattern surfaces as a single cluster with a higher occurrence count.
Deterministic by construction: no embeddings, no model calls, no randomness,
and candidate order does not affect the output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .models import LessonCandidate

_TOKEN_RE = re.compile(r"[A-Za-z0-9_']+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "based",
    "before",
    "candidate",
    "for",
    "if",
    "in",
    "is",
    "it",
    "lesson",
    "must",
    "not",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "when",
}

DEFAULT_SIMILARITY_THRESHOLD = 0.4


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(value) if token.lower() not in _STOPWORDS}


def _candidate_tokens(candidate: LessonCandidate) -> set[str]:
    return _tokens(f"{candidate.summary} {candidate.observed_problem}")


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _is_stronger(candidate: LessonCandidate, current: LessonCandidate) -> bool:
    """Return True if ``candidate`` should replace ``current`` as the representative.

    A representative is the highest-confidence member; ties break on higher
    evidence strength, then on the lexicographically smaller id so the choice is
    fully deterministic regardless of input order.
    """
    candidate_rank = (candidate.confidence, candidate.evidence_strength)
    current_rank = (current.confidence, current.evidence_strength)
    if candidate_rank != current_rank:
        return candidate_rank > current_rank
    return candidate.id < current.id


def _candidate_sort_key(candidate: LessonCandidate) -> tuple[str, str, str, float, float]:
    return (
        candidate.id,
        candidate.summary,
        candidate.observed_problem,
        candidate.confidence,
        candidate.evidence_strength,
    )


@dataclass(slots=True)
class LessonCluster:
    """A group of lesson candidates judged to describe the same recurring pattern."""

    cluster_id: str
    representative: LessonCandidate
    members: list[LessonCandidate] = field(default_factory=list)

    @property
    def occurrence_count(self) -> int:
        return len(self.members)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "occurrence_count": self.occurrence_count,
            "representative_id": self.representative.id,
            "member_ids": [member.id for member in self.members],
            "representative": self.representative.to_dict(),
        }


class LessonClusterer:
    """Group similar lesson candidates so recurring patterns stand out.

    Candidates are processed in canonical order by id, summary,
    observed_problem, confidence, and evidence strength. A candidate joins the
    first existing cluster whose seed it meets ``threshold`` Jaccard similarity
    with; otherwise it seeds a new cluster. Comparing against each cluster's
    stable seed (rather than every member) keeps the result a deterministic
    function of candidate content, candidate ids, and ``threshold``.
    """

    def __init__(self, threshold: float = DEFAULT_SIMILARITY_THRESHOLD) -> None:
        if not 0.0 < threshold <= 1.0:
            raise ValueError("threshold must be in the interval (0.0, 1.0]")
        self.threshold = threshold

    def cluster(self, candidates: list[LessonCandidate]) -> list[LessonCluster]:
        clusters: list[LessonCluster] = []
        seed_tokens: list[set[str]] = []
        for candidate in sorted(candidates, key=_candidate_sort_key):
            tokens = _candidate_tokens(candidate)
            placed = False
            for index, existing in enumerate(clusters):
                if _jaccard(tokens, seed_tokens[index]) >= self.threshold:
                    existing.members.append(candidate)
                    if _is_stronger(candidate, existing.representative):
                        existing.representative = candidate
                    placed = True
                    break
            if not placed:
                clusters.append(
                    LessonCluster(
                        cluster_id=f"cluster-{candidate.id}",
                        representative=candidate,
                        members=[candidate],
                    )
                )
                seed_tokens.append(tokens)
        return clusters
