"""Tests for the TraceImporter protocol and built-in importers (#52, #82)."""

from __future__ import annotations

import pytest

from lessonweaver.importers import (
    CLAUDE_CODE_PROVENANCE_KEY,
    FAILURE_CASE_PROVENANCE_KEY,
    ClaudeCodeTraceImporter,
    DictTraceImporter,
    FailureCaseImporter,
    TraceImporter,
    candidates_from_failure_case,
)
from lessonweaver.models import TraceBundle, TraceEventType
from lessonweaver.traces import validate_trace_dict

CANONICAL_TRACE = {
    "trace_id": "trace-1",
    "source": "unit-test",
    "task": "Do work",
    "events": [{"id": "e1", "type": "user_message"}],
    "outcome": "success",
}

FAILURE_CASE = {
    "schema": "weaver-spec/failure-case@1",
    "failure_id": "fc-0001",
    "task": "Decide whether to deploy",
    "source": "fuzz-replay",
    "replay": {"ref": "replays/fc-0001.json", "reproducible": True},
    "failure": {"summary": "Stale artifact used as evidence.", "severity": "high"},
    "correction": {"summary": "Required a fresh check first."},
}


def test_builtin_importers_satisfy_protocol() -> None:
    # TraceImporter is runtime_checkable, so isinstance verifies the contract.
    assert isinstance(ClaudeCodeTraceImporter(), TraceImporter)
    assert isinstance(DictTraceImporter(), TraceImporter)
    assert isinstance(FailureCaseImporter(), TraceImporter)


# --- ClaudeCodeTraceImporter --------------------------------------------------


CLAUDE_CODE_TRACE = {
    "schema": "claude-code/transcript@1",
    "session_id": "claude-session-42",
    "task": "Fix the auth regression",
    "cwd": "/repo",
    "transcript": [
        {
            "uuid": "user-1",
            "type": "user",
            "message": "The login test is failing for alice@example.com",
            "line": 4,
        },
        {
            "uuid": "tool-1",
            "type": "tool_use",
            "name": "Edit",
            "input": {"file_path": "src/auth.py", "old_string": "Bearer sk-secret-token-value"},
        },
        {
            "uuid": "result-1",
            "type": "tool_result",
            "tool_use_id": "tool-1",
            "content": "No match found",
            "is_error": True,
        },
        {
            "uuid": "assistant-1",
            "type": "assistant",
            "message": "I assumed the token check lived in auth.py.",
        },
        {
            "uuid": "human-1",
            "type": "human_correction",
            "content": "Use src/login.py instead and never log alice@example.com.",
            "path": "src/login.py",
            "unexpected": "preserve-me",
        },
    ],
}


def test_claude_code_can_import_transcript_payload() -> None:
    importer = ClaudeCodeTraceImporter()
    assert importer.can_import(CLAUDE_CODE_TRACE) is True
    assert importer.can_import({"source": "claude_code", "events": []}) is True
    assert importer.can_import(CANONICAL_TRACE) is False


def test_claude_code_maps_realistic_trace_and_validates() -> None:
    bundle = ClaudeCodeTraceImporter().import_trace(CLAUDE_CODE_TRACE)

    assert validate_trace_dict(bundle.to_dict()) == []
    assert bundle.trace_id == "claude-session-42"
    assert bundle.source == "claude_code"
    assert bundle.task == "Fix the auth regression"
    assert bundle.outcome == "corrected_by_human"
    assert [event.type for event in bundle.events] == [
        TraceEventType.USER_MESSAGE,
        TraceEventType.TOOL_CALL,
        TraceEventType.TOOL_RESULT,
        TraceEventType.ASSISTANT_MESSAGE,
        TraceEventType.HUMAN_CORRECTION,
    ]
    assert bundle.events[1].metadata["tool_name"] == "Edit"
    assert bundle.events[1].metadata["path"] == "src/auth.py"
    assert bundle.events[2].success is False
    assert bundle.events[2].status == "failed"
    assert bundle.events[4].metadata["path"] == "src/login.py"
    assert bundle.events[4].metadata["claude_code"]["unexpected"] == "preserve-me"
    provenance = bundle.metadata[CLAUDE_CODE_PROVENANCE_KEY]
    assert provenance["session_id"] == "claude-session-42"
    assert provenance["cwd"] == "/repo"


