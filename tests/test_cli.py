"""Tests for CLI subcommands."""

import json

from lessonweaver.cli import main
from lessonweaver.models import (
    LessonCandidate,
    LessonStatus,
    RecommendedActionType,
    RiskLevel,
    Scope,
    SkillCard,
    SkillStatus,
)
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


def _candidate(
    candidate_id: str = "cand-1",
    action_type: RecommendedActionType = RecommendedActionType.EVAL,
    status: LessonStatus = LessonStatus.APPROVED,
) -> LessonCandidate:
    return LessonCandidate(
        id=candidate_id,
        summary="Inspect diffs before PR review",
        evidence_trace_ids=["trace-1"],
        evidence_event_ids=["e1"],
        observed_problem="Agent approved a PR without inspecting the diff.",
        proposed_lesson="Inspect changed files before drawing review conclusions.",
        confidence=0.62,
        recommended_action_type=action_type,
        risk_level=RiskLevel.MEDIUM,
        scope=Scope.PROJECT,
        status=status,
    )


def test_cli_export_skill_from_registry(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    exit_code = main(["export-skill", "skill-1", "--registry-root", str(tmp_path)])
    assert exit_code == 0
    assert "# PR Diff First" in capsys.readouterr().out


def test_cli_export_skill_agents_md(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    exit_code = main(
        ["export-skill", "skill-1", "--format", "agents-md", "--registry-root", str(tmp_path)]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "<!-- lessonweaver skill_id=skill-1" in out
    assert "### PR Diff First" in out


def test_cli_export_skill_copilot_repo(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    exit_code = main(
        ["export-skill", "skill-1", "--format", "copilot-repo", "--registry-root", str(tmp_path)]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "<!-- lessonweaver skill_id=skill-1 version=" in out
    assert "## PR Diff First" in out


def test_cli_export_skill_claude_skill(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    exit_code = main(
        ["export-skill", "skill-1", "--format", "claude-skill", "--registry-root", str(tmp_path)]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "# PR Diff First" in out
    assert "## When to use" in out


def test_cli_export_skill_claude_rule(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    exit_code = main(
        ["export-skill", "skill-1", "--format", "claude-rule", "--registry-root", str(tmp_path)]
    )
    assert exit_code == 0
    assert "# Rule: PR Diff First" in capsys.readouterr().out


def test_cli_export_skill_claude_md(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    exit_code = main(
        ["export-skill", "skill-1", "--format", "claude-md", "--registry-root", str(tmp_path)]
    )
    assert exit_code == 0
    assert "## Operational guidance: PR Diff First" in capsys.readouterr().out


def test_cli_export_skill_copilot_path_applies_to(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    exit_code = main(
        [
            "export-skill",
            "skill-1",
            "--format",
            "copilot-path",
            "--applies-to",
            "src/**/*.py",
            "--registry-root",
            str(tmp_path),
        ]
    )
    assert exit_code == 0
    assert 'applyTo: "src/**/*.py"' in capsys.readouterr().out


def test_cli_export_skill_codex_is_json_directory(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    exit_code = main(
        ["export-skill", "skill-1", "--format", "codex", "--registry-root", str(tmp_path)]
    )
    assert exit_code == 0
    directory = json.loads(capsys.readouterr().out)
    assert set(directory) == {"SKILL.md", "metadata.json"}
    assert json.loads(directory["metadata.json"])["id"] == "skill-1"


def test_cli_export_lesson_eval_from_registry(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_candidate(_candidate())
    exit_code = main(
        ["export-lesson", "cand-1", "--format", "eval", "--registry-root", str(tmp_path)]
    )
    assert exit_code == 0
    assert "# Eval: Inspect diffs before PR review" in capsys.readouterr().out


def test_cli_export_lesson_guardrail(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_candidate(_candidate(action_type=RecommendedActionType.GUARDRAIL))
    exit_code = main(
        ["export-lesson", "cand-1", "--format", "guardrail", "--registry-root", str(tmp_path)]
    )
    assert exit_code == 0
    assert "# Guardrail: Inspect diffs before PR review" in capsys.readouterr().out


def test_cli_export_lesson_workflow(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_candidate(_candidate(action_type=RecommendedActionType.WORKFLOW_CHANGE))
    exit_code = main(
        ["export-lesson", "cand-1", "--format", "workflow", "--registry-root", str(tmp_path)]
    )
    assert exit_code == 0
    assert "# Workflow recommendation: Inspect diffs before PR review" in capsys.readouterr().out


def test_cli_export_lesson_rejects_unapproved_candidate(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_candidate(_candidate(status=LessonStatus.CANDIDATE))
    exit_code = main(
        ["export-lesson", "cand-1", "--format", "eval", "--registry-root", str(tmp_path)]
    )
    assert exit_code == 1
    assert "not approved" in capsys.readouterr().err


def test_cli_export_lesson_rejects_action_type_mismatch(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_candidate(_candidate(action_type=RecommendedActionType.EVAL))
    exit_code = main(
        ["export-lesson", "cand-1", "--format", "guardrail", "--registry-root", str(tmp_path)]
    )
    assert exit_code == 1
    assert "cannot export as 'guardrail'" in capsys.readouterr().err


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
