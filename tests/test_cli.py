"""Tests for CLI subcommands."""

import json
from datetime import datetime, timezone
from pathlib import Path

from lessonweaver.cli import main
from lessonweaver.models import (
    LessonCandidate,
    LessonStatus,
    RecommendedActionType,
    RiskLevel,
    Scope,
    SkillCard,
    SkillStatus,
    SkillUsageEvent,
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


# The full set of base review answers that satisfies the enforced review gate
# (a low-risk skill with no triggered follow-ups). decision=approve last.
_COMPLETE_REVIEW = [
    ("scope", "project"),
    ("action_type", "skill"),
    ("risk_level", "low"),
    ("applicability", "always"),
    ("negative_conditions", "none"),
    ("decision", "approve"),
]


def _answer_full_review(candidate_id: str, registry_root: Path) -> None:
    for question_id, option_id in _COMPLETE_REVIEW:
        main(
            [
                "answer",
                candidate_id,
                question_id,
                option_id,
                "--registry-root",
                str(registry_root),
            ]
        )


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
    _answer_full_review("trace-gh-pr-review-001-human-correction", tmp_path)
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


def test_cli_approve_blocks_incomplete_review(capsys, tmp_path) -> None:
    main(["detect", _TRACE, "--save", "--registry-root", str(tmp_path)])
    capsys.readouterr()
    exit_code = main(["approve", _CID, "--registry-root", str(tmp_path)])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "review is incomplete" in err
    assert "decision" in err
    assert FileSystemRegistry(tmp_path).list_skills() == []


def test_cli_approve_allow_incomplete_records_override(capsys, tmp_path) -> None:
    main(["detect", _TRACE, "--save", "--registry-root", str(tmp_path)])
    capsys.readouterr()
    exit_code = main(
        [
            "approve",
            _CID,
            "--registry-root",
            str(tmp_path),
            "--approved-by",
            "reviewer",
            "--allow-incomplete-review",
        ]
    )
    assert exit_code == 0
    capsys.readouterr()
    skill = FileSystemRegistry(tmp_path).load_skill(f"skill-{_CID}")
    override = skill.metadata["incomplete_review_override"]
    assert override["approved_by"] == "reviewer"
    assert "decision" in override["unanswered_questions"]


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


def test_cli_export_skill_dox_agents_md(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill())
    exit_code = main(
        [
            "export-skill",
            "skill-1",
            "--format",
            "dox-agents-md",
            "--registry-root",
            str(tmp_path),
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "<!-- lessonweaver profile=dox-agents-md skill_id=skill-1" in out
    assert "## Child Instruction Index" in out


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
            "--allow-incomplete-review",
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


def test_cli_detect_sanitize_runs_and_preserves_detection(capsys, tmp_path) -> None:
    # A trace whose human-correction content carries an email; --sanitize must
    # scrub content without breaking detection (one human-correction candidate).
    trace = {
        "trace_id": "trace-sanitize-1",
        "source": "unit-test",
        "task": "Handle a customer request",
        "events": [
            {"id": "e1", "type": "user_message", "content": "reach me at a.user@example.com"},
            {"id": "e2", "type": "human_correction", "content": "Stop echoing a.user@example.com"},
        ],
        "outcome": "corrected_by_human",
    }
    path = tmp_path / "trace.json"
    path.write_text(json.dumps(trace), encoding="utf-8")
    exit_code = main(["detect", str(path), "--sanitize"])
    assert exit_code == 0
    candidates = json.loads(capsys.readouterr().out)
    assert [c["id"] for c in candidates] == ["trace-sanitize-1-human-correction"]


def test_cli_import_failure_case_produces_candidates_with_provenance(capsys) -> None:
    exit_code = main(["import-failure-case", "examples/failure_cases/replayable_eval_failure.json"])
    assert exit_code == 0
    candidates = json.loads(capsys.readouterr().out)
    assert len(candidates) == 2
    for candidate in candidates:
        provenance = candidate["metadata"]["failure_case"]
        assert provenance["failure_id"] == "fc-eval-as-evidence-001"
        assert provenance["reproducible"] is True


def test_cli_import_failure_case_save_persists_to_registry(capsys, tmp_path) -> None:
    main(
        [
            "import-failure-case",
            "examples/failure_cases/replayable_eval_failure.json",
            "--save",
            "--registry-root",
            str(tmp_path),
        ]
    )
    capsys.readouterr()
    registry = FileSystemRegistry(str(tmp_path))
    stored = registry.load_candidate("fc-eval-as-evidence-001-human-correction")
    assert stored.metadata["failure_case"]["failure_id"] == "fc-eval-as-evidence-001"


def test_cli_cluster_groups_repeated_pattern(capsys, tmp_path) -> None:
    # Two distinct traces (different trace_ids) carrying the same human-correction
    # pattern must collapse into one cluster of distinct candidates.
    source = json.loads(
        Path("examples/traces/github_pr_review_failure.json").read_text(encoding="utf-8")
    )
    trace_paths = []
    for trace_id in ("pr-review-a", "pr-review-b"):
        source["trace_id"] = trace_id
        path = tmp_path / f"{trace_id}.json"
        path.write_text(json.dumps(source), encoding="utf-8")
        trace_paths.append(str(path))
    exit_code = main(["cluster", *trace_paths])
    assert exit_code == 0
    clusters = json.loads(capsys.readouterr().out)
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster["occurrence_count"] == 2
    # Members are genuinely distinct candidates from the two separate traces.
    assert set(cluster["member_ids"]) == {
        "pr-review-a-human-correction",
        "pr-review-b-human-correction",
    }


def test_cli_eval_detection_reports_metrics(capsys) -> None:
    exit_code = main(["eval-detection", "examples/detection_corpus/corpus.json"])
    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["true_positives"] == 5
    assert report["false_negatives"] == 1
    assert report["precision"] == 1.0
    assert report["recall"] < 1.0


def test_cli_eval_detection_min_recall_gate_fails(capsys) -> None:
    exit_code = main(
        ["eval-detection", "examples/detection_corpus/corpus.json", "--min-recall", "1.0"]
    )
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "recall" in err


def test_cli_eval_detection_min_precision_gate_passes(capsys) -> None:
    exit_code = main(
        ["eval-detection", "examples/detection_corpus/corpus.json", "--min-precision", "1.0"]
    )
    assert exit_code == 0


# --- review-trace (#106) ----------------------------------------------------


def test_cli_review_trace_emits_packet_and_saves_candidates(capsys, tmp_path) -> None:
    exit_code = main(["review-trace", _TRACE, "--registry-root", str(tmp_path)])
    assert exit_code == 0
    packet = json.loads(capsys.readouterr().out)
    assert packet["trace_id"] == "trace-gh-pr-review-001"
    candidate = packet["candidates"][0]
    assert candidate["candidate_id"] == _CID
    assert "decision" in candidate["remaining_questions"]
    assert candidate["review_complete"] is False
    assert packet["approval"] is None
    # The detected candidate was persisted so the explicit subcommands can resume it.
    assert FileSystemRegistry(tmp_path).load_candidate(_CID).id == _CID


def test_cli_review_trace_apply_answer_reduces_remaining(capsys, tmp_path) -> None:
    exit_code = main(
        ["review-trace", _TRACE, "--registry-root", str(tmp_path), "--answer", "decision=approve"]
    )
    assert exit_code == 0
    candidate = json.loads(capsys.readouterr().out)["candidates"][0]
    assert "decision" not in candidate["remaining_questions"]


def test_cli_review_trace_bad_question_id_leaves_no_partial_writes(capsys, tmp_path) -> None:
    # A valid KEY=VALUE whose question id does not exist must fail before any
    # candidate is persisted, so the command leaves no partial side effects.
    exit_code = main(
        [
            "review-trace",
            _TRACE,
            "--registry-root",
            str(tmp_path),
            "--answer",
            "not-a-question=approve",
        ]
    )
    assert exit_code == 2
    assert "question 'not-a-question' not found" in capsys.readouterr().err
    assert FileSystemRegistry(tmp_path).list_candidates() == []


def test_cli_review_trace_target_includes_export_preview(capsys, tmp_path) -> None:
    exit_code = main(
        ["review-trace", _TRACE, "--registry-root", str(tmp_path), "--target", "agents-md"]
    )
    assert exit_code == 0
    preview = json.loads(capsys.readouterr().out)["candidates"][0]["export_preview"]
    assert preview["format"] == "agents-md"
    assert "<!-- lessonweaver skill_id=" in preview["content"]


def test_cli_review_trace_approve_blocked_when_incomplete(capsys, tmp_path) -> None:
    exit_code = main(["review-trace", _TRACE, "--registry-root", str(tmp_path), "--approve"])
    assert exit_code == 1
    assert "review is incomplete" in capsys.readouterr().err


def test_cli_review_trace_full_answers_then_approve(capsys, tmp_path) -> None:
    argv = ["review-trace", _TRACE, "--registry-root", str(tmp_path)]
    for question_id, option_id in _COMPLETE_REVIEW:
        argv += ["--answer", f"{question_id}={option_id}"]
    argv += ["--approve", "--approved-by", "reviewer"]
    exit_code = main(argv)
    assert exit_code == 0
    packet = json.loads(capsys.readouterr().out)
    assert packet["approval"]["skill_id"] == f"skill-{_CID}"
    assert FileSystemRegistry(tmp_path).load_skill(f"skill-{_CID}").id == f"skill-{_CID}"


def test_cli_review_trace_ambiguous_requires_candidate(capsys, tmp_path) -> None:
    trace = {
        "trace_id": "multi",
        "source": "unit-test",
        "task": "do work",
        "events": [
            {"id": "e1", "type": "evaluation_result", "status": "failed"},
            {"id": "e2", "type": "human_correction", "content": "fix it"},
        ],
        "outcome": "corrected_by_human",
    }
    path = tmp_path / "multi.json"
    path.write_text(json.dumps(trace), encoding="utf-8")
    exit_code = main(["review-trace", str(path), "--registry-root", str(tmp_path), "--approve"])
    assert exit_code == 1
    assert "pass --candidate" in capsys.readouterr().err


# --- export-file (#107) -----------------------------------------------------


def test_cli_export_file_default_previews_diff_without_writing(capsys, tmp_path) -> None:
    FileSystemRegistry(tmp_path).save_skill(_skill())
    target = tmp_path / "AGENTS.md"
    exit_code = main(
        ["export-file", "skill-1", "--path", str(target), "--registry-root", str(tmp_path)]
    )
    assert exit_code == 0
    assert not target.exists()
    out = capsys.readouterr().out
    assert f"+++ b/{target}" in out
    assert "lessonweaver:begin skill_id=skill-1" in out


def test_cli_export_file_write_creates_then_is_idempotent(capsys, tmp_path) -> None:
    FileSystemRegistry(tmp_path).save_skill(_skill())
    target = tmp_path / "AGENTS.md"
    assert (
        main(
            [
                "export-file",
                "skill-1",
                "--path",
                str(target),
                "--registry-root",
                str(tmp_path),
                "--write",
            ]
        )
        == 0
    )
    assert f"created: {target}" in capsys.readouterr().out
    assert "lessonweaver:begin skill_id=skill-1" in target.read_text(encoding="utf-8")

    assert (
        main(
            [
                "export-file",
                "skill-1",
                "--path",
                str(target),
                "--registry-root",
                str(tmp_path),
                "--write",
            ]
        )
        == 0
    )
    assert "no changes" in capsys.readouterr().out


def test_cli_export_file_dry_run_does_not_write_even_with_write(capsys, tmp_path) -> None:
    FileSystemRegistry(tmp_path).save_skill(_skill())
    target = tmp_path / "AGENTS.md"
    exit_code = main(
        [
            "export-file",
            "skill-1",
            "--path",
            str(target),
            "--registry-root",
            str(tmp_path),
            "--write",
            "--dry-run",
        ]
    )
    assert exit_code == 0
    assert not target.exists()
    assert f"[dry-run] would write to: {target}" in capsys.readouterr().out


def test_cli_export_file_preserves_handwritten_content(capsys, tmp_path) -> None:
    FileSystemRegistry(tmp_path).save_skill(_skill())
    target = tmp_path / "AGENTS.md"
    target.write_text("# House rules\n\nKeep PRs small.\n", encoding="utf-8")
    main(
        [
            "export-file",
            "skill-1",
            "--path",
            str(target),
            "--registry-root",
            str(tmp_path),
            "--write",
        ]
    )
    capsys.readouterr()
    content = target.read_text(encoding="utf-8")
    assert "Keep PRs small." in content
    assert "lessonweaver:begin skill_id=skill-1" in content


# --- explain-load / load --explain (#110) -----------------------------------


def test_cli_explain_load_reports_loaded_and_skipped(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_skill("skill-active"))
    registry.save_skill(_skill("skill-draft", status=SkillStatus.DRAFT))
    exit_code = main(["explain-load", "Review this pull request", "--registry-root", str(tmp_path)])
    assert exit_code == 0
    diag = json.loads(capsys.readouterr().out)
    assert [item["skill_id"] for item in diag["loaded"]] == ["skill-active"]
    skipped = {item["skill_id"]: item["reason"] for item in diag["skipped"]}
    assert skipped["skill-draft"] == "status_not_active"
    assert diag["budget"]["used_chars"] > 0


def test_cli_load_explain_flag_emits_diagnostics(capsys, tmp_path) -> None:
    FileSystemRegistry(tmp_path).save_skill(_skill())
    exit_code = main(
        ["load", "Review this pull request", "--registry-root", str(tmp_path), "--explain"]
    )
    assert exit_code == 0
    diag = json.loads(capsys.readouterr().out)
    assert "loaded" in diag and "budget" in diag and "skipped" in diag


# --- cleanup-skills (#112) --------------------------------------------------


def _expired_skill(skill_id: str = "exp") -> SkillCard:
    skill = _skill(skill_id)
    skill.expires_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    return skill


def test_cli_cleanup_skills_dry_run_reports_without_writing(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_expired_skill())
    registry.save_usage_event(
        SkillUsageEvent(id="u1", skill_id="exp", skill_version="0.2.0", task_context="ran")
    )
    exit_code = main(
        ["cleanup-skills", "--registry-root", str(tmp_path), "--now", "2030-01-01T00:00:00Z"]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    reasons = {action["reason"] for action in payload["actions"]}
    assert "expired" in reasons
    assert payload["applied"] == []
    assert registry.load_skill("exp").status is SkillStatus.ACTIVE


def test_cli_cleanup_skills_write_deprecates_expired(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_expired_skill())
    exit_code = main(
        [
            "cleanup-skills",
            "--registry-root",
            str(tmp_path),
            "--now",
            "2030-01-01T00:00:00Z",
            "--write",
        ]
    )
    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["applied"] == ["exp"]
    assert registry.load_skill("exp").status is SkillStatus.DEPRECATED


def test_cli_cleanup_skills_dry_run_overrides_write(capsys, tmp_path) -> None:
    registry = FileSystemRegistry(tmp_path)
    registry.save_skill(_expired_skill())
    exit_code = main(
        [
            "cleanup-skills",
            "--registry-root",
            str(tmp_path),
            "--now",
            "2030-01-01T00:00:00Z",
            "--write",
            "--dry-run",
        ]
    )
    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["applied"] == []
    assert registry.load_skill("exp").status is SkillStatus.ACTIVE
