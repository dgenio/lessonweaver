"""Tests for the detection-quality corpus and precision/recall harness."""

import json
from pathlib import Path

import pytest

from lessonweaver.detection_eval import (
    FALSE_NEGATIVE,
    DetectionCorpus,
    run_clustered_detection_eval,
    run_detection_eval,
)

CORPUS_PATH = "examples/detection_corpus/corpus.json"
BENCHMARK_CORPUS_PATH = "benchmark/v1/corpus.json"
BENCHMARK_RESULTS_PATH = "benchmark/v1/results.json"


def test_bundled_corpus_matches_baseline_scorecard() -> None:
    report = run_detection_eval(DetectionCorpus.from_file(CORPUS_PATH))
    # Baseline locked so a quiet detection-quality regression fails CI.
    assert report.total_cases == 10
    assert report.true_positives == 5
    assert report.false_negatives == 2
    assert report.false_positives == 0
    assert report.true_negatives == 3
    assert report.precision == pytest.approx(1.0)
    assert report.recall == pytest.approx(5 / 7)
    assert report.f1 == pytest.approx(2 * (5 / 7) / (1 + 5 / 7))


def test_public_benchmark_v1_matches_checked_in_results() -> None:
    corpus = DetectionCorpus.from_file(BENCHMARK_CORPUS_PATH)
    expected_results = json.loads(Path(BENCHMARK_RESULTS_PATH).read_text(encoding="utf-8"))

    report = run_detection_eval(corpus)

    assert corpus.corpus_id == "lessonweaver-detection-benchmark-v1"
    assert report.total_cases >= 20
    assert {case.pattern for case in corpus.cases} >= {
        "metadata_flag",
        "human_correction",
        "failed_evaluation",
        "workflow_step",
        "error_retry",
        "tool_fallback",
        "corrected_outcome",
        "recurring_unflagged",
        "no_candidate",
    }
    assert report.to_dict() == expected_results


def test_eval_report_includes_per_signal_metrics() -> None:
    corpus = DetectionCorpus.from_dict(
        {
            "corpus_id": "per-signal",
            "cases": [
                {
                    "case_id": "metadata-positive",
                    "should_detect": True,
                    "pattern": "metadata_flag",
                    "trace": {
                        "trace_id": "metadata-positive",
                        "source": "unit-test",
                        "task": "Review flagged trace",
                        "events": [{"id": "1", "type": "final_answer", "content": "done"}],
                        "outcome": "success",
                        "metadata": {"lesson_candidate": True},
                    },
                },
                {
                    "case_id": "clean-negative",
                    "should_detect": False,
                    "pattern": "no_candidate",
                    "trace": {
                        "trace_id": "clean-negative",
                        "source": "unit-test",
                        "task": "Greet",
                        "events": [{"id": "1", "type": "final_answer", "content": "hello"}],
                        "outcome": "success",
                    },
                },
            ],
        }
    )

    metrics = run_detection_eval(corpus).to_dict()["by_pattern"]

    assert metrics["metadata_flag"]["true_positives"] == 1
    assert metrics["metadata_flag"]["precision"] == pytest.approx(1.0)
    assert metrics["metadata_flag"]["recall"] == pytest.approx(1.0)
    assert metrics["no_candidate"]["true_negatives"] == 1


def test_known_gap_case_is_a_false_negative() -> None:
    report = run_detection_eval(DetectionCorpus.from_file(CORPUS_PATH))
    gap = next(r for r in report.results if r.case_id == "recurring-unflagged-version-miss")
    assert gap.expected is True
    assert gap.detected is False
    assert gap.classification == FALSE_NEGATIVE


def test_clustered_eval_improves_recurring_unflagged_recall() -> None:
    corpus = DetectionCorpus.from_file(CORPUS_PATH)

    base_report = run_detection_eval(corpus)
    clustered_report = run_clustered_detection_eval(corpus)

    recurring = [
        result for result in base_report.results if result.pattern == "recurring_unflagged"
    ]
    assert len(recurring) >= 2
    assert all(result.classification == FALSE_NEGATIVE for result in recurring)
    assert clustered_report.recall_without_clustering == base_report.recall
    assert clustered_report.recall_with_clustering > base_report.recall
    assert clustered_report.clustering_recall_lift > 0
    assert "answered_without_checking_policy_version" in clustered_report.clustered_patterns


def test_clustered_eval_keeps_distinct_recurring_patterns_separate() -> None:
    corpus = DetectionCorpus.from_dict(
        {
            "corpus_id": "distinct-patterns",
            "cases": [
                {
                    "case_id": "pattern-a",
                    "should_detect": True,
                    "trace": {
                        "trace_id": "trace-a",
                        "source": "unit-test",
                        "task": "A",
                        "events": [],
                        "outcome": "success",
                        "metadata": {"recurring_pattern": "pattern_a"},
                    },
                },
                {
                    "case_id": "pattern-b",
                    "should_detect": True,
                    "trace": {
                        "trace_id": "trace-b",
                        "source": "unit-test",
                        "task": "B",
                        "events": [],
                        "outcome": "success",
                        "metadata": {"recurring_pattern": "pattern_b"},
                    },
                },
            ],
        }
    )

    clustered_report = run_clustered_detection_eval(corpus)

    assert clustered_report.clustered_patterns == []
    assert clustered_report.clustered_true_positives == 0
    assert clustered_report.clustered_false_negatives == 2


def test_inline_benign_case_is_true_negative() -> None:
    corpus = DetectionCorpus.from_dict(
        {
            "corpus_id": "inline-1",
            "cases": [
                {
                    "case_id": "benign",
                    "should_detect": False,
                    "trace": {
                        "trace_id": "t1",
                        "source": "unit-test",
                        "task": "Greet",
                        "events": [
                            {"id": "1", "type": "user_message", "content": "hi"},
                            {"id": "2", "type": "final_answer", "content": "hello"},
                        ],
                        "outcome": "success",
                    },
                }
            ],
        }
    )
    report = run_detection_eval(corpus)
    assert report.true_negatives == 1
    assert report.passed == 1
    # No positives at all: precision/recall degrade to 0.0 rather than dividing by zero.
    assert report.precision == 0.0
    assert report.recall == 0.0


def test_label_mismatch_is_false_positive() -> None:
    corpus = DetectionCorpus.from_dict(
        {
            "corpus_id": "inline-fp",
            "cases": [
                {
                    "case_id": "mislabeled",
                    "should_detect": False,
                    "trace_path": "github_pr_review_failure.json",
                }
            ],
        },
        base_dir=Path("examples/traces"),
    )
    report = run_detection_eval(corpus)
    assert report.false_positives == 1
    assert report.precision == 0.0


def test_case_without_trace_source_raises() -> None:
    with pytest.raises(ValueError, match="inline 'trace' object or a 'trace_path'"):
        DetectionCorpus.from_dict({"corpus_id": "bad", "cases": [{"case_id": "missing"}]})