def test_claude_code_handles_missing_optional_fields() -> None:
    bundle = ClaudeCodeTraceImporter().import_trace(
        {
            "schema": "claude-code/hook@1",
            "session_id": "minimal",
            "events": [
                {"type": "tool_result", "content": "done", "is_error": False},
            ],
        }
    )

    assert validate_trace_dict(bundle.to_dict()) == []
    assert bundle.task == "Claude Code session minimal"
    assert bundle.outcome == "success"
    assert bundle.events[0].id == "minimal-event-1"
    assert bundle.events[0].type is TraceEventType.TOOL_RESULT


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        ({"schema": "claude-code/transcript@1", "transcript": []}, "session_id"),
        ({"schema": "claude-code/transcript@1", "session_id": "s1"}, "events"),
        (
            {"schema": "claude-code/transcript@1", "session_id": "s1", "events": ["bad"]},
            "event\\[0\\]",
        ),
    ],
)
def test_claude_code_rejects_malformed_payloads(payload: dict, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        ClaudeCodeTraceImporter().import_trace(payload)


def test_claude_code_sanitizes_content_by_default() -> None:
    bundle = ClaudeCodeTraceImporter().import_trace(CLAUDE_CODE_TRACE)

    contents = "\n".join(event.content or "" for event in bundle.events)
    assert "alice@example.com" not in contents
    assert "Bearer sk-secret-token-value" not in contents
    assert "[REDACTED by email]" in contents
    assert "[REDACTED by bearer_token]" in contents


# --- DictTraceImporter ---------------------------------------------------------


def test_dict_importer_can_import_canonical_only() -> None:
    importer = DictTraceImporter()
    assert importer.can_import(CANONICAL_TRACE) is True
    assert importer.can_import({"failure_id": "x", "failure": {}}) is False
    assert importer.can_import({"trace_id": "x"}) is False  # no events list


def test_dict_importer_matches_from_dict() -> None:
    assert DictTraceImporter().import_trace(CANONICAL_TRACE) == TraceBundle.from_dict(
        CANONICAL_TRACE
    )


def test_dict_importer_rejects_invalid_payload() -> None:
    with pytest.raises(ValueError, match="missing required field: source"):
        DictTraceImporter().import_trace({"trace_id": "x", "events": []})


# --- FailureCaseImporter -------------------------------------------------------


def test_failure_case_can_import() -> None:
    importer = FailureCaseImporter()
    assert importer.can_import(FAILURE_CASE) is True  # schema marker
    assert importer.can_import({"failure_id": "x", "failure": {}}) is True  # structural
    assert importer.can_import(CANONICAL_TRACE) is False
    assert importer.can_import({"failure": {}}) is False  # no id


def test_failure_case_maps_to_bundle_with_correction() -> None:
    bundle = FailureCaseImporter().import_trace(FAILURE_CASE)
    assert bundle.trace_id == "fc-0001"
    assert bundle.source == "fuzz-replay"
    assert bundle.outcome == "corrected_by_human"
    assert [e.type for e in bundle.events] == [
        TraceEventType.EVALUATION_RESULT,
        TraceEventType.HUMAN_CORRECTION,
    ]
    assert bundle.events[0].status == "failed"
    provenance = bundle.metadata[FAILURE_CASE_PROVENANCE_KEY]
    assert provenance["failure_id"] == "fc-0001"
    assert provenance["severity"] == "high"
    assert provenance["replay_ref"] == "replays/fc-0001.json"
    assert provenance["reproducible"] is True


def test_failure_case_without_correction_is_failure_outcome() -> None:
    bundle = FailureCaseImporter().import_trace(
        {"failure_id": "fc-2", "failure": {"summary": "boom"}}
    )
    assert bundle.outcome == "failure"
    assert [e.type for e in bundle.events] == [TraceEventType.EVALUATION_RESULT]


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        ({"task": "x"}, "Unrecognized failure case"),
        ({"failure_id": "", "failure": {"summary": "x"}}, "non-empty 'failure_id'"),
        ({"failure_id": "x", "failure": "not-an-object"}, "missing a 'failure' object"),
    ],
)
def test_failure_case_invalid_payloads(payload: dict, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        FailureCaseImporter().import_trace(payload)


def test_candidates_from_failure_case_stamps_provenance() -> None:
    candidates = candidates_from_failure_case(FAILURE_CASE)
    # A failed eval + a human correction each yield a conservative candidate.
    assert len(candidates) == 2
    ids = {c.id for c in candidates}
    assert ids == {"fc-0001-failed-eval", "fc-0001-human-correction"}
    for candidate in candidates:
        assert candidate.metadata[FAILURE_CASE_PROVENANCE_KEY]["failure_id"] == "fc-0001"
