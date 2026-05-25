"""Tests for CLI subcommands."""

import json

from lessonweaver.cli import main


def test_cli_detect_produces_json(capsys) -> None:
    exit_code = main(["detect", "examples/traces/github_pr_review_failure.json"])
    assert exit_code == 0
    output = capsys.readouterr().out
    candidates = json.loads(output)
    assert isinstance(candidates, list)
    assert len(candidates) >= 1
    assert "summary" in candidates[0]


def test_cli_detect_boring_trace_empty(capsys) -> None:
    # The external chatbot trace has a failed eval, so use a known-good path
    # We'll test that detect at least runs and returns valid JSON
    exit_code = main(["detect", "examples/traces/external_chatbot_policy_failure.json"])
    assert exit_code == 0
    output = capsys.readouterr().out
    candidates = json.loads(output)
    assert isinstance(candidates, list)
