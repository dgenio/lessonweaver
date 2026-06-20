"""Regression tests for CLI exit codes and stderr prefixes."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from lessonweaver.cli import main
from lessonweaver.models import (
    LessonCandidate,
    LessonStatus,
    RecommendedActionType,
    RiskLevel,
    Scope,
)
from lessonweaver.registry import FileSystemRegistry


def _candidate(
    *,
    action_type: RecommendedActionType = RecommendedActionType.EVAL,
    status: LessonStatus = LessonStatus.APPROVED,
) -> LessonCandidate:
    return LessonCandidate(
        id="cand-1",
        summary="Inspect diffs before PR review",
        evidence_trace_ids=["trace-1"],
        evidence_event_ids=["event-1"],
        observed_problem="Agent approved without checking the diff.",
        proposed_lesson="Inspect changed files before reviewing.",
        confidence=0.62,
        recommended_action_type=action_type,
        risk_level=RiskLevel.LOW,
        scope=Scope.PROJECT,
        status=status,
    )


CliCase = Callable[[Path], tuple[list[str], int, tuple[str, ...]]]


def _detect_missing_file(tmp_path: Path) -> tuple[list[str], int, tuple[str, ...]]:
    missing = tmp_path / "missing.json"
    return ["detect", str(missing)], 1, ("Error:", "file not found", str(missing))


def _detect_invalid_json(tmp_path: Path) -> tuple[list[str], int, tuple[str, ...]]:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    return ["detect", str(path)], 2, ("Error:", "invalid JSON")


def _answer_unknown_question(tmp_path: Path) -> tuple[list[str], int, tuple[str, ...]]:
    registry = FileSystemRegistry(tmp_path)
    registry.save_candidate(_candidate(status=LessonStatus.CANDIDATE))
    return (
        ["answer", "cand-1", "not-a-question", "approve", "--registry-root", str(tmp_path)],
        2,
        ("Error:", "question 'not-a-question' not found"),
    )


def _answer_unknown_option(tmp_path: Path) -> tuple[list[str], int, tuple[str, ...]]:
    registry = FileSystemRegistry(tmp_path)
    registry.save_candidate(_candidate(status=LessonStatus.CANDIDATE))
    return (
        ["answer", "cand-1", "decision", "not-an-option", "--registry-root", str(tmp_path)],
        2,
        ("Error:", "unknown option 'not-an-option'"),
    )


def _export_lesson_unapproved(tmp_path: Path) -> tuple[list[str], int, tuple[str, ...]]:
    registry = FileSystemRegistry(tmp_path)
    registry.save_candidate(_candidate(status=LessonStatus.CANDIDATE))
    return (
        ["export-lesson", "cand-1", "--format", "eval", "--registry-root", str(tmp_path)],
        1,
        ("Error:", "not approved"),
    )


def _export_lesson_action_mismatch(tmp_path: Path) -> tuple[list[str], int, tuple[str, ...]]:
    registry = FileSystemRegistry(tmp_path)
    registry.save_candidate(_candidate(action_type=RecommendedActionType.EVAL))
    return (
        ["export-lesson", "cand-1", "--format", "guardrail", "--registry-root", str(tmp_path)],
        1,
        ("Error:", "cannot export as 'guardrail'"),
    )


@pytest.mark.parametrize(
    "case_factory",
    [
        _detect_missing_file,
        _detect_invalid_json,
        _answer_unknown_question,
        _answer_unknown_option,
        _export_lesson_unapproved,
        _export_lesson_action_mismatch,
    ],
)
def test_cli_error_contracts(
    case_factory: CliCase, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    argv, expected_code, expected_stderr_tokens = case_factory(tmp_path)

    exit_code = main(argv)
    captured = capsys.readouterr()

    assert exit_code == expected_code
    assert captured.out == ""
    for token in expected_stderr_tokens:
        assert token in captured.err
