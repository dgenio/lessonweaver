"""Tests for the detection-quality corpus and precision/recall harness."""

from pathlib import Path

import pytest

from lessonweaver.detection_eval import (
    FALSE_NEGATIVE,
    DetectionCorpus,
    run_detection_eval,
)

CORPUS_PATH = "examples/detection_corpus/corpus.json"


def test_bundled_corpus_matches_baseline_scorecard() -> None:
    report = run_detection_eval(DetectionCorpus.from_file(CORPUS_PATH))
    # Baseline locked so a quiet detection-quality regression fails CI.
    assert report.total_cases == 9
    assert report.true_positives == 5
    assert report.false_negatives == 1
    assert report.false_positives == 0
    assert report.true_negatives == 3
    assert report.precision == pytest.approx(1.0)
    assert report.recall == pytest.approx(5 / 6)
    assert report.f1 == pytest.approx(2 * (5 / 6) / (1 + 5 / 6))


def test_known_gap_case_is_a_false_negative() -> None:
    report = run_detection_eval(DetectionCorpus.from_file(CORPUS_PATH))
    gap = next(r for r in report.results if r.case_id == "recurring-unflagged-version-miss")
    assert gap.expected is True
    assert gap.detected is False
    assert gap.classification == FALSE_NEGATIVE


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
