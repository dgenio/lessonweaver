"""Tests for the TraceImporter protocol and built-in importers (#52, #82)."""

from __future__ import annotations

import pytest

from lessonweaver.detection import LessonDetector
from lessonweaver.importers import (
    FAILURE_CASE_PROVENANCE_KEY,
    DictTraceImporter,
    FailureCaseImporter,
    OpenCodeTraceImporter,
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
    assert isinstance(DictTraceImporter(), TraceImporter)
    assert isinstance(FailureCaseImporter(), TraceImporter)
    assert isinstance(OpenCodeTraceImporter(), TraceImporter)


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


# --- OpenCodeTraceImporter ----------------------------------------------------


OPENCODE_TRACE = {
    "source": "opencode",
    "session_id": "oc-session-1",
    "task": "Review a pull request",
    "workspace": "/repo",
    "events": [
        {"id": "u1", "type": "user", "message": "Please review PR #42"},
        {
            "id": "t1",
            "type": "tool_call",
            "tool": "git.diff",
            "input": {"path": "src/app.py"},
        },
        {
            "id": "r1",
            "type": "tool_result",
            "tool": "git.diff",
            "output": "No diff read",
            "success": False,
        },
        {
            "id": "h1",
            "type": "correction",
            "message": "You must inspect the diff before approving.",
            "file": "src/app.py",
        },
    ],
}


def test_opencode_importer_can_import_structural_payload() -> None:
    importer = OpenCodeTraceImporter()
    assert importer.can_import(OPENCODE_TRACE) is True
    assert importer.can_import({"schema": "opencode/plugin-events@1", "events": []}) is True
    assert importer.can_import(CANONICAL_TRACE) is False


def test_opencode_importer_normalizes_to_valid_trace_bundle() -> None:
    bundle = OpenCodeTraceImporter().import_trace(OPENCODE_TRACE)

    assert bundle.trace_id == "oc-session-1"
    assert bundle.source == "opencode"
    assert bundle.task == "Review a pull request"
    assert bundle.outcome == "corrected_by_human"
    assert [event.type for event in bundle.events] == [
        TraceEventType.USER_MESSAGE,
        TraceEventType.TOOL_CALL,
        TraceEventType.TOOL_RESULT,
        TraceEventType.HUMAN_CORRECTION,
    ]
    assert bundle.events[2].success is False
    assert bundle.events[3].content == "You must inspect the diff before approving."
    assert validate_trace_dict(bundle.to_dict()) == []


def test_opencode_failed_tool_result_enables_fallback_detection() -> None:
    bundle = OpenCodeTraceImporter().import_trace(
        {
            "source": "opencode",
            "session_id": "oc-tool-fallback",
            "task": "Find auth config",
            "events": [
                {"id": "call-1", "type": "tool_call", "tool": "read", "input": "auth.py"},
                {
                    "id": "result-1",
                    "type": "tool_result",
                    "tool_call_id": "call-1",
                    "output": "No match found",
                    "success": False,
                },
                {"id": "call-2", "type": "tool_call", "tool": "read", "input": "login.py"},
                {
                    "id": "result-2",
                    "type": "tool_result",
                    "tool_call_id": "call-2",
                    "output": "Found match",
                    "success": True,
                },
            ],
        }
    )

    candidates = LessonDetector().detect(bundle)

    assert bundle.events[0].success is False
    assert bundle.events[0].status == "failed"
    assert bundle.events[2].success is True
    assert [candidate.id for candidate in candidates] == ["oc-tool-fallback-tool-fallback"]


def test_opencode_importer_preserves_safe_unknown_fields_in_metadata() -> None:
    bundle = OpenCodeTraceImporter().import_trace(OPENCODE_TRACE)

    assert bundle.metadata["opencode"]["workspace"] == "/repo"
    assert bundle.events[1].metadata["tool"] == "git.diff"
    assert bundle.events[1].metadata["input"] == {"path": "src/app.py"}
    assert bundle.events[3].metadata["file"] == "src/app.py"


def test_opencode_importer_fills_missing_optional_event_fields() -> None:
    bundle = OpenCodeTraceImporter().import_trace(
        {
            "source": "opencode",
            "session_id": "oc-minimal",
            "events": [{"type": "assistant", "message": "I will inspect the diff."}],
        }
    )

    assert bundle.task == "OpenCode session"
    assert bundle.events[0].id == "oc-minimal-event-1"
    assert bundle.events[0].type is TraceEventType.ASSISTANT_MESSAGE
    assert bundle.outcome == "success"


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        ({"source": "opencode", "events": []}, "session_id"),
        ({"source": "opencode", "session_id": "oc-1"}, "events"),
        ({"source": "opencode", "session_id": "oc-1", "events": ["bad"]}, "event object"),
    ],
)
def test_opencode_importer_rejects_malformed_payloads(payload: dict, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        OpenCodeTraceImporter().import_trace(payload)


def test_opencode_importer_redacts_event_content_by_default() -> None:
    bundle = OpenCodeTraceImporter().import_trace(
        {
            "source": "opencode",
            "session_id": "oc-redact",
            "events": [
                {
                    "type": "correction",
                    "message": "Do not echo a.user@example.com in the answer.",
                }
            ],
        }
    )

    assert bundle.events[0].content == "Do not echo [REDACTED by email] in the answer."
