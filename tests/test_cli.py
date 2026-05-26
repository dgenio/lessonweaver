"""Tests for CLI subcommands."""

import json

from lessonweaver.cli import main
from lessonweaver.models import RiskLevel, Scope, SkillCard, SkillStatus
from lessonweaver.registry import FileSystemRegistry


def _skill(skill_id: str = "skill-1", *, status: SkillStatus = SkillStatus.ACTIVE) -> SkillCard:
    return SkillCard(
        id=skill_id,
        name="PR Diff First",
        description="Inspect changed files before reviewing pull requests.",
        applies_when=["reviewing pull requests"],
        does_not_apply_when=["no code changes"],
        instructions=["Inspect changed files first"],
        anti_patterns=["title-only approval"],
        evidence_trace_ids=["trace-1"],
        confidence=0.8,
        risk_level=RiskLevel.LOW,
        scope=Scope.PROJECT,
        version="0.2.0",
        status=status,
    )


def test_cli_detect_produces_json(capsys) -> None:
    exit_code = main(["detect", "examples/traces/github_pr_review_failure.json"])
    assert exit_code == 0
    output = capsys.readouterr().out
    candidates = json.loads(output)
    assert isinstance(candidates, list)
    assert len(candidates) >= 1
    assert "summary" in candidates[0]


def test_cli_detect_save_and_interview_candidate(capsys, tmp_path) -> None:
    main(
        [
            "detect",
            "examples/traces/github_pr_review_failure.json",
            "--save",
            "--registry-root",
            str(tmp_path),
        ]
    )
    capsys.readouterr()
    exit_code = main(
        ["interview", "trace-gh-pr-review-001-human-correction", "--registry-root", str(tmp_path)]
    )
    assert exit_code == 0
    questions = json.loads(capsys.readouterr().out)
    assert any(question["id"] == "decision" for question in questions)


def test_cli_answer_and_approve_flow(capsys, tmp_path) -> None:
    main(
        [
            "detect",
            "examples/traces/github_pr_review_failure.json",
            "--save",
            "--registry-root",
            str(tmp_path),
        ]
    )
    capsys.readouterr()
    main(
        [
            "answer",
            "trace-gh-pr-review-001-human-correction",
            "decision",
            "approve",
            "--registry-root",
            str(tmp_path),
        ]
    )
    capsys.readouterr()
    exit_code = main(
        [
            "approve",
            "trace-gh-pr-review-001-human-correction",
            "--registry-root",
            str(tmp_path),
            "--approved-by",
            "reviewer",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["skill_id"] == "skill-trace-gh-pr-review-001-human-correction"


def test_cli_answer_unknown_question_returns_error(capsys, tmp_path) -> None:
    main(
        [
            "detect",
            "examples/traces/github_pr_review_failure.json",
            "--save",
            "--registry-root",
            str(tmp_path),
        ]
    )
    capsys.readouterr()
    exit_code = main(
        [
            "answer",
            "trace-gh-pr-review-001-human-correction",
            "not-a-question",
            "approve",
            "--registry-root",
            str(tmp_path),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "question 'not-a-question' not found" in captured.err


def test_cli_answer_unknown_option_returns_error(capsys, tmp_path) -> None:
    main(
        [
            "detect",
            "examples/traces/github_pr_review_failure.json",
            "--save",
            "--registry-root",
            str(tmp_path),
        ]
    )
    capsys.readouterr()
    exit_code = main(
        [
            "answer",
            "trace-gh-pr-review-001-human-correction",
            "decision",
            "not-an-option",
            "--registry-root",
            str(tmp_path),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "unknown option 'not-an-option'" in captured.err


def test_cli_export_skill_from_registry(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    exit_code = main(["export-skill", "skill-1", "--registry-root", str(tmp_path)])
    assert exit_code == 0
    assert "# PR Diff First" in capsys.readouterr().out


def test_cli_lint_returns_one_for_errors(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    bad = _skill()
    bad.applies_when = []
    registry.save_skill(bad)
    exit_code = main(["lint", "skill-1", "--registry-root", str(tmp_path)])
    assert exit_code == 1
    assert "LW001" in capsys.readouterr().out


def test_cli_retrieve(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    exit_code = main(["retrieve", "Review this PR", "--registry-root", str(tmp_path)])
    assert exit_code == 0
    results = json.loads(capsys.readouterr().out)
    assert results[0]["skill_id"] == "skill-1"


def test_cli_promote_skill(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill(status=SkillStatus.DRAFT))
    exit_code = main(["promote-skill", "skill-1", "approved", "--registry-root", str(tmp_path)])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "approved"
