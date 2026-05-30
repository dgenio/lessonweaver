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


def test_cli_validate_skill_passes(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    suite = {
        "suite_id": "suite-1",
        "skill_id": "skill-1",
        "examples": [
            {"example_id": "pos", "task": "Review this pull request", "should_load": True},
            {"example_id": "neg", "task": "Generate a SQL migration", "should_load": False},
        ],
    }
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")
    exit_code = main(["validate-skill", str(suite_path), "--registry-root", str(tmp_path)])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["pass_rate"] == 1.0
    assert payload["passed"] == 2


def test_cli_validate_skill_fails_with_exit_code_one(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    suite = {
        "suite_id": "suite-1",
        "skill_id": "skill-1",
        "examples": [
            {"example_id": "fn", "task": "Summarize meeting notes", "should_load": True},
        ],
    }
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")
    exit_code = main(["validate-skill", str(suite_path), "--registry-root", str(tmp_path)])
    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["false_negatives"] == 1


def test_cli_validate_skill_warns_when_suite_skill_id_missing(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    suite = {
        "suite_id": "suite-1",
        "skill_id": "unknown-skill",
        "examples": [
            {"example_id": "pos", "task": "Review this pull request", "should_load": True},
        ],
    }
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")
    exit_code = main(["validate-skill", str(suite_path), "--registry-root", str(tmp_path)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "warning: suite skill_id 'unknown-skill' not found" in captured.err
    assert "expected_skill_id override" in captured.err


def test_cli_promote_skill(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill(status=SkillStatus.DRAFT))
    exit_code = main(["promote-skill", "skill-1", "approved", "--registry-root", str(tmp_path)])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "approved"


def test_cli_log_usage_records_event(capsys, tmp_path) -> None:
    exit_code = main(
        [
            "log-usage",
            "skill-1",
            "Reviewing a pull request",
            "--skill-version",
            "0.2.0",
            "--outcome",
            "resolved",
            "--positive",
            "--id",
            "usage-1",
            "--registry-root",
            str(tmp_path),
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["id"] == "usage-1"
    assert payload["outcome_positive"] is True

    registry = FileSystemRegistry(tmp_path)
    stored = registry.list_skill_usage("skill-1")
    assert len(stored) == 1
    assert stored[0].task_context == "Reviewing a pull request"


def test_cli_report_stale_outputs_json(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill(status=SkillStatus.DEPRECATED))
    exit_code = main(
        ["report-stale", "--registry-root", str(tmp_path), "--now", "2026-05-26T12:00:00Z"]
    )
    assert exit_code == 0
    reports = json.loads(capsys.readouterr().out)
    reasons = {report["reason"] for report in reports}
    assert "deprecated" in reasons
    assert "never_used" in reasons


def test_cli_detect_output_writes_file_and_silences_stdout(capsys, tmp_path) -> None:
    out_path = tmp_path / "candidates.json"
    exit_code = main(
        [
            "detect",
            "examples/traces/github_pr_review_failure.json",
            "--output",
            str(out_path),
        ]
    )
    assert exit_code == 0
    assert capsys.readouterr().out == ""
    candidates = json.loads(out_path.read_text(encoding="utf-8"))
    assert isinstance(candidates, list)
    assert len(candidates) >= 1


def test_cli_detect_missing_file_returns_one(capsys, tmp_path) -> None:
    missing = tmp_path / "does-not-exist.json"
    exit_code = main(["detect", str(missing)])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "file not found" in err
    assert str(missing) in err
    assert "Errno" not in err


def test_cli_detect_invalid_json_returns_two(capsys, tmp_path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    exit_code = main(["detect", str(bad)])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "invalid JSON" in err
    assert "line" in err and "column" in err


def test_cli_export_skill_output_writes_file(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    out_path = tmp_path / "skill.md"
    exit_code = main(
        ["export-skill", "skill-1", "--registry-root", str(tmp_path), "--output", str(out_path)]
    )
    assert exit_code == 0
    assert capsys.readouterr().out == ""
    assert "# PR Diff First" in out_path.read_text(encoding="utf-8")


def test_cli_export_skill_json_envelope(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    exit_code = main(["export-skill", "skill-1", "--registry-root", str(tmp_path), "--json"])
    assert exit_code == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["format"] == "markdown"
    assert "# PR Diff First" in envelope["content"]


def test_cli_export_skill_dry_run_does_not_write(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    out_path = tmp_path / "skill.md"
    exit_code = main(
        [
            "export-skill",
            "skill-1",
            "--registry-root",
            str(tmp_path),
            "--output",
            str(out_path),
            "--dry-run",
        ]
    )
    assert exit_code == 0
    assert not out_path.exists()
    assert f"[dry-run] would write to: {out_path}" in capsys.readouterr().out


def test_cli_approve_dry_run_does_not_persist(capsys, tmp_path) -> None:
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
            "approve",
            "trace-gh-pr-review-001-human-correction",
            "--registry-root",
            str(tmp_path),
            "--dry-run",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["skill_id"] == "skill-trace-gh-pr-review-001-human-correction"
    assert FileSystemRegistry(tmp_path).list_skills() == []


def test_cli_interview_session_create_resume_and_completed_guard(capsys, tmp_path) -> None:
    from lessonweaver.interview import load_session, save_session

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
    session_path = tmp_path / "session.json"
    main(
        [
            "interview",
            "trace-gh-pr-review-001-human-correction",
            "--registry-root",
            str(tmp_path),
            "--session",
            str(session_path),
        ]
    )
    capsys.readouterr()
    assert session_path.exists()

    exit_code = main(["resume-interview", str(session_path), "--registry-root", str(tmp_path)])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    remaining_ids = {question["id"] for question in payload["remaining_questions"]}
    assert "decision" in remaining_ids

    session = load_session(session_path)
    session.completed = True
    save_session(session, session_path)
    exit_code = main(["resume-interview", str(session_path), "--registry-root", str(tmp_path)])
    assert exit_code == 1
    assert "already completed" in capsys.readouterr().err


_TRACE = "examples/traces/github_pr_review_failure.json"
_CID = "trace-gh-pr-review-001-human-correction"


def test_cli_answer_records_into_session(capsys, tmp_path) -> None:
    from lessonweaver.interview import load_session

    main(["detect", _TRACE, "--save", "--registry-root", str(tmp_path)])
    capsys.readouterr()
    session_path = tmp_path / "session.json"
    main(["interview", _CID, "--registry-root", str(tmp_path), "--session", str(session_path)])
    capsys.readouterr()

    exit_code = main(
        [
            "answer",
            _CID,
            "risk_level",
            "high",
            "--registry-root",
            str(tmp_path),
            "--session",
            str(session_path),
        ]
    )
    assert exit_code == 0
    capsys.readouterr()

    session = load_session(session_path)
    assert len(session.answers) == 1
    assert session.answers[0].question_id == "risk_level"
    assert session.current_question_index == 1

    main(["resume-interview", str(session_path), "--registry-root", str(tmp_path)])
    payload = json.loads(capsys.readouterr().out)
    remaining_ids = {question["id"] for question in payload["remaining_questions"]}
    assert "risk_level" not in remaining_ids  # already answered
    assert "approval_requirement" in remaining_ids  # high-risk follow-up queued
    assert payload["current_question_index"] == 1


def test_cli_answer_rejects_completed_session(capsys, tmp_path) -> None:
    from lessonweaver.interview import load_session, save_session

    main(["detect", _TRACE, "--save", "--registry-root", str(tmp_path)])
    capsys.readouterr()
    session_path = tmp_path / "session.json"
    main(["interview", _CID, "--registry-root", str(tmp_path), "--session", str(session_path)])
    capsys.readouterr()
    session = load_session(session_path)
    session.completed = True
    save_session(session, session_path)

    exit_code = main(
        [
            "answer",
            _CID,
            "risk_level",
            "high",
            "--registry-root",
            str(tmp_path),
            "--session",
            str(session_path),
        ]
    )
    assert exit_code == 1
    assert "already completed" in capsys.readouterr().err


def test_cli_interview_session_dry_run_does_not_write(capsys, tmp_path) -> None:
    main(["detect", _TRACE, "--save", "--registry-root", str(tmp_path)])
    capsys.readouterr()
    session_path = tmp_path / "session.json"
    exit_code = main(
        [
            "interview",
            _CID,
            "--registry-root",
            str(tmp_path),
            "--session",
            str(session_path),
            "--dry-run",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert not session_path.exists()
    assert f"[dry-run] would write session to: {session_path}" in out


def test_cli_interview_session_requires_registry_backed_candidate(capsys, tmp_path) -> None:
    candidate = LessonCandidate(
        id="loose-cand",
        summary="Loose candidate not saved to a registry...",
        evidence_trace_ids=["trace-1"],
        evidence_event_ids=["event-1"],
        observed_problem="Agent missed key step.",
        proposed_lesson="Check diff first.",
        confidence=0.6,
        recommended_action_type=RecommendedActionType.SKILL,
        risk_level=RiskLevel.LOW,
        scope=Scope.PROJECT,
    )
    cand_path = tmp_path / "candidate.json"
    cand_path.write_text(json.dumps(candidate.to_dict()), encoding="utf-8")
    session_path = tmp_path / "session.json"
    exit_code = main(
        [
            "interview",
            str(cand_path),
            "--registry-root",
            str(tmp_path / "registry"),
            "--session",
            str(session_path),
        ]
    )
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "registry-backed candidate" in err
    assert not session_path.exists()


def test_cli_resume_missing_candidate_errors_clearly(capsys, tmp_path) -> None:
    from lessonweaver.interview import save_session
    from lessonweaver.models import ReviewSession

    session = ReviewSession(
        session_id="s9",
        candidate_id="ghost",
        started_at="2026-05-30T10:00:00+00:00",
        updated_at="2026-05-30T10:00:00+00:00",
    )
    session_path = tmp_path / "session.json"
    save_session(session, session_path)
    exit_code = main(
        ["resume-interview", str(session_path), "--registry-root", str(tmp_path / "registry")]
    )
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "not in the registry" in err
    assert "ghost" in err
