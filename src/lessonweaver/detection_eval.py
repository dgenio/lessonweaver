"""Measure detection quality against a labeled trace corpus.

The detector is conservative by design (it prefers false negatives), which makes
its quality hard to argue about without evidence: does it actually find recurring
failures, or does it mostly re-surface mistakes a human already flagged? A
*detection corpus* pairs traces with a ground-truth ``should_detect`` label —
including non-obvious recurring patterns the detector may still miss — so
precision, recall, and F1 can be measured and regressions caught in CI. Fully
deterministic; no model calls.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .detection import LessonDetector
from .models import LessonCandidate, TraceBundle

TRUE_POSITIVE = "true_positive"
TRUE_NEGATIVE = "true_negative"
FALSE_POSITIVE = "false_positive"
FALSE_NEGATIVE = "false_negative"
CLUSTER_ONLY_METADATA_KEY = "cluster_only"


def _classify(should_detect: bool, detected: bool) -> str:
    if should_detect:
        return TRUE_POSITIVE if detected else FALSE_NEGATIVE
    return FALSE_POSITIVE if detected else TRUE_NEGATIVE


def _is_cluster_only_candidate(candidate: LessonCandidate) -> bool:
    return candidate.metadata.get(CLUSTER_ONLY_METADATA_KEY) is True


@dataclass(slots=True)
class DetectionCase:
    """A single labeled trace expectation.

    ``should_detect`` is the ground truth: ``True`` means the detector ought to
    emit at least one candidate for this trace, ``False`` means it should stay
    silent (a benign variation). ``pattern`` is a free-text label for grouping
    related cases in a scorecard; it does not affect scoring.
    """

    case_id: str
    trace: TraceBundle
    should_detect: bool = True
    pattern: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, base_dir: Path | None = None) -> DetectionCase:
        if "trace" in data:
            trace = TraceBundle.from_dict(data["trace"])
        elif "trace_path" in data:
            trace_path = Path(str(data["trace_path"]))
            if base_dir is not None and not trace_path.is_absolute():
                trace_path = base_dir / trace_path
            with trace_path.open("r", encoding="utf-8") as handle:
                trace = TraceBundle.from_dict(json.load(handle))
        else:
            raise ValueError(
                f"detection case '{data.get('case_id', '?')}' must provide either an inline "
                f"'trace' object or a 'trace_path'"
            )
        return cls(
            case_id=str(data["case_id"]),
            trace=trace,
            should_detect=bool(data.get("should_detect", True)),
            pattern=str(data.get("pattern", "")),
            notes=str(data.get("notes", "")),
        )


@dataclass(slots=True)
class DetectionCorpus:
    """A set of labeled detection cases."""

    corpus_id: str
    cases: list[DetectionCase] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, base_dir: Path | None = None) -> DetectionCorpus:
        return cls(
            corpus_id=str(data["corpus_id"]),
            cases=[
                DetectionCase.from_dict(item, base_dir=base_dir) for item in data.get("cases", [])
            ],
        )

    @classmethod
    def from_file(cls, path: str | Path) -> DetectionCorpus:
        """Load a corpus from JSON. ``trace_path`` entries resolve relative to it."""
        corpus_path = Path(path)
        with corpus_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"{path} must contain a JSON object")
        return cls.from_dict(data, base_dir=corpus_path.parent)


@dataclass(slots=True)
class DetectionEvalResult:
    """Outcome of scoring one case against the detector."""

    case_id: str
    expected: bool  # should_detect
    detected: bool  # whether any candidate was produced
    passed: bool  # detected == expected
    classification: str  # one of the TRUE_/FALSE_ constants in this module
    candidate_count: int
    pattern: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DetectionEvalReport:
    """Aggregate detection-quality scorecard with precision/recall/F1."""

    corpus_id: str
    total_cases: int
    passed: int
    failed: int
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    results: list[DetectionEvalResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total_cases if self.total_cases > 0 else 0.0

    @property
    def precision(self) -> float:
        predicted_positive = self.true_positives + self.false_positives
        return self.true_positives / predicted_positive if predicted_positive > 0 else 0.0

    @property
    def recall(self) -> float:
        actual_positive = self.true_positives + self.false_negatives
        return self.true_positives / actual_positive if actual_positive > 0 else 0.0

    @property
    def f1(self) -> float:
        denominator = self.precision + self.recall
        return 2 * self.precision * self.recall / denominator if denominator > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "corpus_id": self.corpus_id,
            "total_cases": self.total_cases,
            "passed": self.passed,
            "failed": self.failed,
            "true_positives": self.true_positives,
            "true_negatives": self.true_negatives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "pass_rate": self.pass_rate,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "results": [result.to_dict() for result in self.results],
        }


@dataclass(slots=True)
class ClusteredDetectionEvalReport:
    """Detection scorecard comparing independent recall with clustered recall."""

    corpus_id: str
    total_cases: int
    recall_without_clustering: float
    recall_with_clustering: float
    clustering_recall_lift: float
    clustered_true_positives: int
    clustered_false_negatives: int
    clustered_patterns: list[str] = field(default_factory=list)
    base_report: DetectionEvalReport | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "corpus_id": self.corpus_id,
            "total_cases": self.total_cases,
            "recall_without_clustering": self.recall_without_clustering,
            "recall_with_clustering": self.recall_with_clustering,
            "clustering_recall_lift": self.clustering_recall_lift,
            "clustered_true_positives": self.clustered_true_positives,
            "clustered_false_negatives": self.clustered_false_negatives,
            "clustered_patterns": self.clustered_patterns,
            "base_report": self.base_report.to_dict() if self.base_report is not None else None,
        }


def run_detection_eval(
    corpus: DetectionCorpus, detector: LessonDetector | None = None
) -> DetectionEvalReport:
    """Run the detector over every case and score detect/no-detect against labels.

    A case passes when the detector's silence/output matches ``should_detect``.
    Delegates entirely to ``LessonDetector``; no model calls.
    """
    detector = detector or LessonDetector()
    results: list[DetectionEvalResult] = []
    tallies: dict[str, int] = {
        TRUE_POSITIVE: 0,
        TRUE_NEGATIVE: 0,
        FALSE_POSITIVE: 0,
        FALSE_NEGATIVE: 0,
    }

    for case in corpus.cases:
        candidates = [
            candidate
            for candidate in detector.detect(case.trace)
            if not _is_cluster_only_candidate(candidate)
        ]
        detected = bool(candidates)
        classification = _classify(case.should_detect, detected)
        tallies[classification] += 1
        results.append(
            DetectionEvalResult(
                case_id=case.case_id,
                expected=case.should_detect,
                detected=detected,
                passed=detected == case.should_detect,
                classification=classification,
                candidate_count=len(candidates),
                pattern=case.pattern,
                notes=case.notes,
            )
        )

    passed_count = sum(1 for result in results if result.passed)
    return DetectionEvalReport(
        corpus_id=corpus.corpus_id,
        total_cases=len(results),
        passed=passed_count,
        failed=len(results) - passed_count,
        true_positives=tallies[TRUE_POSITIVE],
        true_negatives=tallies[TRUE_NEGATIVE],
        false_positives=tallies[FALSE_POSITIVE],
        false_negatives=tallies[FALSE_NEGATIVE],
        results=results,
    )


def run_clustered_detection_eval(
    corpus: DetectionCorpus,
    detector: LessonDetector | None = None,
    *,
    min_occurrences: int = 2,
) -> ClusteredDetectionEvalReport:
    """Score recall after promoting repeated weak candidates through clustering.

    ``run_detection_eval`` remains strict: weak ``cluster_only`` candidates do
    not count as independently detected. This opt-in path groups those weak
    candidates across the whole corpus and treats a recurring pattern as
    detected only when at least ``min_occurrences`` occurrences cluster.
    """
    detector = detector or LessonDetector()
    base_report = run_detection_eval(corpus, detector)
    weak_pattern_counts: dict[str, int] = {}
    weak_pattern_by_trace: dict[str, str] = {}

    for case in corpus.cases:
        for candidate in detector.detect(case.trace):
            if not _is_cluster_only_candidate(candidate):
                continue
            recurring_pattern = candidate.metadata.get("recurring_pattern")
            if not isinstance(recurring_pattern, str) or not recurring_pattern:
                continue
            weak_pattern_counts[recurring_pattern] = (
                weak_pattern_counts.get(recurring_pattern, 0) + 1
            )
            for trace_id in candidate.evidence_trace_ids:
                weak_pattern_by_trace[trace_id] = recurring_pattern

    clustered_patterns = {
        pattern for pattern, count in weak_pattern_counts.items() if count >= min_occurrences
    }

    detected_with_clustering = []
    for case, result in zip(corpus.cases, base_report.results, strict=True):
        recurring_pattern = weak_pattern_by_trace.get(case.trace.trace_id, "")
        detected_with_clustering.append(
            result.detected or (case.should_detect and recurring_pattern in clustered_patterns)
        )

    clustered_true_positives = sum(
        1
        for case, detected in zip(corpus.cases, detected_with_clustering, strict=True)
        if case.should_detect and detected
    )
    clustered_false_negatives = sum(
        1
        for case, detected in zip(corpus.cases, detected_with_clustering, strict=True)
        if case.should_detect and not detected
    )
    denominator = clustered_true_positives + clustered_false_negatives
    recall_with_clustering = clustered_true_positives / denominator if denominator > 0 else 0.0

    return ClusteredDetectionEvalReport(
        corpus_id=corpus.corpus_id,
        total_cases=len(corpus.cases),
        recall_without_clustering=base_report.recall,
        recall_with_clustering=recall_with_clustering,
        clustering_recall_lift=recall_with_clustering - base_report.recall,
        clustered_true_positives=clustered_true_positives,
        clustered_false_negatives=clustered_false_negatives,
        clustered_patterns=sorted(clustered_patterns),
        base_report=base_report,
    )
