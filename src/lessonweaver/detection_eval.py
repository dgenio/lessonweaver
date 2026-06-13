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
from .models import TraceBundle

TRUE_POSITIVE = "true_positive"
TRUE_NEGATIVE = "true_negative"
FALSE_POSITIVE = "false_positive"
FALSE_NEGATIVE = "false_negative"


def _classify(should_detect: bool, detected: bool) -> str:
    if should_detect:
        return TRUE_POSITIVE if detected else FALSE_NEGATIVE
    return FALSE_POSITIVE if detected else TRUE_NEGATIVE


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
class DetectionEvalPatternMetrics:
    """Aggregate scorecard for one labeled detection pattern."""

    total_cases: int
    passed: int
    failed: int
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int

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
        }


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
    by_pattern: dict[str, DetectionEvalPatternMetrics] = field(default_factory=dict)

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
            "by_pattern": {
                pattern: metrics.to_dict()
                for pattern, metrics in sorted(self.by_pattern.items(), key=lambda item: item[0])
            },
            "results": [result.to_dict() for result in self.results],
        }


def _metrics_for_results(results: list[DetectionEvalResult]) -> DetectionEvalPatternMetrics:
    true_positives = sum(1 for result in results if result.classification == TRUE_POSITIVE)
    true_negatives = sum(1 for result in results if result.classification == TRUE_NEGATIVE)
    false_positives = sum(1 for result in results if result.classification == FALSE_POSITIVE)
    false_negatives = sum(1 for result in results if result.classification == FALSE_NEGATIVE)
    passed = sum(1 for result in results if result.passed)
    return DetectionEvalPatternMetrics(
        total_cases=len(results),
        passed=passed,
        failed=len(results) - passed,
        true_positives=true_positives,
        true_negatives=true_negatives,
        false_positives=false_positives,
        false_negatives=false_negatives,
    )


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
        candidates = detector.detect(case.trace)
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
    patterns = sorted({result.pattern or "unlabeled" for result in results})
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
        by_pattern={
            pattern: _metrics_for_results(
                [result for result in results if (result.pattern or "unlabeled") == pattern]
            )
            for pattern in patterns
        },
    )
